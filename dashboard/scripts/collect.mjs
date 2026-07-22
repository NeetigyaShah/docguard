// Bundle the authoritative .orchestrator state into a single JSON the app fetches.
// No dependencies; safe against missing/empty files.
import { readFileSync, existsSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const orch = join(here, "..", "..", ".orchestrator");
const outDir = join(here, "..", "public");

function readJson(name, fallback) {
  const p = join(orch, name);
  if (!existsSync(p)) return fallback;
  try {
    return JSON.parse(readFileSync(p, "utf-8"));
  } catch {
    return fallback;
  }
}

function readActivity() {
  const p = join(orch, "activity.jsonl");
  if (!existsSync(p)) return [];
  return readFileSync(p, "utf-8")
    .split(/\r?\n/)
    .filter(Boolean)
    .map((l) => {
      try {
        return JSON.parse(l);
      } catch {
        return null;
      }
    })
    .filter(Boolean);
}

const bundle = {
  state: readJson("state.json", {}),
  features: readJson("features.json", { features: [] }).features || [],
  milestones: readJson("milestones.json", { milestones: [] }).milestones || [],
  dependencies: readJson("dependencies.json", { dag: {} }),
  blockers: readJson("blockers.json", { blockers: [] }).blockers || [],
  agents: readJson("agents.json", { agents: [] }).agents || [],
  tests: readJson("tests.json", { records: [] }).records || [],
  activity: readActivity().reverse(), // most recent first
  generatedAt: new Date().toISOString(),
};

mkdirSync(outDir, { recursive: true });
writeFileSync(join(outDir, "orchestrator.json"), JSON.stringify(bundle, null, 2));
console.log(
  `collect: ${bundle.features.length} features, ${bundle.tests.length} test records, ${bundle.activity.length} activity events`
);
