// `npm run smoke` drives the shell through every tab and writes a screenshot of each, so a change
// to the UI can be looked at without a portal login or a rebuild.
import type { BrowserWindow } from "electron";
import { chmodSync, mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { delay } from "./proc";

const TABS = ["dashboard", "import", "build", "events", "notes", "doctor"];

function writePrivateScreenshot(file: string, data: Buffer): void {
  writeFileSync(file, data, { flag: "wx", mode: 0o600 });
}

export async function runSmoke(window: BrowserWindow): Promise<void> {
  const outDir = mkdtempSync(join(tmpdir(), "clippi-health-smoke-"));
  chmodSync(outDir, 0o700);
  process.stdout.write(`saving private smoke screenshots in ${outDir}\n`);
  if (window.webContents.isLoadingMainFrame()) {
    const { promise, resolve } = Promise.withResolvers<void>();
    window.webContents.once("did-finish-load", () => resolve());
    await promise;
  }
  for (const tab of TABS) {
    window.webContents.send("tab", tab);
    await delay(1500); // the dashboard iframe inlines Plotly, so give it a paint
    const image = await window.webContents.capturePage();
    const file = join(outDir, `${tab}.png`);
    writePrivateScreenshot(file, image.toPNG());
    process.stdout.write(`captured ${file}\n`);
  }
  for (const theme of ["light", "dark"]) {
    await window.webContents.executeJavaScript(`(() => {
      document.querySelector('[data-theme-value="${theme}"]').click();
    })()`);
    window.webContents.send("tab", "import");
    await delay(500);
    const image = await window.webContents.capturePage();
    const file = join(outDir, `import-${theme}.png`);
    writePrivateScreenshot(file, image.toPNG());
    process.stdout.write(`captured ${file}\n`);
  }
  await window.webContents.executeJavaScript(`(() => {
    document.querySelector('[data-theme-value="light"]').click();
    document.querySelector(".connector details").open = true;
    document.querySelector(".connector").scrollIntoView({ block: "start" });
  })()`);
  await delay(500);
  const connectorNames = await window.webContents.executeJavaScript(`(() =>
    [...document.querySelectorAll(".connector-heading strong")].map((node) => node.textContent)
  )()`);
  for (const expected of ["BJC HealthCare MyChart", "Labcorp", "Quest Diagnostics"]) {
    if (!connectorNames.includes(expected)) throw new Error(`connector card did not render: ${expected}`);
  }
  process.stdout.write(`connector cards ${JSON.stringify(connectorNames)}\n`);
  const connector = await window.webContents.capturePage();
  const connectorFile = join(outDir, "connector-light.png");
  writePrivateScreenshot(connectorFile, connector.toPNG());
  process.stdout.write(`captured ${connectorFile}\n`);
  const themeMenuState = await window.webContents.executeJavaScript(`(() => {
    document.querySelector('[data-theme-value="light"]').click();
    document.getElementById("theme-toggle").click();
    const menu = document.getElementById("theme-menu");
    const rect = menu.getBoundingClientRect();
    const front = document.elementFromPoint(rect.left + rect.width / 2, rect.top + rect.height / 2);
    return { hidden: menu.hidden, display: getComputedStyle(menu).display, front: menu.contains(front), rect: rect.toJSON() };
  })()`);
  if (themeMenuState.hidden || themeMenuState.display === "none" || !themeMenuState.front) {
    throw new Error("theme menu did not open above the app content");
  }
  process.stdout.write(`theme menu ${JSON.stringify(themeMenuState)}\n`);
  await delay(250);
  const themeMenu = await window.webContents.capturePage();
  const themeMenuFile = join(outDir, "theme-menu.png");
  writePrivateScreenshot(themeMenuFile, themeMenu.toPNG());
  process.stdout.write(`captured ${themeMenuFile}\n`);
  await window.webContents.executeJavaScript(`(() => {
    document.querySelector('[data-theme-value="system"]').click();
  })()`);
}
