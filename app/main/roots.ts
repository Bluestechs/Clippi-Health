// Where the data lives. The app keeps the repo layout (raw/, data/, hand-edited inputs) so the
// `hp` CLI, SQL and anything else pointed at the folder keep working.
import { app } from "electron";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";

export type Paths = {
  root: string;
  raw: string;
  rawApple: string;
  rawImports: string;
  rawOther: string;
  rawPrevious: string;
  data: string;
  db: string;
  dashboard: string;
  curatedEvents: string;
  notes: string;
  topics: string;
  builder: string;
  cli: string;
  smartConnector: string;
};

/** The folder this build was shipped from: app/ sits inside the Clippi-Health folder. */
export function defaultRoot(): string {
  return resolve(app.getAppPath(), "..");
}

const CONFIG_FILE = "config.json";

/** A folder is a Clippi-Health root when the reference builder is there. */
export function isRoot(dir: string): boolean {
  return existsSync(join(dir, "healthpilot.py"));
}

export function getRoot(): string {
  try {
    const saved = JSON.parse(readFileSync(join(app.getPath("userData"), CONFIG_FILE), "utf8")) as { root?: string };
    if (saved.root && existsSync(saved.root)) return saved.root;
  } catch {
    // no config yet, or unreadable — fall back to the folder we ship in
  }
  return defaultRoot();
}

export function setRoot(root: string): void {
  mkdirSync(app.getPath("userData"), { recursive: true });
  writeFileSync(join(app.getPath("userData"), CONFIG_FILE), JSON.stringify({ root }, null, 2) + "\n");
}

export function paths(root = getRoot()): Paths {
  return {
    root,
    raw: join(root, "raw"),
    rawApple: join(root, "raw", "apple"),
    rawImports: join(root, "raw", "imports"),
    rawOther: join(root, "raw", "other"),
    rawPrevious: join(root, "raw", "_previous"),
    data: join(root, "data"),
    db: join(root, "data", "health.db"),
    dashboard: join(root, "dashboard.html"),
    curatedEvents: join(root, "curated_events.csv"),
    notes: join(root, "case_study_notes.md"),
    topics: join(root, "topics.json"),
    builder: join(root, "healthpilot.py"),
    cli: join(root, "hp"),
    smartConnector: join(root, "smart_connect.py"),
  };
}
