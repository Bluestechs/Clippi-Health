// `hp add` in TypeScript: Apple Health exports go to raw/apple, local email/document ZIPs to
// raw/imports, and loose files/folders to raw/other. The selected originals are copied unchanged.
import { copyFileSync, cpSync, existsSync, mkdirSync, readdirSync, renameSync, rmSync, statSync, utimesSync } from "node:fs";
import { basename, extname, join, resolve } from "node:path";
import type { Paths } from "./roots";
import { zipEntryNames } from "./zip";

export type ImportItem = {
  source: string;
  kind: "apple" | "portal" | "archive" | "folder" | "file";
  dest: string;
  note: string;
};

export type ImportPlan = {
  items: ImportItem[];
  /** Apple exports already in raw/apple that a new one would replace. */
  replaced: string[];
  skipped: string[];
};

function timestamp(): string {
  const now = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}-${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}`;
}

const ARCHIVE_EXTENSIONS = new Set([
  ".mbox", ".eml", ".pdf", ".docx", ".html", ".htm", ".txt", ".md", ".xml",
  ".jpg", ".jpeg", ".png", ".tif", ".tiff", ".heic",
]);
const OUTLOOK_EXTENSIONS = new Set([".pst", ".olm", ".msg"]);

function memberExtension(name: string): string {
  const leaf = name.split("/").at(-1) ?? name;
  return extname(leaf).toLowerCase();
}

export function planImport(paths: Paths, inputs: string[]): ImportPlan {
  const items: ImportItem[] = [];
  const skipped: string[] = [];
  const replaced: string[] = [];
  let sawApple = false;

  for (const input of inputs) {
    const path = resolve(input);
    if (!existsSync(path)) {
      skipped.push(`${path} does not exist`);
      continue;
    }
    const stats = statSync(path);
    if (stats.isFile() && extname(path).toLowerCase() === ".zip") {
      const names = zipEntryNames(path);
      if (names?.some((n) => n.endsWith("apple_health_export/export.xml"))) {
        items.push({
          source: path,
          kind: "apple",
          dest: join(paths.rawApple, basename(path)),
          note: "Apple Health export — device data is parsed on the next build (~30 s)",
        });
        sawApple = true;
        continue;
      }
      if (names?.some((name) => {
        const normalized = `/${name.replaceAll("\\", "/")}`.toUpperCase();
        const leaf = normalized.split("/").at(-1) ?? "";
        return normalized.includes("/IHE_XDM/") && leaf.startsWith("DOC") && leaf.endsWith(".XML");
      })) {
        items.push({
          source: path,
          kind: "portal",
          dest: join(paths.rawOther, basename(path)),
          note: "MyChart C-CDA record ZIP — parsed locally on the next build",
        });
        continue;
      }
      const extensions = new Set((names ?? []).map(memberExtension));
      const supported = [...extensions].some((extension) => ARCHIVE_EXTENSIONS.has(extension));
      const outlook = [...extensions].filter((extension) => OUTLOOK_EXTENSIONS.has(extension));
      if (supported) {
        items.push({
          source: path,
          kind: "archive",
          dest: join(paths.rawImports, basename(path)),
          note: outlook.length
            ? "Local email/document archive — supported files will be parsed offline; PST/OLM/MSG members will be retained but skipped"
            : "Local email/document archive — parsed offline on the next build",
        });
        continue;
      }
      if (outlook.length) {
        skipped.push(`${path} contains only ${outlook.join(", ")} Outlook files. Export messages as .eml files, put them in a folder, and ZIP that folder.`);
        continue;
      }
      if (names !== null) {
        skipped.push(`${path} has no supported email or document files`);
        continue;
      }
    }
    if (stats.isDirectory()) {
      items.push({
        source: path,
        kind: "folder",
        dest: join(paths.rawOther, basename(path)),
        note: existsSync(join(path, "IHE_XDM")) ? "C-CDA record download" : "folder",
      });
      continue;
    }
    items.push({ source: path, kind: "file", dest: join(paths.rawOther, basename(path)), note: "file" });
  }

  if (sawApple && existsSync(paths.rawApple)) {
    const incoming = new Set(items.filter((i) => i.kind === "apple").map((i) => i.dest));
    for (const name of readdirSync(paths.rawApple)) {
      const existing = join(paths.rawApple, name);
      if (name.toLowerCase().endsWith(".zip") && !incoming.has(existing)) replaced.push(existing);
    }
  }
  return { items, replaced, skipped };
}

/** Carries out a plan; returns one log line per action. */
export function applyImport(paths: Paths, plan: ImportPlan, replaceApple: boolean): string[] {
  const log: string[] = [];
  mkdirSync(paths.rawApple, { recursive: true });
  mkdirSync(paths.rawImports, { recursive: true });
  mkdirSync(paths.rawOther, { recursive: true });

  if (replaceApple && plan.replaced.length) {
    mkdirSync(paths.rawPrevious, { recursive: true });
    for (const old of plan.replaced) {
      const moved = join(paths.rawPrevious, `${basename(old, ".zip")}-${timestamp()}.zip`);
      renameSync(old, moved);
      log.push(`kept previous Apple export → ${moved.slice(paths.root.length + 1)}`);
    }
  }

  for (const item of plan.items) {
    if (item.kind === "folder") {
      if (existsSync(item.dest)) rmSync(item.dest, { recursive: true, force: true });
      cpSync(item.source, item.dest, { recursive: true, preserveTimestamps: true });
    } else {
      copyFileSync(item.source, item.dest);
      const stats = statSync(item.source); // the build caches Apple device data by zip size + mtime
      utimesSync(item.dest, stats.atime, stats.mtime);
    }
    log.push(`${item.note} → ${item.dest.slice(paths.root.length + 1)}`);
  }
  return log;
}
