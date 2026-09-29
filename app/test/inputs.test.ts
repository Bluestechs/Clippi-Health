import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import {
  EVENT_COLUMNS,
  LANES,
  parseCsv,
  readEvents,
  readNotes,
  toCsv,
  writeEvents,
  writeNotes,
  type EventRow,
} from "../main/inputs";
import type { Paths } from "../main/roots";
import { makePaths } from "./helpers";

let root: string;
let paths: Paths;

beforeEach(() => {
  root = mkdtempSync(join(tmpdir(), "hp-inputs-"));
  paths = makePaths(root);
});

afterEach(() => {
  rmSync(root, { recursive: true, force: true });
});

function event(overrides: Partial<EventRow> = {}): EventRow {
  return { date: "2020-01-01", lane: LANES[0], title: "t", detail: "", org: "", docs: "", replaces: "", ...overrides };
}

describe("parseCsv", () => {
  it("keeps commas inside quoted fields", () => {
    expect(parseCsv('a,"b,c",d\n')).toEqual([["a", "b,c", "d"]]);
  });

  it("unescapes doubled quotes", () => {
    expect(parseCsv('"he said ""hi""",plain\n')).toEqual([['he said "hi"', "plain"]]);
  });

  it("keeps newlines inside quoted fields", () => {
    expect(parseCsv('"line one\nline two",x\ny,z\n')).toEqual([["line one\nline two", "x"], ["y", "z"]]);
  });

  it("reads CRLF line endings", () => {
    expect(parseCsv("a,b\r\nc,d\r\n")).toEqual([["a", "b"], ["c", "d"]]);
  });

  it("does not invent a row for the trailing newline", () => {
    expect(parseCsv("a,b\n")).toHaveLength(1);
    expect(parseCsv("a,b")).toEqual([["a", "b"]]);
  });

  it("returns no rows for empty text", () => {
    expect(parseCsv("")).toEqual([]);
  });

  it("keeps empty fields", () => {
    expect(parseCsv("a,,c\n")).toEqual([["a", "", "c"]]);
  });
});

describe("toCsv", () => {
  it("quotes only fields that need it and ends with a newline", () => {
    expect(toCsv([["a", "b,c", 'say "hi"', "line\nbreak"]])).toBe('a,"b,c","say ""hi""","line\nbreak"\n');
  });

  it("round-trips awkward values", () => {
    const rows = [
      [...EVENT_COLUMNS],
      ["2021-05-04", LANES[1], "Op, right side", 'note with "quotes"', "Org\nName", "raw/other/x.pdf", ""],
      ["2021-06-01", LANES[3], "MRI", "", "", "", "2021-05-04"],
    ];
    expect(parseCsv(toCsv(rows))).toEqual(rows);
  });
});

describe("readEvents", () => {
  it("returns nothing when the file is absent", () => {
    expect(readEvents(paths)).toEqual([]);
  });

  it("maps columns by header name, not position", () => {
    writeFileSync(paths.curatedEvents, "title,date,lane\nBiopsy,2019-03-02,Imaging\n");
    expect(readEvents(paths)[0]).toMatchObject({ date: "2019-03-02", lane: "Imaging", title: "Biopsy" });
  });

  it("fills in columns the file does not have", () => {
    writeFileSync(paths.curatedEvents, "date,title\n2019-03-02,Biopsy\n");
    const [row] = readEvents(paths);
    expect(row).toEqual({ date: "2019-03-02", lane: "", title: "Biopsy", detail: "", org: "", docs: "", replaces: "" });
  });

  it("tolerates short rows and blank lines", () => {
    writeFileSync(paths.curatedEvents, "date,lane,title,detail\n\n2019-03-02,Imaging\n   \n2020-01-01,Imaging,X,d\n");
    const rows = readEvents(paths);
    expect(rows).toHaveLength(2);
    expect(rows[0]).toMatchObject({ date: "2019-03-02", lane: "Imaging", title: "", detail: "" });
    expect(rows[1]).toMatchObject({ title: "X", detail: "d" });
  });

  it("reads quoted values written by a spreadsheet", () => {
    writeFileSync(paths.curatedEvents, 'date,lane,title\r\n2019-03-02,Imaging,"MRI, left knee"\r\n');
    expect(readEvents(paths)[0]?.title).toBe("MRI, left knee");
  });
});

describe("writeEvents", () => {
  it("always writes the canonical header in order", () => {
    writeEvents(paths, [event()]);
    expect(readFileSync(paths.curatedEvents, "utf8").split("\n")[0]).toBe(EVENT_COLUMNS.join(","));
  });

  it("rewrites a file whose header was in a different order into canonical form", () => {
    writeFileSync(paths.curatedEvents, "title,date,lane\nBiopsy,2019-03-02,Imaging\n");
    writeEvents(paths, readEvents(paths));
    expect(readFileSync(paths.curatedEvents, "utf8")).toBe(
      "date,lane,title,detail,org,docs,replaces\n2019-03-02,Imaging,Biopsy,,,,\n",
    );
  });

  it("survives a write/read round trip with quoting-sensitive values", () => {
    const rows = [event({ title: "Op, right", detail: 'said "yes"\nnext line' })];
    writeEvents(paths, rows);
    expect(readEvents(paths)).toEqual(rows);
  });

  it("writes a header-only file for no events", () => {
    writeEvents(paths, []);
    expect(readFileSync(paths.curatedEvents, "utf8")).toBe("date,lane,title,detail,org,docs,replaces\n");
    expect(readEvents(paths)).toEqual([]);
  });
});

describe("notes", () => {
  it("returns an empty string when the file is absent", () => {
    expect(readNotes(paths)).toBe("");
  });

  it("ends the file with exactly one newline", () => {
    writeNotes(paths, "## Heading\nbody");
    expect(readFileSync(paths.notes, "utf8")).toBe("## Heading\nbody\n");
    writeNotes(paths, "## Heading\nbody\n");
    expect(readFileSync(paths.notes, "utf8")).toBe("## Heading\nbody\n");
    expect(readNotes(paths)).toBe("## Heading\nbody\n");
  });
});
