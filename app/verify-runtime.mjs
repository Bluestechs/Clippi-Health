import { existsSync, mkdtempSync, readFileSync, rmSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { join, resolve } from "node:path";
import { tmpdir } from "node:os";

const executable = resolve("runtime", "clippi-runtime", process.platform === "win32" ? "clippi-runtime.exe" : "clippi-runtime");
if (!existsSync(executable)) throw new Error(`Bundled runtime was not found at ${executable}`);

const root = mkdtempSync(join(tmpdir(), "clippi-health-runtime-"));
const env = { ...process.env, CLIPPI_HEALTH_ROOT: root };

function run(args) {
  const result = spawnSync(executable, args, { env, encoding: "utf8" });
  if (result.status !== 0) {
    throw new Error(`${args.join(" ")} failed (${result.status}): ${result.stderr || result.stdout}`);
  }
  return result.stdout;
}

try {
  run(["build"]);
  for (const path of ["clippi-health.json", "data/health.db", "dashboard.html"]) {
    if (!existsSync(join(root, path))) throw new Error(`Runtime did not create ${path}`);
  }
  const summary = JSON.parse(run(["query", "--json", "summary"]));
  if (!Array.isArray(summary.sources) || typeof summary.labs !== "number" || typeof summary.built_at !== "string") {
    throw new Error("Runtime summary shape is invalid");
  }
  const connectors = JSON.parse(run(["smart", "list", "--json"]));
  if (!Array.isArray(connectors) || !connectors.some((item) => item.key === "fhir-bjc-mychart")) {
    throw new Error("Runtime connector catalog is missing BJC MyChart");
  }
  const marker = JSON.parse(readFileSync(join(root, "clippi-health.json"), "utf8"));
  if (marker.format !== "clippi-health-record-store") throw new Error("Runtime root marker is invalid");
  console.log("Bundled runtime passed clean-store build, query, and connector checks.");
} finally {
  rmSync(root, { recursive: true, force: true });
}
