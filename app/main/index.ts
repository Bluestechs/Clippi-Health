// Clippi-Health desktop app. Everything it produces is the same as the CLI's: raw/ gets files,
// healthpilot.py rebuilds data/ and dashboard.html, nothing leaves the machine.
import { app, BrowserWindow, net, protocol, shell } from "electron";
import squirrelStartup from "electron-squirrel-startup";
import { tmpdir } from "node:os";
import { pathToFileURL } from "node:url";
import { join, normalize, resolve, sep } from "node:path";
import { registerIpc } from "./ipc";
import { runSmoke } from "./smoke";
import { getRoot } from "./roots";

if (squirrelStartup) app.quit();

if (process.platform === "win32") app.setAppUserModelId("io.github.bennydogg.clippihealth");

protocol.registerSchemesAsPrivileged([
  { scheme: "hp", privileges: { standard: true, secure: true, supportFetchAPI: true, stream: true } },
]);

app.setName("Clippi-Health");

let mainWindow: BrowserWindow | null = null;

function createWindow(): BrowserWindow {
  const window = new BrowserWindow({
    width: 1280,
    height: 860,
    minWidth: 900,
    minHeight: 600,
    title: "Clippi-Health",
    icon: join(__dirname, "logo.png"),
    backgroundColor: "#f9f9f7",
    webPreferences: {
      preload: join(__dirname, "preload.js"),
      contextIsolation: true,
      sandbox: true,
      nodeIntegration: false,
    },
  });
  window.loadFile(join(__dirname, "index.html"));
  window.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });
  return window;
}

app.whenReady().then(async () => {
  // hp://root/<path> serves the built dashboard (and whatever it references) out of the data folder,
  // so the same file still opens standalone in a browser.
  protocol.handle("hp", (request) => {
    const url = new URL(request.url);
    // The scheme is standard, so the host ("root") and the query string stay out of url.pathname.
    // resolve() strips any trailing separator a saved root may carry, so the prefix test is exact.
    const root = resolve(getRoot());
    const target = normalize(join(root, decodeURIComponent(url.pathname)));
    if (target !== root && !target.startsWith(root + sep)) return new Response("outside the data folder", { status: 403 });
    return net.fetch(pathToFileURL(target).toString());
  });

  registerIpc(() => mainWindow);
  mainWindow = createWindow();

  if (process.argv.includes("--smoke")) {
    await runSmoke(mainWindow, resolve(tmpdir(), "clippi-health-smoke"));
    app.quit();
    return;
  }

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) mainWindow = createWindow();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});
