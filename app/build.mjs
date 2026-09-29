// Bundles the three Electron entry points. No bundler config files, no watch mode:
// `npm start` runs this once and launches Electron.
import { build } from "esbuild";
import { cp, mkdir, rm } from "node:fs/promises";

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
