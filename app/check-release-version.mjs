import { readFileSync } from "node:fs";

const pkg = JSON.parse(readFileSync(new URL("./package.json", import.meta.url), "utf8"));
const expected = `v${pkg.version}`;
const actual = process.env.GITHUB_REF_NAME;
if (!actual) throw new Error("GITHUB_REF_NAME is not set");
if (actual !== expected) throw new Error(`Release tag ${actual} does not match app version ${expected}`);
console.log(`Release tag matches app version: ${actual}`);
