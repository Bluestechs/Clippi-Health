// Bundles the three Electron entry points. No bundler config files, no watch mode:
// `npm start` runs this once and launches Electron.
import { build } from "esbuild";
import { cp, mkdir, rm, writeFile } from "node:fs/promises";
import { spawnSync } from "node:child_process";

await rm("dist", { recursive: true, force: true });
await mkdir("dist", { recursive: true });

const common = { bundle: true, sourcemap: true, logLevel: "info" };

await build({
  ...common,
  entryPoints: ["main/index.ts"],
  outfile: "dist/main.js",
  platform: "node",
  format: "cjs",
  target: "node22",
  external: ["electron"],
});

await build({
  ...common,
  entryPoints: ["preload/index.ts"],
  outfile: "dist/preload.js",
  platform: "node",
  format: "cjs",
  target: "node22",
  external: ["electron"],
});

await build({
  ...common,
  entryPoints: ["renderer/app.ts"],
  outfile: "dist/renderer.js",
  platform: "browser",
  format: "iife",
  target: "chrome120",
});

await cp("renderer/index.html", "dist/index.html");
await cp("renderer/styles.css", "dist/styles.css");
await cp("../assets/clippi-health-logo.png", "dist/logo.png");
await cp("../LICENSE", "dist/LICENSE");
await cp("../THIRD_PARTY_NOTICES.md", "dist/THIRD_PARTY_NOTICES.md");
await cp("../vendor/LICENSE.plotly.js.txt", "dist/LICENSE.plotly.js.txt");
await cp("../vendor/LICENSE.python.txt", "dist/LICENSE.python.txt");
await cp("../vendor/LICENSE.pyinstaller.txt", "dist/LICENSE.pyinstaller.txt");
await cp("../vendor/LICENSE.pypdf.txt", "dist/LICENSE.pypdf.txt");

const guide = spawnSync(process.env.PYTHON ?? (process.platform === "win32" ? "python" : "python3"), ["-c", `
from pathlib import Path
import sys
sys.path.insert(0, str(Path("../scripts").resolve()))
from md2pdf import md_to_html
print(md_to_html(Path("../docs/EPIC_REGISTRATION.md").read_text(encoding="utf-8"), "Your Epic registration · Clippi-Health", render_links=True))
`], { encoding: "utf8", env: { ...process.env, PYTHONUTF8: "1" } });
if (guide.error) throw guide.error;
if (guide.status !== 0) throw new Error(`Registration checklist generation failed: ${guide.stderr}`);
const policy = `<meta name="viewport" content="width=device-width, initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'">`;
const layout = `<style>body{box-sizing:border-box;max-width:76ch;margin:auto;padding:24px;background:#f9f9f7;color:#242424;font:16px/1.6 system-ui,sans-serif;overflow-wrap:anywhere}h1{font-size:1.5rem}h2{font-size:1.125rem}code{font-size:.9em}a{color:#1559a3}</style>`;
await writeFile("dist/epic-registration.html", guide.stdout.replace("<html>", '<html lang="en">').replace("<head>", "<head>" + policy).replace("</head>", layout + "</head>").replace("<body>", "<body><main>").replace("</body>", "</main></body>"));
