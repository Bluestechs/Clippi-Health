import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { zipEntryNames } from "../main/zip";
import { writeZip, writeZip64 } from "./helpers";

let dir: string;

beforeAll(() => {
  dir = mkdtempSync(join(tmpdir(), "hp-zip-"));
});

afterAll(() => {
  rmSync(dir, { recursive: true, force: true });
});

describe("zipEntryNames", () => {
  it("lists the entries of a plain archive", () => {
    const path = writeZip(join(dir, "plain.zip"), [
      { name: "apple_health_export/export.xml", data: "<HealthData/>" },
      { name: "apple_health_export/export_cda.xml", data: "<ClinicalDocument/>" },
    ]);
    expect(zipEntryNames(path)).toEqual([
      "apple_health_export/export.xml",
      "apple_health_export/export_cda.xml",
    ]);
  });

  it("lists entries of an archive written by the system zip tool", () => {
    if (!existsSync("/usr/bin/zip")) return; // optional cross-check; the hand-written fixtures cover it
    const source = join(dir, "real");
    mkdirSync(join(source, "apple_health_export"), { recursive: true });
    writeFileSync(join(source, "apple_health_export", "export.xml"), "<HealthData/>\n");
    const path = join(dir, "real.zip");
    execFileSync("/usr/bin/zip", ["-qr", path, "apple_health_export"], { cwd: source });
    expect(zipEntryNames(path)).toContain("apple_health_export/export.xml");
  });

  it("returns an empty list for an archive with no entries", () => {
    expect(zipEntryNames(writeZip(join(dir, "empty.zip"), []))).toEqual([]);
  });

  it("reads entry names through the ZIP64 end-of-central-directory record", () => {
    const path = writeZip64(join(dir, "big.zip"), [
      { name: "apple_health_export/export.xml", data: "<HealthData/>" },
      { name: "apple_health_export/workout-routes/route.gpx", data: "<gpx/>" },
    ]);
    const tail = readFileSync(path);
    // the 32-bit record carries only sentinels, so the names can only come from the ZIP64 record
    expect(tail.readUInt16LE(tail.length - 12)).toBe(0xffff);
    expect(tail.readUInt32LE(tail.length - 6)).toBe(0xffffffff);
    expect(zipEntryNames(path)).toEqual([
      "apple_health_export/export.xml",
      "apple_health_export/workout-routes/route.gpx",
    ]);
  });

  it("returns null for a file that is not a ZIP", () => {
    const path = join(dir, "notes.txt");
    writeFileSync(path, "date,lane,title\n");
    expect(zipEntryNames(path)).toBeNull();
  });

  it("returns null for an empty file and for a missing path", () => {
    const path = join(dir, "zero.zip");
    writeFileSync(path, "");
    expect(zipEntryNames(path)).toBeNull();
    expect(zipEntryNames(join(dir, "absent.zip"))).toBeNull();
  });

  it("returns null when the archive tail is truncated", () => {
    const whole = writeZip(join(dir, "whole.zip"), [{ name: "a.txt", data: "a" }]);
    const path = join(dir, "cut.zip");
    writeFileSync(path, readFileSync(whole).subarray(0, 40));
    expect(zipEntryNames(path)).toBeNull();
  });
});
