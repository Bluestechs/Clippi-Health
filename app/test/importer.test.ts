import { existsSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, rmSync, statSync, utimesSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { applyImport, planImport } from "../main/importer";
import type { Paths } from "../main/roots";
import { makePaths, writeZip } from "./helpers";

let root: string;
let incoming: string;
let paths: Paths;

beforeEach(() => {
  root = mkdtempSync(join(tmpdir(), "hp-import-root-"));
  incoming = mkdtempSync(join(tmpdir(), "hp-import-src-"));
  paths = makePaths(root);
  mkdirSync(paths.rawApple, { recursive: true });
  mkdirSync(paths.rawOther, { recursive: true });
});

afterEach(() => {
  for (const dir of [root, incoming]) rmSync(dir, { recursive: true, force: true });
});

function appleZip(name: string): string {
  return writeZip(join(incoming, name), [
    { name: "apple_health_export/export.xml", data: "<HealthData/>" },
    { name: "apple_health_export/export_cda.xml", data: "<ClinicalDocument/>" },
  ]);
}

describe("planImport", () => {
  it("classifies an Apple Health export as apple and aims it at raw/apple", () => {
    const plan = planImport(paths, [appleZip("export.zip")]);
    expect(plan.items).toHaveLength(1);
    expect(plan.items[0]).toMatchObject({ kind: "apple", dest: join(paths.rawApple, "export.zip") });
    expect(plan.items[0]?.note).toContain("Apple Health export");
  });

  it("classifies a document zip as a local archive", () => {
    const path = writeZip(join(incoming, "records.zip"), [{ name: "readme.txt", data: "hi" }]);
    const plan = planImport(paths, [path]);
    expect(plan.items[0]).toMatchObject({
      kind: "archive",
      dest: join(paths.rawImports, "records.zip"),
    });
  });

  it("classifies a MyChart IHE XDM zip as a portal record", () => {
    const path = writeZip(join(incoming, "mychart-record.zip"), [
      { name: "BJC/IHE_XDM/SUBSET01/DOC0001.XML", data: "<ClinicalDocument/>" },
    ]);
    const plan = planImport(paths, [path]);
    expect(plan.items[0]).toMatchObject({
      kind: "portal",
      dest: join(paths.rawOther, "mychart-record.zip"),
    });
    expect(plan.items[0]?.note).toContain("MyChart C-CDA record ZIP");
  });

  it("classifies a Gmail Takeout MBOX zip as a local archive", () => {
    const path = writeZip(join(incoming, "takeout.zip"), [{ name: "Takeout/Mail/Health.mbox", data: "From sender@example.test\n" }]);
    expect(planImport(paths, [path]).items[0]).toMatchObject({
      kind: "archive",
      dest: join(paths.rawImports, "takeout.zip"),
    });
  });

  it("rejects an Outlook PST-only zip with EML export guidance", () => {
    const path = writeZip(join(incoming, "outlook.zip"), [{ name: "mail/export.pst", data: "pst" }]);
    const plan = planImport(paths, [path]);
    expect(plan.items).toEqual([]);
    expect(plan.skipped[0]).toContain("Export messages as .eml files");
  });

  it("rejects a zip without a supported member", () => {
    const path = writeZip(join(incoming, "unknown.zip"), [{ name: "data.bin", data: "hi" }]);
    const plan = planImport(paths, [path]);
    expect(plan.items).toEqual([]);
    expect(plan.skipped[0]).toContain("no supported email or document files");
  });

  it("treats a non-zip file as a file", () => {
    const path = join(incoming, "letter.pdf");
    writeFileSync(path, "%PDF-1.4\n");
    expect(planImport(paths, [path]).items[0]).toMatchObject({ kind: "file", dest: join(paths.rawOther, "letter.pdf") });
  });

  it("labels a folder holding IHE_XDM as a C-CDA record download", () => {
    const folder = join(incoming, "record-download");
    mkdirSync(join(folder, "IHE_XDM"), { recursive: true });
    writeFileSync(join(folder, "IHE_XDM", "doc.xml"), "<ClinicalDocument/>");
    expect(planImport(paths, [folder]).items[0]).toMatchObject({
      kind: "folder",
      note: "C-CDA record download",
      dest: join(paths.rawOther, "record-download"),
    });
  });

  it("labels any other folder plainly", () => {
    const folder = join(incoming, "scans");
    mkdirSync(folder);
    expect(planImport(paths, [folder]).items[0]).toMatchObject({ kind: "folder", note: "folder" });
  });

  it("skips paths that do not exist and keeps planning the rest", () => {
    const missing = join(incoming, "gone.zip");
    const plan = planImport(paths, [missing, appleZip("export.zip")]);
    expect(plan.skipped).toEqual([`${missing} does not exist`]);
    expect(plan.items).toHaveLength(1);
  });

  it("reports the Apple export already in raw/apple as replaced", () => {
    writeFileSync(join(paths.rawApple, "old.zip"), "old");
    const plan = planImport(paths, [appleZip("export.zip")]);
    expect(plan.replaced).toEqual([join(paths.rawApple, "old.zip")]);
  });

  it("does not report a replacement when no Apple export is incoming", () => {
    writeFileSync(join(paths.rawApple, "old.zip"), "old");
    const path = join(incoming, "letter.pdf");
    writeFileSync(path, "%PDF-1.4\n");
    expect(planImport(paths, [path]).replaced).toEqual([]);
  });

  it("does not count a same-named export as something to move aside", () => {
    writeFileSync(join(paths.rawApple, "export.zip"), "old");
    expect(planImport(paths, [appleZip("export.zip")]).replaced).toEqual([]);
  });
});

describe("applyImport", () => {
  it("copies the new export in and keeps the old one in raw/_previous", () => {
    writeFileSync(join(paths.rawApple, "old.zip"), "old");
    const plan = planImport(paths, [appleZip("export.zip")]);
    applyImport(paths, plan, true);

    expect(existsSync(join(paths.rawApple, "old.zip"))).toBe(false);
    expect(readdirSync(paths.rawApple)).toEqual(["export.zip"]);
    const kept = readdirSync(paths.rawPrevious);
    expect(kept).toHaveLength(1);
    expect(kept[0]).toMatch(/^old-\d{8}-\d{6}\.zip$/);
    expect(readFileSync(join(paths.rawPrevious, kept[0] ?? ""), "utf8")).toBe("old");
  });

  it("leaves the old export alone when the user declined the replacement", () => {
    writeFileSync(join(paths.rawApple, "old.zip"), "old");
    applyImport(paths, planImport(paths, [appleZip("export.zip")]), false);
    expect(readdirSync(paths.rawApple).sort()).toEqual(["export.zip", "old.zip"]);
    expect(existsSync(paths.rawPrevious)).toBe(false);
  });

  it("creates raw/apple and raw/other when the root is bare", () => {
    rmSync(paths.raw, { recursive: true, force: true });
    const path = join(incoming, "letter.pdf");
    writeFileSync(path, "%PDF-1.4\n");
    const log = applyImport(paths, planImport(paths, [path]), true);
    expect(existsSync(join(paths.rawOther, "letter.pdf"))).toBe(true);
    expect(log).toEqual(["file → raw/other/letter.pdf"]);
  });

  it("copies a local archive into raw/imports", () => {
    const source = writeZip(join(incoming, "messages.zip"), [{ name: "mail/one.eml", data: "Subject: Test\n\nBody" }]);
    const log = applyImport(paths, planImport(paths, [source]), true);
    expect(readFileSync(join(paths.rawImports, "messages.zip"))).toEqual(readFileSync(source));
    expect(log).toEqual(["Local email/document archive — parsed offline on the next build → raw/imports/messages.zip"]);
  });

  it("replaces an existing destination folder rather than merging into it", () => {
    const stale = join(paths.rawOther, "record-download");
    mkdirSync(stale, { recursive: true });
    writeFileSync(join(stale, "stale.xml"), "old");

    const folder = join(incoming, "record-download");
    mkdirSync(join(folder, "IHE_XDM"), { recursive: true });
    writeFileSync(join(folder, "IHE_XDM", "doc.xml"), "<ClinicalDocument/>");

    applyImport(paths, planImport(paths, [folder]), true);
    expect(readdirSync(stale)).toEqual(["IHE_XDM"]);
    expect(readFileSync(join(stale, "IHE_XDM", "doc.xml"), "utf8")).toBe("<ClinicalDocument/>");
  });

  it("preserves the modification time of a copied file", () => {
    // the Python build caches Apple device data by zip size + mtime, so a copy must not look newer
    const source = appleZip("export.zip");
    const when = new Date("2023-07-04T12:34:56.000Z");
    utimesSync(source, when, when);
    applyImport(paths, planImport(paths, [source]), true);
    const dest = statSync(join(paths.rawApple, "export.zip"));
    expect(dest.mtime.getTime()).toBe(when.getTime());
    expect(dest.size).toBe(statSync(source).size);
  });

  it("logs one root-relative line per action", () => {
    writeFileSync(join(paths.rawApple, "old.zip"), "old");
    const folder = join(incoming, "scans");
    mkdirSync(folder);
    const log = applyImport(paths, planImport(paths, [appleZip("export.zip"), folder]), true);
    expect(log).toHaveLength(3);
    expect(log[0]).toMatch(/^kept previous Apple export → raw\/_previous\/old-\d{8}-\d{6}\.zip$/);
    expect(log.slice(1)).toEqual([
      "Apple Health export — device data is parsed on the next build (~30 s) → raw/apple/export.zip",
      "folder → raw/other/scans",
    ]);
  });
});
