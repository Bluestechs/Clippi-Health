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
  await delay(1200);
  const originalRoot = await window.webContents.executeJavaScript('(async () => (await window.hp.state()).root)()');
  await window.webContents.executeJavaScript('document.getElementById("demo-toggle").click()');
  let ready = false;
  for (let attempt = 0; attempt < 60; attempt++) {
    await delay(500);
    ready = await window.webContents.executeJavaScript(`
      document.body.classList.contains("demo-mode") && document.getElementById("who").textContent === "Sally"
    `).catch(() => false);
    if (ready) break;
  }
  if (!ready) throw new Error("The Demo button did not load Sally Seastar");
  process.stdout.write("Demo button loaded Sally Seastar in an isolated store.\n");
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
  window.webContents.send("tab", "dashboard");
  await delay(500);
  const dashboard = window.webContents.mainFrame.frames.find(frame => frame.url.startsWith("hp://root/"));
  if (!dashboard) throw new Error("Demo dashboard frame is missing");
  const sample = await dashboard.executeJavaScript(`(() => {
    showTab("vitals");
    return { name: DATA.patient.firstName, days: DATA.vitals.filter(r => r.metric === "CGM / meter glucose").length, labs: DATA.labs.length };
  })()`) as { name: string; days: number; labs: number };
  if (sample.name !== "Sally" || sample.days !== 365 || sample.labs !== 108) throw new Error("Demo charts lack expected data");
  await delay(700);
  writePrivateScreenshot(join(outDir, "demo-vitals.png"), (await window.webContents.capturePage()).toPNG());
  const zoom = await dashboard.executeJavaScript(`(async () => {
    const chart = document.querySelector("#vitals .js-plotly-plot");
    const dates = DATA.vitals.filter(r => r.metric === "CGM / meter glucose").map(r => r.date);
    const range = dates.slice(-14);
    await Plotly.relayout(chart, { "xaxis.range": [range[0], range.at(-1)] });
    return chart.layout.xaxis.range;
  })()`) as string[];
  if (zoom.length !== 2 || zoom[0] === zoom[1]) throw new Error("Demo CGM chart did not zoom");
  const paired = await dashboard.executeJavaScript(`(async () => {
    const glucose = document.querySelector('[data-diabetes-metric="glucose"] .js-plotly-plot');
    const insulin = document.querySelector('[data-diabetes-metric="insulin"] .js-plotly-plot');
    const sameRange = () => JSON.stringify(glucose.layout.xaxis.range) === JSON.stringify(insulin.layout.xaxis.range);
    const fromGlucose = sameRange();
    const dates = DATA.vitals.filter(r => r.metric === "Insulin").map(r => r.date);
    await Plotly.relayout(insulin, { "xaxis.range": [dates.at(-7), dates.at(-1)] });
    await new Promise(requestAnimationFrame);
    const fromInsulin = sameRange();
    await Plotly.relayout(insulin, { "xaxis.autorange": true });
    await new Promise(requestAnimationFrame);
    const reset = sameRange() && new Date(glucose.layout.xaxis.range[0]) < new Date(dates.at(-14));
    const left = glucose.getBoundingClientRect(), right = insulin.getBoundingClientRect();
    return { fromGlucose, fromInsulin, reset, sideBySide: right.left > left.left && Math.abs(right.top - left.top) < 5 };
  })()`) as { fromGlucose: boolean; fromInsulin: boolean; reset: boolean; sideBySide: boolean };
  if (!Object.values(paired).every(Boolean)) throw new Error(`Paired diabetes charts failed: ${JSON.stringify(paired)}`);
  for (const theme of ["light", "dark"]) {
    await window.webContents.executeJavaScript(`document.querySelector('[data-theme-value="${theme}"]').click()`);
    await delay(300);
    const colors = await dashboard.executeJavaScript(`(() => {
      const insulin = document.querySelector('[data-diabetes-metric="insulin"] .js-plotly-plot');
      const basal = insulin.data.filter(trace => trace.name.startsWith("Basal"));
      const bolus = insulin.data.filter(trace => trace.name.startsWith("Bolus"));
      return basal.length > 0 && bolus.length > 0 &&
        basal.every(trace => trace.line.color === cssVar("--insulin-basal")) &&
        bolus.every(trace => trace.line.color === cssVar("--c-orange"));
    })()`);
    if (!colors) throw new Error(`Insulin delivery types did not use pink/orange in ${theme} theme`);
    writePrivateScreenshot(join(outDir, `diabetes-${theme}.png`), (await window.webContents.capturePage()).toPNG());
  }
  process.stdout.write(`Paired diabetes charts passed bidirectional zoom, reset, layout and basal/bolus colors in both themes.\n`);
  writePrivateScreenshot(join(outDir, "demo-vitals-zoom.png"), (await window.webContents.capturePage()).toPNG());
  await dashboard.executeJavaScript('showTab("labs")');
  await delay(500);
  writePrivateScreenshot(join(outDir, "demo-labs.png"), (await window.webContents.capturePage()).toPNG());
  process.stdout.write(`Demo chart data and zoom passed: ${JSON.stringify(sample)}\n`);
  const returned = await window.webContents.executeJavaScript(`(async () => {
    const result = await window.hp.setDemo(false);
    const state = await window.hp.state();
    return { ok: result.code === 0 && !state.demo, root: state.root, notes: await window.hp.notes() };
  })()`);
  if (!returned.ok || returned.root !== originalRoot || returned.notes !== "Smoke return-folder sentinel\n") {
    throw new Error("Demo exit did not restore the original record folder and notes");
  }
}
