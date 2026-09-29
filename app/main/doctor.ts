// The Doctor tab: the CLI's own checks (so both front doors agree) plus what only the app knows.
import { existsSync } from "node:fs";
import { findTool, run } from "./proc";
import { isRoot, type Paths } from "./roots";

export type Check = { check: string; ok: boolean; hint?: string };

export async function doctor(paths: Paths): Promise<Check[]> {
  const checks: Check[] = [
    { check: `data folder ${paths.root}`, ok: isRoot(paths.root), hint: "pick a folder that contains healthpilot.py" },
  ];

  const python = findTool("python3");
  checks.push({ check: "python3 (record builder)", ok: Boolean(python), hint: "xcode-select --install, or install Python 3.9+" });
  let merged = false;
  if (python && existsSync(paths.cli)) {
    // `--json` is a flag on `hp` itself, not on the subcommand: `hp --json doctor`. Only stdout is
    // parsed, so a warning on stderr cannot make the CLI's checks disappear.
    const { code, stdout, stderr } = await run(python, [paths.cli, "--json", "doctor"], { cwd: paths.root });
    const complaint = stderr.trimEnd().split("\n").at(-1)?.trim();
    if (code === 0) {
      try {
        checks.push(...(JSON.parse(stdout) as Check[]));
        merged = true;
      } catch {
        checks.push({ check: "hp doctor", ok: false, hint: `the CLI's checks were not JSON${complaint ? `: ${complaint}` : ""}` });
      }
    } else {
      checks.push({ check: "hp doctor", ok: false, hint: complaint || `the CLI exited ${code}` });
    }
  }

  if (!merged) checks.push({ check: "hp doctor", ok: false, hint: "run ./hp --json doctor in the data folder" });
  return checks;
}
