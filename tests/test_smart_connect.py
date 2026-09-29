"""Local SMART connector validation tests; all records and endpoints are synthetic."""
import json
import tempfile
import unittest
import urllib.parse
from pathlib import Path
from unittest.mock import patch

import smart_connect


def raw_profile(**changes):
    value = {
        "key": "fhir-example",
        "name": "Example Health",
        "org": "Example Health",
        "fhir_base": "https://records.example.test/fhir/r4",
        "client_id": "public-example",
        "redirect_uri": "http://127.0.0.1:8765/oauth/callback",
    }
    value.update(changes)
    return value


def profile(**changes):
    return smart_connect.validate_profile(raw_profile(**changes))


class SmartConnectorTests(unittest.TestCase):
    def test_profile_requires_public_loopback_oauth(self):
        self.assertEqual(profile()["key"], "fhir-example")
        for change in [
            {"key": "example"},
            {"fhir_base": "http://records.example.test/fhir"},
            {"redirect_uri": "https://healthpilot.example/callback"},
            {"client_secret": "must-not-be-shipped"},
        ]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                profile(**change)

    def test_catalog_profile_can_wait_for_client_id(self):
        value = smart_connect.validate_profile(raw_profile(client_id=""), require_client_id=False)
        self.assertFalse(value["ready"])
        with self.assertRaises(ValueError):
            smart_connect.validate_profile(value)

    def test_authorization_uses_pkce_and_state(self):
        value = profile()
        url = smart_connect.authorization_url(value, {"authorization_endpoint": "https://records.example.test/auth"},
                                                  "expected-state", "verifier")
        query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        self.assertEqual(query["state"], ["expected-state"])
        self.assertEqual(query["code_challenge_method"], ["S256"])
        self.assertNotIn("client_secret", query)
        self.assertEqual(query["redirect_uri"], [value["redirect_uri"]])

    def test_pagination_refuses_external_next_link(self):
        pages = [{"resourceType": "Bundle", "entry": [],
                  "link": [{"relation": "next", "url": "https://attacker.example/steal"}]}]
        with patch.object(smart_connect, "request_json", side_effect=pages):
            with self.assertRaises(RuntimeError):
                list(smart_connect.bundle_resources("https://records.example.test/fhir/r4/Observation?patient=p1",
                                                    "https://records.example.test/fhir/r4", {}))

    def test_import_writes_only_generic_local_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            incoming = root / "incoming.jsonl"
            incoming.write_text('{"resourceType":"Patient","id":"synthetic"}\n')
            with patch.multiple(smart_connect, ROOT=root, RAW_FHIR=root / "raw" / "fhir"):
                output = smart_connect.import_file(incoming, "fhir-example", "Example Health")
            config = json.loads((output.parent / "healthpilot-source.json").read_text())
            self.assertEqual((config["key"], config["system"]), ("fhir-example", "FHIR file import"))
            self.assertNotIn("token", json.dumps(config).lower())

    def test_store_replaces_export_without_persisting_tokens(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            value = profile()
            resources = [{"resourceType": "Patient", "id": "synthetic"}]
            with patch.multiple(smart_connect, ROOT=root, RAW_FHIR=root / "raw" / "fhir"):
                output = smart_connect.store_resources(value, resources)
            self.assertEqual(json.loads(output.read_text())["id"], "synthetic")
            combined = output.read_text() + (output.parent / "healthpilot-source.json").read_text()
            self.assertNotIn("access_token", combined)

    def test_local_client_id_configuration_merges_with_bundled_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = root / "connectors"
            local = root / "raw" / "connectors"
            catalog.mkdir(parents=True)
            bundled = raw_profile(client_id="")
            catalog.joinpath("example.json").write_text(json.dumps(bundled))
            with patch.multiple(smart_connect, CONNECTORS=catalog, LOCAL_CONNECTORS=local):
                self.assertFalse(smart_connect.load_profile("fhir-example")["ready"])
                saved = smart_connect.configure_profile("fhir-example", "public-production-id")
                self.assertTrue(saved.is_file())
                configured = smart_connect.load_profile("fhir-example")
                self.assertTrue(configured["ready"])
                self.assertEqual(configured["client_id"], "public-production-id")
                smart_connect.clear_profile_configuration("fhir-example")
                self.assertFalse(smart_connect.load_profile("fhir-example")["ready"])


if __name__ == "__main__":
    unittest.main()
