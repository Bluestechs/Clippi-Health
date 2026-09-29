import { app } from "electron";
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import type { Paths } from "./roots";
import { findTool } from "./proc";

export type RuntimeArea = "build" | "query" | "smart" | "demo";

export type Invocation = {
  cmd: string;
  args: string[];
  env: Record<string, string>;
};

/** Use source Python while developing and the bundled native helper after installation. */
export function invocation(paths: Paths, area: RuntimeArea, args: string[] = []): Invocation | null {
  const env = { CLIPPI_HEALTH_ROOT: paths.root };
  if (app.isPackaged) {
    return existsSync(paths.runtime) ? { cmd: paths.runtime, args: [area, ...args], env } : null;
  }
  const python = findTool("python3") ?? findTool("python");
  if (!python) return null;
  const script = area === "demo" ? join(dirname(paths.builder), "demo_data.py")
    : area === "build" ? paths.builder : area === "query" ? paths.cli : paths.smartConnector;
  return existsSync(script) ? { cmd: python, args: [script, ...args], env } : null;
}
