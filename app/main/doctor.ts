// The Doctor tab: the CLI's own checks (so both front doors agree) plus what only the app knows.
import { run } from "./proc";
import { isRoot, type Paths } from "./roots";
import { invocation } from "./runtime";

export type Check = { check: string; ok: boolean; hint?: string };

export async function doctor(paths: Paths): Promise<Check[]> {
  const checks: Check[] = [
    { check: `data folder ${paths.root}`, ok: isRoot(paths.root), hint: "choose or create a Clippi-Health data folder" },
  ];

  const command = invocation(paths, "query", ["--json", "doctor"]);
  checks.push({ check: "bundled record engine", ok: Boolean(command), hint: "reinstall Clippi-Health" });
  let merged = false;
  if (command) {
    const { code, stdout, stderr } = await run(command.cmd, command.args, { cwd: paths.root, env: command.env });
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

  if (!merged) checks.push({ check: "record engine doctor", ok: false, hint: "reinstall Clippi-Health or review the activity log" });
  return checks;
}
