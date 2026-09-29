// The hand-edited inputs the build reads: curated_events.csv (timeline rows) and
// case_study_notes.md (appended verbatim to the case study). Formats must stay exactly as the
// Python builder expects them — see data/DATA_DICTIONARY.md § 8.
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import type { Paths } from "./roots";

export const EVENT_COLUMNS = ["date", "lane", "title", "detail", "org", "docs", "replaces"] as const;

/** Lane vocabulary from healthpilot.py LANES; the builder drops rows with an unknown lane. */
export const LANES = [
  "Diagnoses",
  "Surgery & procedures",
  "Hospital & ED",
  "Imaging",
  "Pathology & reports",
  "Milestones",
] as const;

export function parseCsv(text: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let field = "";
  let quoted = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (quoted) {
      if (c === '"' && text[i + 1] === '"') {
        field += '"';
        i++;
      } else if (c === '"') {
        quoted = false;
      } else {
        field += c;
      }
      continue;
    }
    if (c === '"') quoted = true;
    else if (c === ",") {
      row.push(field);
      field = "";
    } else if (c === "\n" || c === "\r") {
      if (c === "\r" && text[i + 1] === "\n") i++;
      row.push(field);
      rows.push(row);
      row = [];
      field = "";
    } else field += c;
  }
  if (field !== "" || row.length) {
    row.push(field);
    rows.push(row);
  }
  return rows;
}

export function toCsv(rows: string[][]): string {
  return rows
    .map((row) => row.map((cell) => (/[",\n\r]/.test(cell) ? `"${cell.replace(/"/g, '""')}"` : cell)).join(","))
    .join("\n") + "\n";
}

export type EventRow = Record<(typeof EVENT_COLUMNS)[number], string>;

export function readEvents(paths: Paths): EventRow[] {
  if (!existsSync(paths.curatedEvents)) return [];
  const rows = parseCsv(readFileSync(paths.curatedEvents, "utf8")).filter((r) => r.some((c) => c.trim() !== ""));
  const header = rows.shift() ?? [];
  return rows.map((row) => {
    const event = {} as EventRow;
    for (const column of EVENT_COLUMNS) {
      const at = header.indexOf(column);
      event[column] = (at >= 0 ? row[at] : "") ?? "";
    }
    return event;
  });
}

export function writeEvents(paths: Paths, events: EventRow[]): void {
  const rows = [[...EVENT_COLUMNS], ...events.map((event) => EVENT_COLUMNS.map((column) => event[column] ?? ""))];
  writeFileSync(paths.curatedEvents, toCsv(rows));
}

export function readNotes(paths: Paths): string {
  return existsSync(paths.notes) ? readFileSync(paths.notes, "utf8") : "";
}

export function writeNotes(paths: Paths, text: string): void {
  writeFileSync(paths.notes, text.endsWith("\n") ? text : text + "\n");
}
