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
  runtime: string;
};

const ROOT_MARKER = "clippi-health.json";

/** Development uses the checkout; installed builds create a private writable record store. */
export function defaultRoot(): string {
  return app.isPackaged
    ? join(app.getPath("userData"), "records")
    : resolve(app.getAppPath(), "..");
}

const CONFIG_FILE = "config.json";

/** Existing source checkouts and initialized installed stores are both valid data roots. */
export function isRoot(dir: string): boolean {
  return existsSync(join(dir, "healthpilot.py")) || existsSync(join(dir, ROOT_MARKER));
}

export function initializeRoot(root: string): void {
  mkdirSync(root, { recursive: true });
  for (const child of ["raw/apple", "raw/imports", "raw/other", "raw/fhir", "data"]) {
    mkdirSync(join(root, child), { recursive: true });
  }
  const marker = join(root, ROOT_MARKER);
  if (!existsSync(marker)) {
    writeFileSync(marker, JSON.stringify({ format: "clippi-health-record-store", version: 1 }, null, 2) + "\n");
  }
}

export function getRoot(): string {
  try {
    const saved = JSON.parse(readFileSync(join(app.getPath("userData"), CONFIG_FILE), "utf8")) as { root?: string };
    if (saved.root && existsSync(saved.root)) return saved.root;
  } catch {
    // no config yet, or unreadable — fall back to the folder we ship in
  }
  const root = defaultRoot();
  initializeRoot(root);
  return root;
}

export function setRoot(root: string): void {
  initializeRoot(root);
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
    runtime: app.isPackaged
      ? join(process.resourcesPath, "clippi-runtime", process.platform === "win32" ? "clippi-runtime.exe" : "clippi-runtime")
      : "",
  };
}
