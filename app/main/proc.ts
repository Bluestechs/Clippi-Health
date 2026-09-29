// Running the Python builder and query CLI with their output streamed to the UI.
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { delimiter, join } from "node:path";

export type LogSink = (line: string) => void;

/** `output` is the merged stream, in the order the log drawer showed it; `stdout` is what a
 *  command's JSON must be parsed from, and `stderr` is what a failure can be explained with. */
export type RunResult = { code: number; output: string; stdout: string; stderr: string };

/**
 * A GUI process started from Finder inherits a bare PATH, so the tools the app shells out to have
 * to be found by hand in the places package managers put them.
 */
export function findTool(name: string): string | null {
  const dirs = [
    ...(process.env.PATH ?? "").split(delimiter),
    "/opt/homebrew/bin",
    "/usr/local/bin",
    "/usr/bin",
  ];
  for (const dir of dirs) {
    if (!dir) continue;
    const candidate = join(dir, name);
    if (existsSync(candidate)) return candidate;
  }
  return null;
}

export function delay(ms: number): Promise<void> {
  const { promise, resolve } = Promise.withResolvers<void>();
  setTimeout(resolve, ms);
  return promise;
}

export function run(
  cmd: string,
  args: string[],
  opts: { cwd: string; onLine?: LogSink; env?: Record<string, string> },
): Promise<RunResult> {
  const { promise, resolve, reject } = Promise.withResolvers<RunResult>();
  const child = spawn(cmd, args, { cwd: opts.cwd, env: { ...process.env, ...opts.env } });
  let output = "";
  let stdout = "";
  let stderr = "";
  let pending = "";
  const feed = (chunk: Buffer) => {
    const text = chunk.toString("utf8");
    output += text;
    if (!opts.onLine) return;
    pending += text;
    const lines = pending.split("\n");
    pending = lines.pop() ?? "";
    for (const line of lines) opts.onLine(line);
  };
  child.stdout.on("data", (chunk: Buffer) => {
    stdout += chunk.toString("utf8");
    feed(chunk);
  });
  child.stderr.on("data", (chunk: Buffer) => {
    stderr += chunk.toString("utf8");
    feed(chunk);
  });
  child.on("error", reject);
  child.on("close", (code) => {
    if (pending && opts.onLine) opts.onLine(pending);
    resolve({ code: code ?? -1, output, stdout, stderr });
  });
  return promise;
}
