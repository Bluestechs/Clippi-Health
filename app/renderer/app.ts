// The app shell. No data handling here: every disk, portal and subprocess operation is an IPC call.
type AppState = {
  demo: boolean;
  root: string;
  defaultRoot: string;
  valid: boolean;
  dashboard: boolean;
  database: boolean;
};
type ImportItem = { source: string; kind: string; dest: string; note: string };
type ImportPlan = { items: ImportItem[]; replaced: string[]; skipped: string[] };
type Check = { check: string; ok: boolean; hint?: string };
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
type EventRow = Record<string, string>;
type Summary = {
  patient?: { firstName?: string };
  built_at?: string;
  labs?: number;
  distinct_tests?: number;
  documents?: Record<string, number>;
  encounters_past?: number;
  events?: number;
  vitals_days?: number;
  sources?: { key: string; org: string; exported_at: string; coverage_from: string; coverage_to: string }[];
};

type Bridge = {
  setDemo(enabled: boolean): Promise<{ code: number; error?: string }>;
  state(): Promise<AppState>;
  summary(): Promise<Summary | null>;
  chooseRoot(): Promise<AppState>;
  build(): Promise<{ code: number; error?: string }>;
  openDashboardExternally(): Promise<string | null>;
  planImport(): Promise<ImportPlan | null>;
  planPortalImport(): Promise<ImportPlan | null>;
  planArchiveImport(): Promise<ImportPlan | null>;
  applyImport(plan: ImportPlan, replaceApple: boolean, rebuild: boolean): Promise<{ code: number; error?: string }>;
  connectors(): Promise<Connector[]>;
  configureConnector(key: string, clientId: string): Promise<{ code: number; error?: string }>;
  clearConnector(key: string): Promise<{ code: number; error?: string }>;
  openConnectorLink(key: string, kind: "portal" | "registration" | "help"): Promise<string | null>;
  openRegistrationGuide(): Promise<string | null>;
  connectSource(key: string): Promise<{ code: number; error?: string }>;
  doctor(): Promise<Check[]>;
  events(): Promise<EventRow[]>;
  saveEvents(rows: EventRow[]): Promise<boolean>;
  notes(): Promise<string>;
  saveNotes(text: string): Promise<boolean>;
  onLog(handler: (line: string) => void): void;
  onTab(handler: (tab: string) => void): void;
};

export {}; // module scope, so the Window augmentation below is allowed

declare global {
  interface Window {
    hp: Bridge;
  }
}

const EVENT_COLUMNS = ["date", "lane", "title", "detail", "org", "docs", "replaces"];
const LANES = ["Diagnoses", "Surgery & procedures", "Hospital & ED", "Imaging", "Pathology & reports", "Milestones"];

/** Elements are all in index.html; a missing one is a bug, not a runtime condition. */
function el<T extends HTMLElement>(id: string): T {
  const node = document.getElementById(id);
  if (!node) throw new Error(`missing element #${id}`);
  return node as T;
}

let state: AppState | null = null;
let events: EventRow[] = [];
type Theme = "system" | "light" | "dark";
const THEME_LABELS: Record<Theme, string> = { system: "System", light: "Light · Paper", dark: "Dark" };
let currentTheme: Theme = "system";

function isTheme(value: string | null): value is Theme {
  return value === "system" || value === "light" || value === "dark";
}

function applyTheme(theme: Theme): void {
  currentTheme = theme;
  if (theme === "system") document.documentElement.removeAttribute("data-theme");
  else document.documentElement.dataset.theme = theme;
  localStorage.setItem("healthpilot-theme", theme);
  for (const button of document.querySelectorAll<HTMLButtonElement>("[data-theme-value]")) {
    button.setAttribute("aria-checked", String(button.dataset.themeValue === theme));
  }
  const toggle = el<HTMLButtonElement>("theme-toggle");
  toggle.setAttribute("aria-label", `Choose color theme. Current: ${THEME_LABELS[theme]}`);
  toggle.title = `Color theme: ${THEME_LABELS[theme]}`;
  el<HTMLIFrameElement>("dashboard").contentWindow?.postMessage({ type: "healthpilot:theme", theme }, "*");
}

function setThemeMenu(open: boolean): void {
  const menu = el<HTMLElement>("theme-menu");
  const toggle = el<HTMLButtonElement>("theme-toggle");
  menu.hidden = !open;
  toggle.setAttribute("aria-expanded", String(open));
  if (open) {
    menu.querySelector<HTMLButtonElement>(`[data-theme-value="${currentTheme}"]`)?.focus();
  }
}

// --- log drawer -------------------------------------------------------------

function appendLog(line: string): void {
  const log = el<HTMLPreElement>("log");
  log.textContent += line + "\n";
  log.scrollTop = log.scrollHeight;
  el("log-last").textContent = line.slice(0, 120);
}

// --- tabs -------------------------------------------------------------------

function showTab(name: string): void {
  for (const button of document.querySelectorAll<HTMLButtonElement>("#tabs button")) {
    button.setAttribute("aria-selected", String(button.dataset.tab === name));
    button.tabIndex = button.dataset.tab === name ? 0 : -1;
  }
  for (const section of document.querySelectorAll<HTMLElement>("main section")) {
    section.hidden = section.id !== `tab-${name}`;
  }
  if (name === "doctor") void renderDoctor();
  if (name === "events") void loadEvents();
  if (name === "notes") void loadNotes();
  if (name === "build") void renderSummary();
  if (name === "import") {
    void renderSources();
    void renderConnectors();
  }
}

// --- state ------------------------------------------------------------------

async function refreshState(): Promise<void> {
  state = await window.hp.state();
  document.body.classList.toggle("demo-mode", state.demo);
  el("demo-banner").hidden = !state.demo;
  el("demo-toggle").textContent = state.demo ? "Exit demo" : "Try demo";
  el("demo-toggle").title = state.demo ? "Return to your own records" : "Open Sally Seastar’s fictional record";
  for (const id of ["root-choose", "open-external", "import-choose", "archive-import-choose"]) {
    el<HTMLButtonElement>(id).disabled = state.demo;
  }
  el("root-path").textContent = state.root;
  el("dashboard-note").textContent = !state.valid
    ? "The selected data folder is unavailable. Reconnect it or choose your existing records in Doctor → Change data folder."
    : state.dashboard ? ""
      : "No dashboard yet — add data, then rebuild on the Build tab.";
  const frame = el<HTMLIFrameElement>("dashboard");
  // An empty white frame reads as a broken app: hide it until there is a file to serve and let
  // #dashboard-note say why. The timestamp defeats the cache after a rebuild.
  frame.hidden = !state.dashboard;
  frame.src = state.dashboard ? `hp://root/dashboard.html?v=${Date.now()}` : "about:blank";
}

async function renderSummary(): Promise<void> {
  const summary = await window.hp.summary();
  const card = el("summary-card");
  // The header names whoever the current data folder belongs to; a folder with no database must
  // not keep showing the last one.
  el("who").textContent = summary?.patient?.firstName ?? "";
  el("built").textContent = summary?.built_at ? `built ${summary.built_at}` : "";
  if (!summary) {
    card.hidden = true;
    return;
  }
  card.hidden = false;
  const documents = Object.entries(summary.documents ?? {})
    .map(([kind, n]) => `${n} ${kind}`)
    .join(", ");
  const lines = [
    `${summary.labs ?? 0} lab results · ${summary.distinct_tests ?? 0} distinct tests`,
    `documents: ${documents || "none"}`,
    `${summary.encounters_past ?? 0} past encounters · ${summary.events ?? 0} timeline events · ${summary.vitals_days ?? 0} days of device data`,
    ...(summary.sources ?? []).map(
      (source) => `${source.key}: ${source.org} — exported ${source.exported_at}, records ${source.coverage_from} → ${source.coverage_to}`,
    ),
  ];
  const target = el("summary");
  target.replaceChildren(
    ...lines.map((line) => {
      const div = document.createElement("div");
      div.textContent = line;
      return div;
    }),
  );
}

// --- import -----------------------------------------------------------------

async function renderSources(): Promise<void> {
  const target = el("current-sources");
  const summary = await window.hp.summary();
  const sources = summary?.sources ?? [];
  if (!sources.length) {
    target.textContent = "No sources have been built yet. Choose an import or connection below.";
    return;
  }
  target.replaceChildren(...sources.map((source) => {
    const row = document.createElement("div");
    row.className = "source-row";
    const identity = document.createElement("div");
    const name = document.createElement("strong");
    name.textContent = source.org || source.key;
    const key = document.createElement("code");
    key.textContent = source.key;
    identity.append(name, key);
    const detail = document.createElement("span");
    const coverage = source.coverage_from || source.coverage_to
      ? `${source.coverage_from || "?"} → ${source.coverage_to || "?"}`
      : "coverage not reported";
    detail.textContent = `${coverage} · imported ${source.exported_at || "date unknown"}`;
    row.append(identity, detail);
    return row;
  }));
}

let renderedConnectorCatalog: string | null = null;

async function renderConnectors(): Promise<void> {
  const target = el("connector-list");
  const root = state?.root, demo = state?.demo;
  const connectors = await window.hp.connectors();
  if (state?.root !== root || state?.demo !== demo) return;
  const catalog = JSON.stringify([root, demo, connectors]);
  // A tab refresh must not remove the focused control, open details, or unsaved client ID.
  if (catalog === renderedConnectorCatalog) return;
  if (!connectors.length) {
    target.textContent = "No health-system profiles were found. You can still import FHIR, C-CDA, Apple Health, and ordinary files below.";
    renderedConnectorCatalog = catalog;
    return;
  }
  target.replaceChildren(...connectors.map((connector) => {
    const card = document.createElement("article");
    card.className = "connector";

    const heading = document.createElement("div");
    heading.className = "connector-heading";
    const identity = document.createElement("div");
    const name = document.createElement("strong");
    name.textContent = connector.name;
    const org = document.createElement("span");
    org.textContent = connector.org;
    identity.append(name, org);
    const status = document.createElement("span");
    status.className = `badge ${connector.ready ? "on" : ""}`;
    status.textContent = connector.ready ? "Your client ID saved" : "Manual import available";
    heading.append(identity, status);
    card.append(heading);

    if (connector.manual_export_steps?.length) {
      const manual = document.createElement("div");
      manual.className = "connector-manual";
      const title = document.createElement("strong");
      title.textContent = connector.manual_title ?? "Import a one-time download";
      const steps = document.createElement("ol");
      for (const value of connector.manual_export_steps) {
        const step = document.createElement("li");
        step.textContent = value;
        steps.append(step);
      }
      const actions = document.createElement("div");
      actions.className = "row";
      if (connector.portal_url) {
        const portal = document.createElement("button");
        portal.className = "ghost";
        portal.textContent = connector.portal_label ?? `Open ${connector.name}`;
        portal.onclick = async () => {
          const error = await window.hp.openConnectorLink(connector.key, "portal");
          if (error) appendLog(error);
        };
        actions.append(portal);
      }
      if (connector.manual_help_url) {
        const help = document.createElement("button");
        help.className = "ghost";
        help.textContent = connector.manual_help_label ?? "View export instructions";
        help.onclick = async () => {
          const error = await window.hp.openConnectorLink(connector.key, "help");
          if (error) appendLog(error);
        };
        actions.append(help);
      }
      const choose = document.createElement("button");
      choose.textContent = connector.import_label ?? "Choose downloaded files…";
      const planTarget = document.createElement("div");
      choose.onclick = async () => {
        const plan = connector.manual_import_mode === "portal"
          ? await window.hp.planPortalImport()
          : await window.hp.planImport();
        renderImportPlan(planTarget, plan, `Import ${connector.name} records`);
      };
      actions.append(choose);
      manual.append(title, steps, actions, planTarget);
      card.append(manual);
    }

    const direct = document.createElement("div");
    direct.className = "connector-direct";
    const directText = document.createElement("div");
    const directTitle = document.createElement("strong");
    directTitle.textContent = "Direct OAuth connection";
    const directNote = document.createElement("span");
    directNote.textContent = connector.ready
      ? `Your public client ID is saved in this local record store; provider activation still needs to be confirmed. Sign in separately on ${connector.name}'s page; Clippi-Health downloads FHIR to this computer and discards the token when it finishes.`
      : connector.direct_note ?? (connector.direct_capable
        ? "Save the public client ID from your provider registration in this local record store. The manual download above works without registration."
        : "This provider has not published the app-registration details needed for a safe local OAuth connection.");
    directText.append(directTitle, directNote);
    direct.append(directText);
    if (connector.ready) {
      const button = document.createElement("button");
      button.textContent = "Connect";
      button.onclick = async () => {
        button.disabled = true;
        el("log").hidden = false;
        const result = await window.hp.connectSource(connector.key);
        if (result.error) appendLog(result.error);
        button.disabled = false;
        await refreshState();
        await renderSummary();
        await renderSources();
      };
      direct.append(button);
    }
    card.append(direct);

    if (!connector.direct_capable && !connector.registration_note && !connector.registration_url) return card;

    const setup = document.createElement("details");
    const setupTitle = document.createElement("summary");
    setupTitle.textContent = connector.direct_capable
      ? (connector.ready ? "Your direct connection settings" : "Your registration for direct connection")
      : "Direct OAuth status";
    const setupNote = document.createElement("p");
    setupNote.className = "sub";
    setupNote.textContent = connector.registration_note ?? "Enter the public client ID from your own provider registration. It identifies the registered app, not your patient account, and is saved only in this local record store.";
    const registrationSteps = document.createElement("ol");
    registrationSteps.className = "registration-steps";
    for (const value of connector.registration_steps ?? []) {
      const step = document.createElement("li");
      step.textContent = value;
      registrationSteps.append(step);
    }
    const setupActions = document.createElement("div");
    setupActions.className = "connector-setup";
    if (!connector.direct_capable) {
      // Manual-only profiles can link to a provider's API request path, but cannot accept a
      // client ID until an endpoint and loopback OAuth contract have been verified.
    } else if (connector.ready) {
      const clear = document.createElement("button");
      clear.className = "ghost";
      clear.textContent = "Remove your local client ID";
      clear.onclick = async () => {
        const result = await window.hp.clearConnector(connector.key);
        if (result.error) appendLog(result.error);
        await renderConnectors();
      };
      setupActions.append(clear);
    } else {
      const input = document.createElement("input");
      input.placeholder = "Your production public client ID";
      input.autocomplete = "off";
      input.setAttribute("aria-label", "Your production public client ID");
      const save = document.createElement("button");
      save.textContent = "Save your client ID locally";
      const error = document.createElement("span");
      error.className = "error";
      save.onclick = async () => {
        error.textContent = "";
        save.disabled = true;
        const result = await window.hp.configureConnector(connector.key, input.value.trim());
        save.disabled = false;
        if (result.error) error.textContent = result.error;
        else await renderConnectors();
      };
      setupActions.append(input, save, error);
    }
    if (connector.registration_url) {
      const registration = document.createElement("button");
      registration.className = "ghost";
      registration.textContent = connector.registration_label ?? "Open your provider registration";
      registration.onclick = async () => {
        const error = await window.hp.openConnectorLink(connector.key, "registration");
        if (error) appendLog(error);
      };
      setupActions.append(registration);
    }
    if (connector.registration_guide === "epic") {
      const guide = document.createElement("button");
      guide.className = "ghost";
      guide.textContent = "Open full registration checklist";
      guide.onclick = async () => {
        const error = await window.hp.openRegistrationGuide();
        if (error) appendLog(error);
      };
      setupActions.append(guide);
    }
    setup.append(setupTitle, setupNote);
    if (registrationSteps.childElementCount) setup.append(registrationSteps);
    if (setupActions.childElementCount) setup.append(setupActions);
    card.append(setup);
    if (state?.demo) {
      for (const control of card.querySelectorAll<HTMLButtonElement | HTMLInputElement>("button, input")) {
        control.disabled = true;
        control.title = "Exit demo to connect or import personal records";
      }
    }
    return card;
  }));
  renderedConnectorCatalog = catalog;
}

function renderImportPlan(target: HTMLElement, plan: ImportPlan | null, label: string): void {
  target.replaceChildren();
  if (!plan || (!plan.items.length && !plan.skipped.length)) return;

  const list = document.createElement("ul");
  list.className = "plan";
  for (const item of plan.items) {
    const li = document.createElement("li");
    li.textContent = `${item.note}: ${item.source}`;
    list.append(li);
  }
  for (const skip of plan.skipped) {
    const li = document.createElement("li");
    li.className = "warn";
    li.textContent = skip;
    list.append(li);
  }
  target.append(list);

  const replace = document.createElement("input");
  replace.type = "checkbox";
  replace.checked = true;
  replace.style.width = "auto";
  if (plan.replaced.length) {
    const replaceRow = document.createElement("label");
    replaceRow.append(replace, document.createTextNode(` Keep the current Apple export in raw/_previous and replace it (${plan.replaced.length})`));
    target.append(replaceRow);
  }

  const rebuildRow = document.createElement("label");
  const rebuild = document.createElement("input");
  rebuild.type = "checkbox";
  rebuild.checked = true;
  rebuild.style.width = "auto";
  rebuildRow.append(rebuild, document.createTextNode(" Rebuild after copying"));
  target.append(rebuildRow);

  const apply = document.createElement("button");
  apply.textContent = label;
  apply.onclick = async () => {
    apply.disabled = true;
    el("log").hidden = false;
    const result = await window.hp.applyImport(plan, replace.checked, rebuild.checked);
    if (result.error) appendLog(result.error);
    target.replaceChildren();
    await refreshState();
    await renderSummary();
    await renderSources();
  };
  const row = document.createElement("div");
  row.className = "row";
  row.style.marginTop = "12px";
  row.append(apply);
  target.append(row);
}

async function chooseImport(archive = false): Promise<void> {
  const plan = archive ? await window.hp.planArchiveImport() : await window.hp.planImport();
  const target = el(archive ? "archive-import-plan" : "import-plan");
  renderImportPlan(target, plan, archive ? "Import archive" : "Add to local record");
}

// --- curated events ---------------------------------------------------------

async function loadEvents(): Promise<void> {
  events = await window.hp.events();
  renderEvents();
}

function renderEvents(): void {
  const table = el<HTMLTableElement>("events-table");
  const head = document.createElement("tr");
  for (const column of [...EVENT_COLUMNS, ""]) {
    const th = document.createElement("th");
    th.textContent = column || "Actions";
    th.scope = "col";
    head.append(th);
  }
  const rows = events.map((event, index) => {
    const tr = document.createElement("tr");
    for (const column of EVENT_COLUMNS) {
      const td = document.createElement("td");
      if (column === "lane") {
        const select = document.createElement("select");
        select.setAttribute("aria-label", `Event ${index + 1}: ${column}`);
        for (const lane of ["", ...LANES]) {
          const option = document.createElement("option");
          option.value = lane;
          option.textContent = lane;
          option.selected = lane === event[column];
          select.append(option);
        }
        select.onchange = () => {
          event[column] = select.value;
        };
        td.append(select);
      } else {
        const input = document.createElement("input");
        input.value = event[column] ?? "";
        input.setAttribute("aria-label", `Event ${index + 1}: ${column}`);
        input.oninput = () => {
          event[column] = input.value;
        };
        td.append(input);
      }
      tr.append(td);
    }
    const actions = document.createElement("td");
    const remove = document.createElement("button");
    remove.className = "ghost danger";
    remove.textContent = "×";
    remove.setAttribute("aria-label", `Remove event ${index + 1}`);
    remove.onclick = () => {
      events.splice(index, 1);
      renderEvents();
      el("events-add").focus();
    };
    actions.append(remove);
    tr.append(actions);
    return tr;
  });
  table.replaceChildren(head, ...rows);
}

// --- notes ------------------------------------------------------------------

async function loadNotes(): Promise<void> {
  el<HTMLTextAreaElement>("notes").value = await window.hp.notes();
}

// --- doctor -----------------------------------------------------------------

async function renderDoctor(): Promise<void> {
  const checks = await window.hp.doctor();
  el("doctor-list").replaceChildren(
    ...checks.map((check) => {
      const row = document.createElement("div");
      row.className = "check";
      const flag = document.createElement("span");
      flag.className = check.ok ? "flag ok" : "flag warn";
      flag.textContent = check.ok ? "OK" : "WARN";
      const label = document.createElement("span");
      label.textContent = check.check;
      const hint = document.createElement("span");
      hint.className = "hint";
      hint.textContent = !check.ok && check.hint ? `→ ${check.hint}` : "";
      row.append(flag, label, hint);
      return row;
    }),
  );
}

// --- wiring -----------------------------------------------------------------

let requestedDemo = false;
async function switchDemo(enabled: boolean): Promise<void> {
  requestedDemo = enabled;
  document.body.classList.add("mode-switching");
  el("mode-cover").hidden = false;
  el("mode-retry").hidden = true;
  el("mode-back").hidden = true;
  el("mode-message").textContent = enabled ? "Preparing Sally Seastar’s demo…" : "Returning to your records…";
  // Blank the embedded page now. A full reload drops cached notes, logs, sources and pending UI work.
  el<HTMLIFrameElement>("dashboard").src = "about:blank";
  try {
    const result = await window.hp.setDemo(enabled);
    if (result.code === 0) { window.location.reload(); return; }
    el("mode-message").textContent = result.error ?? "Could not switch records.";
  } catch {
    el("mode-message").textContent = "Could not switch records. Try again when the current operation finishes.";
  }
  // Keep the privacy cover up on errors; returning to the previous records is explicit.
  el("mode-retry").hidden = false;
  el("mode-back").hidden = false;
}

el("demo-toggle").onclick = () => {
  if (state?.demo && !window.confirm("Exit demo and show your personal records? Stop recording before continuing.")) return;
  void switchDemo(!state?.demo);
};
el("mode-retry").onclick = () => void switchDemo(requestedDemo);
el("mode-back").onclick = () => window.location.reload();

window.hp.onLog(appendLog);
window.hp.onTab(showTab);

for (const button of document.querySelectorAll<HTMLButtonElement>("#tabs button")) {
  button.onclick = () => showTab(button.dataset.tab ?? "dashboard");
  button.tabIndex = button.getAttribute("aria-selected") === "true" ? 0 : -1;
  button.onkeydown = (event) => {
    const buttons = [...document.querySelectorAll<HTMLButtonElement>("#tabs button")];
    const index = buttons.indexOf(button);
    const next = event.key === "ArrowRight" ? (index + 1) % buttons.length : event.key === "ArrowLeft" ? (index + buttons.length - 1) % buttons.length : event.key === "Home" ? 0 : event.key === "End" ? buttons.length - 1 : null;
    if (next == null) return;
    event.preventDefault(); buttons[next]?.click(); buttons[next]?.focus();
  };
}

el("log-toggle").onclick = () => {
  const log = el("log");
  log.hidden = !log.hidden;
  el("log-toggle").setAttribute("aria-expanded", String(!log.hidden));
};

const savedTheme = localStorage.getItem("healthpilot-theme");
applyTheme(isTheme(savedTheme) ? savedTheme : "system");
el("theme-toggle").onclick = () => setThemeMenu(el("theme-menu").hidden);
el("theme-menu").onkeydown = (event) => {
  const buttons = [...el("theme-menu").querySelectorAll<HTMLButtonElement>("button")];
  const index = buttons.indexOf(document.activeElement as HTMLButtonElement);
  const next = event.key === "ArrowDown" ? (index + 1) % buttons.length : event.key === "ArrowUp" ? (index + buttons.length - 1) % buttons.length : event.key === "Home" ? 0 : event.key === "End" ? buttons.length - 1 : null;
  if (next == null) return;
  event.preventDefault(); buttons[next]?.focus();
};
for (const button of document.querySelectorAll<HTMLButtonElement>("[data-theme-value]")) {
  button.onclick = () => {
    const theme = button.dataset.themeValue ?? null;
    if (isTheme(theme)) applyTheme(theme);
    setThemeMenu(false);
    el<HTMLButtonElement>("theme-toggle").focus();
  };
}
document.addEventListener("click", (event) => {
  if (!el("theme-picker").contains(event.target as Node)) setThemeMenu(false);
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !el("theme-menu").hidden) {
    setThemeMenu(false);
    el<HTMLButtonElement>("theme-toggle").focus();
  }
});
el<HTMLIFrameElement>("dashboard").addEventListener("load", () => applyTheme(currentTheme));

el("open-external").onclick = async () => {
  const problem = await window.hp.openDashboardExternally();
  if (problem) appendLog(problem);
};

el("build-run").onclick = async () => {
  const button = el<HTMLButtonElement>("build-run");
  button.disabled = true;
  el("build-state").textContent = "building…";
  el("log").hidden = false;
  const result = await window.hp.build();
  el("build-state").textContent = result.code === 0 ? "done" : `failed (${result.error ?? result.code})`;
  button.disabled = false;
  await refreshState();
  await renderSummary();
};

el("import-choose").onclick = () => void chooseImport();
el("archive-import-choose").onclick = () => void chooseImport(true);

window.addEventListener("message", (event: MessageEvent) => {
  const frame = el<HTMLIFrameElement>("dashboard");
  if (event.source !== frame.contentWindow) return;
  const message = event.data as { type?: string; tab?: string } | null;
  if (message?.type === "healthpilot:navigate" && message.tab === "sources") showTab("import");
});

el("events-add").onclick = () => {
  events.push(Object.fromEntries(EVENT_COLUMNS.map((column) => [column, ""])));
  renderEvents();
};

el("events-save").onclick = async () => {
  await window.hp.saveEvents(events);
  el("events-state").textContent = `saved ${events.length} rows — rebuild to see them on the timeline`;
};

el("notes-save").onclick = async () => {
  await window.hp.saveNotes(el<HTMLTextAreaElement>("notes").value);
  el("notes-state").textContent = "saved — rebuild to include them in the case study";
};

el("doctor-run").onclick = () => void renderDoctor();

el("root-choose").onclick = async () => {
  state = await window.hp.chooseRoot();
  await refreshState();
  await renderSummary();
  await renderDoctor();
};

void (async () => {
  await refreshState();
  await renderSummary();
})();
