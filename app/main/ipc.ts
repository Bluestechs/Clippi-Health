// Every renderer request, in one place. Handlers return plain data; long-running work streams lines
// to the window on the "log" channel.
import { BrowserWindow, dialog, ipcMain, shell } from "electron";
import { existsSync } from "node:fs";
import { doctor } from "./doctor";
import { applyImport, planImport, type ImportPlan } from "./importer";
import { readEvents, readNotes, writeEvents, writeNotes, type EventRow } from "./inputs";
import { run } from "./proc";
import { defaultRoot, getRoot, isRoot, paths, setRoot } from "./roots";
import { invocation } from "./runtime";

export type AppState = {
  root: string;
  defaultRoot: string;
  valid: boolean;
  dashboard: boolean;
  database: boolean;
};

type Connector = {
  key: string;
  name: string;
  org: string;
  fhir_base?: string;
  ready: boolean;
  direct_capable: boolean;
  direct_note?: string;
  registration_url?: string;
  registration_note?: string;
  registration_steps?: string[];
  registration_label?: string;
  registration_guide?: "epic";
  portal_url?: string;
  portal_label?: string;
  manual_help_url?: string;
  manual_help_label?: string;
  manual_export_steps?: string[];
  manual_title?: string;
  manual_import_mode?: "files" | "portal";
  import_label?: string;
};

async function appState(): Promise<AppState> {
  const p = paths();
  return {
    root: p.root,
    defaultRoot: defaultRoot(),
    valid: isRoot(p.root),
    dashboard: existsSync(p.dashboard),
    database: existsSync(p.db),
  };
}

export function registerIpc(getWindow: () => BrowserWindow | null): void {
  const log = (line: string) => getWindow()?.webContents.send("log", line);

  const listConnectors = async (): Promise<Connector[]> => {
    const p = paths();
    const command = invocation(p, "smart", ["list", "--json"]);
    if (!command) return [];
    const { code, stdout, stderr } = await run(command.cmd, command.args, { cwd: p.root, env: command.env });
    if (code !== 0) {
      log(`connector list failed (${code}): ${stderr.trimEnd().split("\n").at(-1)?.trim() || "no error output"}`);
      return [];
    }
    try {
      return JSON.parse(stdout) as Connector[];
    } catch {
      log("connector helper returned an invalid provider list");
      return [];
    }
  };

  ipcMain.handle("state:get", appState);

  ipcMain.handle("summary:get", async () => {
    const p = paths();
    const command = invocation(p, "query", ["--json", "summary"]);
    if (!command || !existsSync(p.db)) return null;
    // `--json` belongs to `hp`, before the subcommand; `hp summary --json` exits 2. Only stdout is
    // parsed: a warning on stderr would otherwise make every summary unreadable.
    const { code, stdout, stderr } = await run(command.cmd, command.args, { cwd: p.root, env: command.env });
    if (code !== 0) {
      // Never log stdout here: on any failure path it may still hold record data.
      log(`hp summary failed (${code}): ${stderr.trimEnd().split("\n").at(-1)?.trim() || "no error output"}`);
      return null;
    }
    try {
      return JSON.parse(stdout);
    } catch {
      log("hp summary returned output that is not JSON — the “What is here” card stays hidden");
      return null;
    }
  });

  ipcMain.handle("root:choose", async () => {
    const window = getWindow();
    const picked = await dialog.showOpenDialog(window!, {
      title: "Choose the Clippi-Health data folder",
      defaultPath: getRoot(),
      properties: ["openDirectory", "createDirectory"],
    });
    const chosen = picked.filePaths[0];
    if (picked.canceled || !chosen) return appState();
    setRoot(chosen);
    return appState();
  });

  ipcMain.handle("build:run", async () => {
    const p = paths();
    const command = invocation(p, "build");
    if (!command) return { code: -1, error: "the bundled record engine was not found" };
    log(`Rebuilding the local record in ${p.root}`);
    const { code } = await run(command.cmd, command.args, { cwd: p.root, onLine: log, env: command.env });
    log(code === 0 ? "build finished" : `build failed (${code})`);
    return { code };
  });

  ipcMain.handle("dashboard:open", async () => {
    const p = paths();
    if (!existsSync(p.dashboard)) return "dashboard.html has not been built yet";
    await shell.openPath(p.dashboard);
    return null;
  });

  ipcMain.handle("import:choose", async () => {
    const window = getWindow();
    const picked = await dialog.showOpenDialog(window!, {
      title: "Add health data",
      message: "Apple Health export zip, a portal record download folder, or PDFs",
      properties: ["openFile", "openDirectory", "multiSelections"],
    });
    if (picked.canceled || !picked.filePaths.length) return null;
    return planImport(paths(), picked.filePaths);
  });

  ipcMain.handle("archive:choose", async () => {
    const window = getWindow();
    const picked = await dialog.showOpenDialog(window!, {
      title: "Choose an email or document export ZIP",
      message: "A local ZIP containing Gmail Takeout MBOX, Outlook EML, or document files",
      properties: ["openFile", "multiSelections"],
      filters: [{ name: "ZIP archives", extensions: ["zip"] }],
    });
    if (picked.canceled || !picked.filePaths.length) return null;
    return planImport(paths(), picked.filePaths);
  });

  ipcMain.handle("portal:choose", async () => {
    const window = getWindow();
    const picked = await dialog.showOpenDialog(window!, {
      title: "Choose the MyChart record download",
      message: "Choose the ZIP MyChart downloaded, or the uncompressed record folder",
      properties: ["openFile", "openDirectory"],
      filters: [{ name: "MyChart record downloads", extensions: ["zip", "xml"] }],
    });
    if (picked.canceled || !picked.filePaths.length) return null;
    return planImport(paths(), picked.filePaths);
  });

  ipcMain.handle("connectors:list", listConnectors);

  ipcMain.handle("connectors:configure", async (_event, key: string, clientId: string) => {
    const p = paths();
    const command = invocation(p, "smart", ["configure", key, clientId]);
    if (!command) return { code: -1, error: "the bundled connector engine was not found" };
    const { code, stderr } = await run(command.cmd, command.args, { cwd: p.root, env: command.env });
    return { code, error: code === 0 ? undefined : stderr.trimEnd().split("\n").at(-1)?.trim() };
  });

  ipcMain.handle("connectors:clear", async (_event, key: string) => {
    const p = paths();
    const command = invocation(p, "smart", ["clear", key]);
    if (!command) return { code: -1, error: "the bundled connector engine was not found" };
    const { code, stderr } = await run(command.cmd, command.args, { cwd: p.root, env: command.env });
    return { code, error: code === 0 ? undefined : stderr.trimEnd().split("\n").at(-1)?.trim() };
  });

  ipcMain.handle("connectors:open-link", async (_event, key: string, kind: "portal" | "registration" | "help") => {
    const connector = (await listConnectors()).find((item) => item.key === key);
    const value = kind === "portal" ? connector?.portal_url
      : kind === "help" ? connector?.manual_help_url
        : connector?.registration_url;
    if (!value) return `No ${kind} link is available for this provider.`;
    const url = new URL(value);
    if (url.protocol !== "https:") return "Provider links must use HTTPS.";
    await shell.openExternal(url.toString());
    return null;
  });

  ipcMain.handle("connectors:open-guide", async () => {
    const guide = paths().root + "/docs/EPIC_REGISTRATION.md";
    if (!existsSync(guide)) return "The Epic registration checklist was not found.";
    return (await shell.openPath(guide)) || null;
  });

  ipcMain.handle("connectors:connect", async (_event, key: string) => {
    const p = paths();
    const command = invocation(p, "smart", ["connect", key, "--no-build"]);
    if (!command) return { code: -1, error: "the bundled connector engine was not found" };
    log(`Starting local SMART connection: ${key}`);
    const result = await run(command.cmd, command.args, { cwd: p.root, onLine: log, env: command.env });
    if (result.code !== 0) return { code: result.code, error: result.stderr.trimEnd().split("\n").at(-1)?.trim() };
    const build = invocation(p, "build");
    if (!build) return { code: -1, error: "the bundled record engine was not found" };
    const built = await run(build.cmd, build.args, { cwd: p.root, onLine: log, env: build.env });
    return { code: built.code, error: built.code === 0 ? undefined : built.stderr.trimEnd().split("\n").at(-1)?.trim() };
  });

  ipcMain.handle("import:apply", async (_event, plan: ImportPlan, replaceApple: boolean, rebuild: boolean) => {
    const p = paths();
    for (const line of applyImport(p, plan, replaceApple)) log(line);
    if (!rebuild) return { code: 0 };
    const command = invocation(p, "build");
    if (!command) return { code: -1, error: "the bundled record engine was not found" };
    const { code } = await run(command.cmd, command.args, { cwd: p.root, onLine: log, env: command.env });
    log(code === 0 ? "build finished" : `build failed (${code})`);
    return { code };
  });

  ipcMain.handle("doctor:run", () => doctor(paths()));

  ipcMain.handle("events:read", () => readEvents(paths()));
  ipcMain.handle("events:write", (_event, rows: EventRow[]) => {
    writeEvents(paths(), rows);
    return true;
  });
  ipcMain.handle("notes:read", () => readNotes(paths()));
  ipcMain.handle("notes:write", (_event, text: string) => {
    writeNotes(paths(), text);
    return true;
  });
}
