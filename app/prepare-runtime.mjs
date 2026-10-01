import { existsSync, mkdirSync, rmSync } from "node:fs";
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
if (process.platform === "linux") {
  // Freeze against glibc 2.35, not the (potentially newer) release runner's Python.
  const engine = process.env.CONTAINER_ENGINE ?? "docker";
  const image = "clippi-health-runtime-builder:ubuntu22.04";
  function container(args) {
    const result = spawnSync(engine, args, { stdio: "inherit" });
    if (result.error) throw result.error;
    if (result.status !== 0) process.exit(result.status ?? 1);
  }
  container(["build", "--tag", image, "--file", resolve(root, "packaging", "Dockerfile.linux-runtime"), resolve(root, "packaging")]);
  mkdirSync(out, { recursive: true });
  mkdirSync(work, { recursive: true });
  const mounts = [
    "run", "--rm", "--user", `${process.getuid()}:${process.getgid()}`,
    "--mount", `type=bind,src=${root},dst=/source,readonly`,
    "--mount", `type=bind,src=${out},dst=/source/app/runtime`,
    "--mount", `type=bind,src=${work},dst=/source/app/.runtime-build`,
    "--workdir", "/source",
    "--env", "PYINSTALLER_CONFIG_DIR=/source/app/.runtime-build/config",
    image,
  ];
  container([...mounts, "python3", "-m", "PyInstaller", "--noconfirm", "--clean",
    "--distpath", "/source/app/runtime", "--workpath", "/source/app/.runtime-build",
    "/source/packaging/runtime.spec"]);
  // A smoke run on the build host alone cannot prove older-libc compatibility.
  container([...mounts, "node", "/source/app/verify-runtime.mjs", "/source/app/runtime/clippi-runtime"]);
} else {
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
}
