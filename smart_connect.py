#!/usr/bin/env python3
"""Local, one-shot SMART-on-FHIR connector for Clippi-Health.

The helper binds only to loopback, opens the system browser for OAuth, downloads
FHIR directly from the selected health system, writes a local NDJSON source, and
discards access tokens when it exits.  It never uses a Clippi-Health cloud service.
"""
import argparse
import base64
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("CLIPPI_HEALTH_ROOT", SOURCE_ROOT)).expanduser().resolve()
RESOURCES = Path(os.environ.get("CLIPPI_HEALTH_RESOURCES", SOURCE_ROOT)).expanduser().resolve()
CONNECTORS = RESOURCES / "connectors"
LOCAL_CONNECTORS = ROOT / "raw" / "connectors"
RAW_FHIR = ROOT / "raw" / "fhir"
DEFAULT_TYPES = [
    "AllergyIntolerance", "CarePlan", "CareTeam", "Condition", "DiagnosticReport",
    "DocumentReference", "Encounter", "Goal", "Immunization", "MedicationRequest",
    "MedicationStatement", "Observation", "Procedure",
]


def b64url(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def is_loopback(host):
    return (host or "").lower() in {"127.0.0.1", "localhost", "::1"}


def validate_remote_url(value, label="URL", allow_loopback_http=False):
    parsed = urllib.parse.urlparse(value)
    allowed_http = allow_loopback_http and parsed.scheme == "http" and is_loopback(parsed.hostname)
    if parsed.scheme != "https" and not allowed_http:
        raise ValueError(f"{label} must use HTTPS" + (" or loopback HTTP" if allow_loopback_http else ""))
    if not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
        raise ValueError(f"{label} is invalid")
    return value.rstrip("/")


def validate_source(value):
    value = value.lower()
    if not re.fullmatch(r"fhir-[a-z0-9_-]+", value):
        raise ValueError("connector key must match fhir-[a-z0-9_-]+")
    return value


def validate_profile(profile, require_client_id=True):
    required = {"key", "name", "org"}
    missing = sorted(required - profile.keys())
    if missing:
        raise ValueError("connector profile is missing: " + ", ".join(missing))
    profile = dict(profile)
    profile["key"] = validate_source(profile["key"])
    if profile.get("client_secret"):
        raise ValueError("local connectors must be public clients; client_secret is forbidden")
    direct_capable = any(profile.get(field) for field in ("fhir_base", "redirect_uri", "client_id"))
    if direct_capable:
        direct_missing = [field for field in ("fhir_base", "redirect_uri") if not profile.get(field)]
        if direct_missing:
            raise ValueError("direct connector profile is missing: " + ", ".join(direct_missing))
        profile["fhir_base"] = validate_remote_url(profile["fhir_base"], "FHIR base", True)
        redirect = urllib.parse.urlparse(profile["redirect_uri"])
        if redirect.scheme != "http" or redirect.hostname != "127.0.0.1" or redirect.path != "/oauth/callback":
            raise ValueError("redirect_uri must be http://127.0.0.1:<port>/oauth/callback")
        if not redirect.port or redirect.port < 1024:
            raise ValueError("redirect_uri must use a fixed unprivileged loopback port")
    else:
        profile["fhir_base"] = ""
        profile["redirect_uri"] = ""
    client_id = str(profile.get("client_id") or "").strip()
    if require_client_id and not direct_capable:
        raise ValueError("connector profile does not offer direct OAuth")
    if require_client_id and not client_id:
        raise ValueError("connector profile requires a public client_id")
    if client_id and (len(client_id) > 256 or not re.fullmatch(r"[A-Za-z0-9._~:/+-]+", client_id)):
        raise ValueError("client_id contains unsupported characters")
    profile["client_id"] = client_id
    profile["direct_capable"] = direct_capable
    profile["ready"] = direct_capable and bool(client_id)
    if profile.get("registration_url"):
        profile["registration_url"] = validate_remote_url(profile["registration_url"], "registration URL")
    if profile.get("portal_url"):
        profile["portal_url"] = validate_remote_url(profile["portal_url"], "portal URL")
    if profile.get("manual_help_url"):
        profile["manual_help_url"] = validate_remote_url(profile["manual_help_url"], "manual help URL")
    for field in ("manual_export_steps", "registration_steps"):
        steps = profile.get(field) or []
        if not isinstance(steps, list) or not all(isinstance(step, str) and step.strip() for step in steps):
            raise ValueError(f"{field} must contain non-empty strings")
        profile[field] = steps
    manual_import_mode = profile.get("manual_import_mode") or "files"
    if manual_import_mode not in {"files", "portal"}:
        raise ValueError("manual_import_mode must be files or portal")
    profile["manual_import_mode"] = manual_import_mode
    scopes = profile.get("scopes") or ["openid", "fhirUser", "launch/patient", "patient/*.rs"]
    profile["scopes"] = scopes if isinstance(scopes, list) else str(scopes).split()
    profile["resource_types"] = profile.get("resource_types") or DEFAULT_TYPES
    if not isinstance(profile["resource_types"], list) or not all(
        isinstance(value, str) and re.fullmatch(r"[A-Z][A-Za-z0-9]+", value)
        for value in profile["resource_types"]
    ):
        raise ValueError("resource_types must contain FHIR resource type names")
    return profile


def profile_paths():
    return sorted(CONNECTORS.glob("*.json")) if CONNECTORS.exists() else []


def load_profiles():
    profiles = []
    for path in profile_paths():
        if path.name.endswith(".example.json"):
            continue
        value = json.loads(path.read_text(encoding="utf-8-sig"))
        values = value if isinstance(value, list) else [value]
        profiles.extend(validate_profile(item, require_client_id=False) for item in values)
    keys = [profile["key"] for profile in profiles]
    if len(keys) != len(set(keys)):
        raise ValueError("connector profile keys must be unique")
    overrides = {}
    for path in sorted(LOCAL_CONNECTORS.glob("*.json")) if LOCAL_CONNECTORS.exists() else []:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
        if set(value) - {"key", "client_id"}:
            raise ValueError(f"local connector override has unsupported fields: {path}")
        key = validate_source(value.get("key", ""))
        overrides[key] = str(value.get("client_id") or "").strip()
    known = set(keys)
    unknown = sorted(set(overrides) - known)
    if unknown:
        raise ValueError("local connector override has unknown key: " + ", ".join(unknown))
    profiles = [validate_profile(dict(profile, client_id=overrides.get(profile["key"], profile["client_id"])),
                                 require_client_id=False) for profile in profiles]
    return profiles


def load_profile(key):
    key = validate_source(key)
    return next((profile for profile in load_profiles() if profile["key"] == key), None)


def configure_profile(key, client_id):
    key = validate_source(key)
    profile = next((item for item in load_profiles() if item["key"] == key), None)
    if not profile:
        raise ValueError(f"unknown connector {key!r}")
    if not profile["direct_capable"]:
        raise ValueError(f"{profile['name']} does not publish a configurable direct OAuth profile")
    candidate = validate_profile(dict(profile, client_id=client_id), require_client_id=True)
    LOCAL_CONNECTORS.mkdir(parents=True, exist_ok=True)
    destination = LOCAL_CONNECTORS / f"{key}.json"
    descriptor, temp_name = tempfile.mkstemp(prefix=key + ".", suffix=".tmp", dir=LOCAL_CONNECTORS)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump({"key": key, "client_id": candidate["client_id"]}, stream, indent=2, sort_keys=True)
            stream.write("\n")
        Path(temp_name).replace(destination)
    except Exception:
        Path(temp_name).unlink(missing_ok=True)
        raise
    return destination


def clear_profile_configuration(key):
    key = validate_source(key)
    if not any(item["key"] == key for item in load_profiles()):
        raise ValueError(f"unknown connector {key!r}")
    (LOCAL_CONNECTORS / f"{key}.json").unlink(missing_ok=True)


def request_json(url, *, method="GET", headers=None, data=None, timeout=60):
    request = urllib.request.Request(url, method=method, headers=headers or {}, data=data)
    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=timeout) as response:
            if response.status < 200 or response.status >= 300:
                raise RuntimeError(f"HTTP {response.status}")
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"network error: {exc.reason}") from exc


def discover(profile):
    base = profile["fhir_base"]
    config = request_json(base + "/.well-known/smart-configuration")
    authorize = validate_remote_url(config.get("authorization_endpoint", ""), "authorization endpoint", True)
    token = validate_remote_url(config.get("token_endpoint", ""), "token endpoint", True)
    return {"authorization_endpoint": authorize, "token_endpoint": token,
            "capabilities": config.get("capabilities") or []}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Never risk forwarding an OAuth bearer token through an HTTP redirect."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def authorization_url(profile, discovery, state, verifier):
    if not profile.get("client_id"):
        raise ValueError("connector needs a public client ID before it can connect")
    challenge = b64url(hashlib.sha256(verifier.encode("ascii")).digest())
    query = urllib.parse.urlencode({
        "response_type": "code",
        "client_id": profile["client_id"],
        "redirect_uri": profile["redirect_uri"],
        "scope": " ".join(profile["scopes"]),
        "aud": profile["fhir_base"],
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    })
    return discovery["authorization_endpoint"] + "?" + query


class OAuthResult:
    def __init__(self, state):
        self.state = state
        self.code = None
        self.error = None
        self.done = threading.Event()


def callback_handler(result):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            query = urllib.parse.parse_qs(parsed.query)
            good_path = parsed.path == "/oauth/callback"
            good_state = secrets.compare_digest((query.get("state") or [""])[0], result.state)
            if not good_path or not good_state:
                self.send_response(400)
                message = "Invalid OAuth callback. Return to Clippi-Health and try again."
            else:
                result.code = (query.get("code") or [None])[0]
                result.error = (query.get("error_description") or query.get("error") or [None])[0]
                self.send_response(200 if result.code and not result.error else 400)
                message = "Connection received. You can close this window and return to Clippi-Health."
                result.done.set()
            body = ("<!doctype html><meta charset=utf-8><title>Clippi-Health</title>"
                    f"<p>{message}</p>").encode()
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format, *_args):
            return

    return Handler


def receive_callback(profile, state, authorize_url, open_browser=True, timeout=600):
    redirect = urllib.parse.urlparse(profile["redirect_uri"])
    result = OAuthResult(state)
    server = ThreadingHTTPServer((redirect.hostname, redirect.port), callback_handler(result))
    server.timeout = 1
    if open_browser:
        webbrowser.open(authorize_url)
    else:
        print(authorize_url, flush=True)
    deadline = time.monotonic() + timeout
    try:
        while not result.done.is_set() and time.monotonic() < deadline:
            server.handle_request()
    finally:
        server.server_close()
    if not result.done.is_set():
        raise RuntimeError("OAuth login timed out")
    if result.error:
        raise RuntimeError(f"OAuth authorization failed: {result.error}")
    if not result.code:
        raise RuntimeError("OAuth callback did not contain an authorization code")
    return result.code


def exchange_code(profile, discovery, code, verifier):
    form = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": profile["redirect_uri"],
        "client_id": profile["client_id"],
        "code_verifier": verifier,
    }).encode()
    token = request_json(discovery["token_endpoint"], method="POST",
                         headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
                         data=form)
    if not token.get("access_token") or not token.get("patient"):
        raise RuntimeError("token response did not contain access_token and patient context")
    return token


def same_fhir_server(url, base):
    target, expected = urllib.parse.urlparse(url), urllib.parse.urlparse(base)
    return (target.scheme, target.hostname, target.port) == (expected.scheme, expected.hostname, expected.port) \
        and (target.path == expected.path or target.path.startswith(expected.path.rstrip("/") + "/"))


def bundle_resources(url, base, headers):
    seen_pages = set()
    while url:
        if url in seen_pages or not same_fhir_server(url, base):
            raise RuntimeError("FHIR pagination returned a loop or an external next link")
        seen_pages.add(url)
        bundle = request_json(url, headers=headers)
        if bundle.get("resourceType") != "Bundle":
            raise RuntimeError("FHIR search did not return a Bundle")
        for entry in bundle.get("entry") or []:
            resource = entry.get("resource")
            if isinstance(resource, dict) and resource.get("resourceType"):
                yield resource
        next_url = next((link.get("url") for link in bundle.get("link") or [] if link.get("relation") == "next"), None)
        url = urllib.parse.urljoin(base.rstrip("/") + "/", next_url) if next_url else None


def fetch_resources(profile, token):
    base = profile["fhir_base"]
    patient = urllib.parse.quote(str(token["patient"]), safe="")
    headers = {"Authorization": "Bearer " + token["access_token"], "Accept": "application/fhir+json"}
    everything = f"{base}/Patient/{patient}/$everything?" + urllib.parse.urlencode({"_count": 200})
    try:
        resources = list(bundle_resources(everything, base, headers))
    except RuntimeError:
        resources = [request_json(f"{base}/Patient/{patient}", headers=headers)]
        for resource_type in profile["resource_types"]:
            query = urllib.parse.urlencode({"patient": token["patient"], "_count": 200})
            try:
                resources.extend(bundle_resources(f"{base}/{resource_type}?{query}", base, headers))
            except RuntimeError as exc:
                print(f"skip {resource_type}: {exc}", file=sys.stderr, flush=True)
    unique = {}
    for resource in resources:
        identity = (resource.get("resourceType"), resource.get("id"))
        key = identity if all(identity) else (resource.get("resourceType"), json.dumps(resource, sort_keys=True))
        unique[key] = resource
    return list(unique.values())


def store_resources(profile, resources):
    folder = RAW_FHIR / profile["key"]
    folder.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(prefix="records.", suffix=".jsonl.tmp", dir=folder)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            for resource in resources:
                stream.write(json.dumps(resource, separators=(",", ":"), ensure_ascii=False) + "\n")
    except Exception:
        Path(temp_name).unlink(missing_ok=True)
        raise
    destination = folder / "records.jsonl"
    Path(temp_name).replace(destination)
    config = {
        "key": profile["key"],
        "org": profile["org"],
        "system": "SMART on FHIR",
        "method": "Direct public-client SMART OAuth with PKCE; records transferred from the health system to this device.",
        "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    (folder / "healthpilot-source.json").write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return destination


def import_file(path, source, org):
    source = validate_source(source)
    path = Path(path).expanduser().resolve()
    if not path.is_file() or path.suffix.lower() not in {".jsonl", ".ndjson"}:
        raise ValueError("import requires an existing .jsonl or .ndjson FHIR export")
    folder = RAW_FHIR / source
    folder.mkdir(parents=True, exist_ok=True)
    destination = folder / "records.jsonl"
    if path != destination.resolve():
        shutil.copy2(path, destination)
    config = {"key": source, "org": org, "system": "FHIR file import",
              "method": "FHIR NDJSON file supplied directly by the user.",
              "exported_at": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(timespec="seconds")}
    (folder / "healthpilot-source.json").write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return destination


def connect(profile, open_browser=True):
    discovery = discover(profile)
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    url = authorization_url(profile, discovery, state, verifier)
    print(f"Opening {profile['name']} sign-in in the system browser…", flush=True)
    code = receive_callback(profile, state, url, open_browser=open_browser)
    token = exchange_code(profile, discovery, code, verifier)
    resources = fetch_resources(profile, token)
    path = store_resources(profile, resources)
    print(f"Downloaded {len(resources)} FHIR resources to {path.relative_to(ROOT)}", flush=True)
    return path


def cmd_list(args):
    public_fields = ("key", "name", "org", "fhir_base", "ready", "direct_capable", "direct_note",
                     "registration_url", "registration_note", "registration_steps", "registration_label",
                     "registration_guide", "portal_url", "portal_label", "manual_help_url",
                     "manual_help_label", "manual_export_steps", "manual_title", "manual_import_mode",
                     "import_label")
    profiles = [{k: p[k] for k in public_fields if k in p} for p in load_profiles()]
    print(json.dumps(profiles, indent=2) if args.json else "\n".join(f"{p['key']}\t{p['name']}" for p in profiles))


def cmd_connect(args):
    profile = load_profile(args.key)
    if not profile:
        raise SystemExit(f"unknown connector {args.key!r}; run: ./hp smart list")
    if not profile["ready"]:
        raise SystemExit(f"{profile['name']} needs Clippi-Health's public client ID; configure it in the Sources tab")
    connect(profile, open_browser=not args.no_browser)
    if not args.no_build:
        subprocess.run([sys.executable, ROOT / "healthpilot.py"], cwd=ROOT, check=True)


def cmd_import(args):
    path = import_file(args.path, args.source, args.org)
    print(path.relative_to(ROOT))
    if not args.no_build:
        subprocess.run([sys.executable, ROOT / "healthpilot.py"], cwd=ROOT, check=True)


def cmd_configure(args):
    path = configure_profile(args.key, args.client_id)
    print(path.relative_to(ROOT))


def cmd_clear(args):
    clear_profile_configuration(args.key)
    print(f"cleared local client ID for {args.key}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    listing = sub.add_parser("list", help="list bundled direct connector profiles")
    listing.add_argument("--json", action="store_true"); listing.set_defaults(fn=cmd_list)
    auth = sub.add_parser("connect", help="run one local OAuth/FHIR import")
    auth.add_argument("key"); auth.add_argument("--no-browser", action="store_true")
    auth.add_argument("--no-build", action="store_true"); auth.set_defaults(fn=cmd_connect)
    local = sub.add_parser("import", help="import an existing FHIR NDJSON export")
    local.add_argument("path"); local.add_argument("--source", required=True); local.add_argument("--org", required=True)
    local.add_argument("--no-build", action="store_true"); local.set_defaults(fn=cmd_import)
    configure = sub.add_parser("configure", help="save a public client ID in the ignored local data folder")
    configure.add_argument("key"); configure.add_argument("client_id"); configure.set_defaults(fn=cmd_configure)
    clear = sub.add_parser("clear", help="remove a locally saved public client ID")
    clear.add_argument("key"); clear.set_defaults(fn=cmd_clear)
    args = parser.parse_args()
    try:
        args.fn(args)
    except (ValueError, RuntimeError, json.JSONDecodeError) as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
