import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const mock = vi.hoisted(() => ({
  userData: "", code: "",
  handlers: new Map<string, (...args: any[]) => any>(),
  run: vi.fn(), dialog: vi.fn(), external: vi.fn(), send: vi.fn(),
}));
vi.mock("electron", () => ({
  app: { isPackaged: false, getPath: () => mock.userData, getAppPath: () => join(mock.code, "app") },
  ipcMain: { handle: (name: string, handler: (...args: any[]) => any) => mock.handlers.set(name, handler) },
  dialog: { showOpenDialog: mock.dialog }, shell: { openPath: mock.external, openExternal: mock.external },
}));
vi.mock("../main/proc", () => ({ run: mock.run }));
vi.mock("../main/runtime", () => ({ invocation: (p: { root: string }, area: string) => ({
  cmd: "helper", args: [area], env: { CLIPPI_HEALTH_ROOT: p.root },
}) }));
import { defaultRoot, demoRoot, getRoot, isDemo, paths, setDemoMode, setRoot } from "../main/roots";
import { registerIpc } from "../main/ipc";

const call = (name: string, ...args: unknown[]) => mock.handlers.get(name)!(null, ...args);
const success = { code: 0, stdout: "{}", stderr: "", output: "" };
let temp: string;
let personal: string;

beforeEach(() => {
  vi.clearAllMocks();
  temp = mkdtempSync(join(tmpdir(), "clippi-demo-test-"));
  mock.userData = join(temp, "settings");
  mock.code = join(temp, "code");
  personal = join(temp, "personal");
  setRoot(personal);
  writeFileSync(join(personal, "case_study_notes.md"), "PRIVATE_SENTINEL");
  mock.run.mockResolvedValue(success);
  registerIpc(() => ({ webContents: { send: mock.send } }) as any);
});
afterEach(() => rmSync(temp, { recursive: true, force: true }));

describe("isolated demo mode", () => {
  it("keeps and restores the personal root, and never falls back when demo files are missing", async () => {
    expect((await call("demo:set", true)).code).toBe(0);
    expect(getRoot()).toBe(demoRoot());
    expect(isDemo()).toBe(true);
    expect((await call("state:get")).root).not.toContain(temp);
    expect(readFileSync(join(personal, "case_study_notes.md"), "utf8")).toBe("PRIVATE_SENTINEL");
    const saved = JSON.parse(readFileSync(join(mock.userData, "config.json"), "utf8"));
    expect(saved).toEqual({ root: personal, demo: true });
    expect((await call("demo:set", false)).code).toBe(0);
    expect(getRoot()).toBe(personal);
    expect(paths(demoRoot()).builder).toBe(join(mock.code, "healthpilot.py"));
  });

  it("starts from the default store when no folder was selected", async () => {
    rmSync(join(mock.userData, "config.json"));
    expect((await call("demo:set", true)).code).toBe(0);
    expect(getRoot()).toBe(demoRoot());
    await call("demo:set", false);
    expect(getRoot()).toBe(defaultRoot());
  });

  it("leaves personal mode intact on generation failure and suppresses paths from errors", async () => {
    mock.run.mockResolvedValue({ ...success, code: 1, stderr: "PRIVATE_SENTINEL" });
    expect((await call("demo:set", true)).code).toBe(-1);
    expect(isDemo()).toBe(false);
    expect(getRoot()).toBe(personal);
    expect(mock.send).not.toHaveBeenCalled();
  });

  it("blocks personal imports, source setup and external windows in the main process", async () => {
    setDemoMode(true);
    for (const name of ["root:choose", "import:choose", "archive:choose", "portal:choose", "import:apply",
      "connectors:configure", "connectors:clear", "connectors:connect", "connectors:open-link",
      "connectors:open-guide", "dashboard:open"]) {
      await expect(call(name)).rejects.toThrow("Exit demo mode");
    }
    expect(mock.dialog).not.toHaveBeenCalled();
    expect(mock.external).not.toHaveBeenCalled();
    expect(() => setRoot(demoRoot())).toThrow("Demo button");
  });

  it("routes editable notes only to the active demo folder", async () => {
    mkdirSync(demoRoot(), { recursive: true });
    setDemoMode(true);
    await call("notes:write", "Sally's fictional note");
    expect(await call("notes:read")).toBe("Sally's fictional note\n");
    expect(readFileSync(join(personal, "case_study_notes.md"), "utf8")).toBe("PRIVATE_SENTINEL");
  });

  it("prevents a switch during an in-flight request, and requests during a switch", async () => {
    writeFileSync(paths().db, "placeholder");
    let finish!: (value: typeof success) => void;
    mock.run.mockImplementation(() => new Promise(resolve => { finish = resolve; }));
    const pending = call("summary:get");
    expect((await call("demo:set", true)).code).toBe(-1);
    finish(success);
    await pending;
    const switching = call("demo:set", true);
    await expect(call("notes:write", "wrong store")).rejects.toThrow("changing");
    expect((await call("demo:set", false)).code).toBe(-1);
    finish(success);
    await switching;
    expect(isDemo()).toBe(true);
  });
});
