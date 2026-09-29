// Where the data lives. The app keeps the repo layout (raw/, data/, hand-edited inputs) so the
// `hp` CLI, SQL and anything else pointed at the folder keep working.
import { app } from "electron";
import { existsSync, mkdirSync, readFileSync, renameSync, rmSync, writeFileSync } from "node:fs";
import { randomUUID } from "node:crypto";
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

type Config = { root?: string; demo?: boolean };
function config(): Config {
  try { return JSON.parse(readFileSync(join(app.getPath("userData"), CONFIG_FILE), "utf8")); }
  catch { return {}; }
}
function saveConfig(value: Config): void {
  const folder = app.getPath("userData");
  mkdirSync(folder, { recursive: true });
  const temporary = join(folder, `.config-${randomUUID()}.tmp`);
  try {
    writeFileSync(temporary, JSON.stringify(value, null, 2) + "\n", { mode: 0o600, flag: "wx" });
    renameSync(temporary, join(folder, CONFIG_FILE));
  } finally { rmSync(temporary, { force: true }); }
}
export const demoRoot = (): string => join(app.getPath("userData"), "demo-records-v1");
export const isDemo = (): boolean => config().demo === true;
/** Called only after a successful demo build; retain the personal folder for the return trip. */
export function setDemoMode(enabled: boolean): void {
  saveConfig({ ...config(), demo: enabled });
}

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
  try {
    writeFileSync(marker, JSON.stringify({ format: "clippi-health-record-store", version: 1 }, null, 2) + "\n", {
      encoding: "utf8",
      flag: "wx",
      mode: 0o600,
    });
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code !== "EEXIST") throw error;
  }
}

export function getRoot(): string {
  const saved = config();
  // Fail closed: a missing demo store must never fall back to personal records.
  if (saved.demo === true) return demoRoot();
  if (saved.root && existsSync(saved.root)) return saved.root;
  const root = defaultRoot();
  initializeRoot(root);
  return root;
}

export function setRoot(root: string): void {
  if (resolve(root) === resolve(demoRoot())) throw new Error("Use the Demo button to open the sample record.");
  initializeRoot(root);
  saveConfig({ root, demo: false });
}

export function paths(root = getRoot()): Paths {
  const code = resolve(app.getAppPath(), "..");
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
    builder: join(code, "healthpilot.py"),
    cli: join(code, "hp"),
    smartConnector: join(code, "smart_connect.py"),
    runtime: app.isPackaged
      ? join(process.resourcesPath, "clippi-runtime", process.platform === "win32" ? "clippi-runtime.exe" : "clippi-runtime")
      : "",
  };
}
