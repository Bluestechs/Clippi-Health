// The only surface the UI gets. Everything that touches the disk, a portal or a subprocess stays in
// the main process.
import { contextBridge, ipcRenderer } from "electron";

const invoke = (channel: string, ...args: unknown[]) => ipcRenderer.invoke(channel, ...args);

contextBridge.exposeInMainWorld("hp", {
  state: () => invoke("state:get"),
  summary: () => invoke("summary:get"),
  chooseRoot: () => invoke("root:choose"),

  build: () => invoke("build:run"),
  openDashboardExternally: () => invoke("dashboard:open"),

  planImport: () => invoke("import:choose"),
  planPortalImport: () => invoke("portal:choose"),
  planArchiveImport: () => invoke("archive:choose"),
  applyImport: (plan: unknown, replaceApple: boolean, rebuild: boolean) =>
    invoke("import:apply", plan, replaceApple, rebuild),
  connectors: () => invoke("connectors:list"),
  configureConnector: (key: string, clientId: string) => invoke("connectors:configure", key, clientId),
  clearConnector: (key: string) => invoke("connectors:clear", key),
  openConnectorLink: (key: string, kind: "portal" | "registration" | "help") => invoke("connectors:open-link", key, kind),
  openRegistrationGuide: () => invoke("connectors:open-guide"),
  connectSource: (key: string) => invoke("connectors:connect", key),

  doctor: () => invoke("doctor:run"),

  events: () => invoke("events:read"),
  saveEvents: (rows: unknown) => invoke("events:write", rows),
  notes: () => invoke("notes:read"),
  saveNotes: (text: string) => invoke("notes:write", text),

  onLog: (handler: (line: string) => void) => {
    ipcRenderer.on("log", (_event, line: string) => handler(line));
  },
  onTab: (handler: (tab: string) => void) => {
    ipcRenderer.on("tab", (_event, tab: string) => handler(tab));
  },
});
