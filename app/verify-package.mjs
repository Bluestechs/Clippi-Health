import assert from "node:assert/strict";
import { closeSync, openSync, readSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const directory = resolve(process.argv[2]);
assert.ok(["win32", "linux"].includes(process.platform), "Evaluation package verification requires Windows or Linux");
assert.ok(["x64", "arm64"].includes(process.arch), "Unsupported evaluation architecture");
const executable = join(directory, process.platform === "win32" ? "Clippi-Health.exe" : "Clippi-Health");
const runtime = join(directory, "resources", "clippi-runtime");

function checkArchitecture(file) {
  const descriptor = openSync(file, "r");
  const header = Buffer.alloc(64);
  try {
    assert.equal(readSync(descriptor, header, 0, header.length, 0), header.length);
    if (process.platform === "win32") {
      assert.equal(header.toString("ascii", 0, 2), "MZ", `Not a PE executable: ${file}`);
      const pe = Buffer.alloc(6);
      assert.equal(readSync(descriptor, pe, 0, pe.length, header.readUInt32LE(60)), pe.length);
      assert.equal(pe.toString("ascii", 0, 4), "PE\0\0");
      assert.equal(pe.readUInt16LE(4), process.arch === "arm64" ? 0xaa64 : 0x8664, `Wrong PE architecture: ${file}`);
    } else {
      assert.equal(header.toString("ascii", 0, 4), "\x7fELF", `Not an ELF executable: ${file}`);
      assert.equal(header[4], 2, "Expected a 64-bit ELF executable");
      assert.equal(header[5], 1, "Expected a little-endian ELF executable");
      assert.equal(header.readUInt16LE(18), process.arch === "arm64" ? 183 : 62, `Wrong ELF architecture: ${file}`);
    }
  } finally {
    closeSync(descriptor);
  }
  console.log(`Verified native ${process.arch} executable: ${file}`);
}

function run(command, args) {
  const result = spawnSync(command, args, { stdio: "inherit", timeout: 300_000 });
  if (result.error) throw result.error;
  assert.equal(result.status, 0, `${command} failed (${result.status}, signal ${result.signal})`);
}

checkArchitecture(executable);
checkArchitecture(join(runtime, process.platform === "win32" ? "clippi-runtime.exe" : "clippi-runtime"));
if (process.platform === "win32") checkArchitecture(join(runtime, "_internal", "python312.dll"));
run(process.execPath, [fileURLToPath(new URL("verify-runtime.mjs", import.meta.url)), runtime]);
if (process.platform === "linux") run("xvfb-run", ["-a", executable, "--smoke"]);
else run(executable, ["--smoke"]);
console.log(`Packaged ${process.platform}/${process.arch} application passed native-engine and fictional desktop smoke checks.`);
