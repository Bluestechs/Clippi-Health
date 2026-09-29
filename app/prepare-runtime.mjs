import { existsSync, rmSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { delimiter, join, resolve } from "node:path";

function findPython() {
  if (process.env.PYTHON) return process.env.PYTHON;
  const names = process.platform === "win32" ? ["python.exe", "python3.exe"] : ["python3", "python"];
  for (const dir of (process.env.PATH ?? "").split(delimiter)) {
    for (const name of names) {
      const candidate = join(dir, name);
      if (existsSync(candidate)) return candidate;
    }
  }
  throw new Error("Python was not found. Release builders need Python plus packaging/requirements-build.txt.");
}

const root = resolve("..");
const out = resolve("runtime");
const work = resolve(".runtime-build");
rmSync(out, { recursive: true, force: true });
rmSync(work, { recursive: true, force: true });
const result = spawnSync(findPython(), [
  "-m", "PyInstaller",
  "--noconfirm",
  "--clean",
  "--distpath", out,
  "--workpath", work,
  resolve(root, "packaging", "runtime.spec"),
], {
  cwd: root,
  stdio: "inherit",
  env: { ...process.env, PYINSTALLER_CONFIG_DIR: join(work, "config") },
});
if (result.status !== 0) process.exit(result.status ?? 1);
