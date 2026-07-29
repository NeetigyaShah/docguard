import { useEffect, useMemo, useState } from "react";
import type { Bundle, Feature } from "./types";

const TABS = [
  "Overview", "Features", "Milestones", "Tests", "Agents",
  "Git / Worktrees", "Infrastructure", "Blockers", "Activity",
] as const;
type Tab = (typeof TABS)[number];

function statusClass(s: string): string {
  const k = s.toUpperCase();
  if (k === "PASSED" || k === "MERGED") return "ok";
  if (k === "IN_PROGRESS" || k === "TESTING") return "prog";
  if (k === "BLOCKED" || k === "BLOCKED_EXTERNAL") return "blocked";
  if (k === "FAILED") return "fail";
  if (k === "PARTIAL") return "partial";
  return "planned";
}

function Badge({ s }: { s: string }) {
  return <span className={`badge ${statusClass(s)}`}>{s}</span>;
}

export function App() {
  const [bundle, setBundle] = useState<Bundle | null>(null);
  const [tab, setTab] = useState<Tab>("Overview");
  const [err, setErr] = useState<string>("");

  const load = () =>
    fetch("./orchestrator.json?" + Date.now())
      .then((r) => r.json())
      .then(setBundle)
      .catch((e) => setErr(String(e)));

  useEffect(() => {
    load();
  }, []);

  if (err) return <div className="app"><p className="err">Failed to load orchestrator.json: {err}</p></div>;
  if (!bundle) return <div className="app"><p>Loading…</p></div>;

  return (
    <div className="shell">
      <header className="topbar">
        <div className="title">
          <span className="logo">📘</span>
          <div>
            <div className="tname">DocGuard</div>
            <div className="tsub">Self-Healing Documentation CI</div>
          </div>
        </div>
        <div className="topmeta">
          <span className="pill">phase {String((bundle.state as Record<string, unknown>).current_phase ?? "—")}</span>
          <button className="refresh" onClick={load}>↻ Refresh</button>
          <a className="ghlink" href="https://github.com/NeetigyaShah/docguard" target="_blank" rel="noreferrer">
            GitHub ↗
          </a>
        </div>
      </header>
      <div className="app">
        <aside className="side">
          <nav>
            {TABS.map((t) => (
              <button key={t} className={t === tab ? "active" : ""} onClick={() => setTab(t)}>
                {t}
              </button>
            ))}
          </nav>
          <div className="gen">state @ {new Date(bundle.generatedAt).toLocaleTimeString()}</div>
        </aside>
        <main className="main">
          <View tab={tab} b={bundle} />
        </main>
      </div>
    </div>
  );
}

function View({ tab, b }: { tab: Tab; b: Bundle }) {
  switch (tab) {
    case "Overview": return <Overview b={b} />;
    case "Features": return <Features b={b} />;
    case "Milestones": return <Milestones b={b} />;
    case "Tests": return <Tests b={b} />;
    case "Agents": return <Agents b={b} />;
    case "Git / Worktrees": return <Git b={b} />;
    case "Infrastructure": return <Infra b={b} />;
    case "Blockers": return <Blockers b={b} />;
    case "Activity": return <ActivityView b={b} />;
  }
}

function count(features: Feature[], pred: (f: Feature) => boolean) {
  return features.filter(pred).length;
}

function Overview({ b }: { b: Bundle }) {
  const f = b.features;
  const st = b.state as Record<string, unknown>;
  const passed = count(f, (x) => ["PASSED", "MERGED"].includes(x.status));
  const stats = [
    ["Passed", passed, "ok"],
    ["In progress", count(f, (x) => ["IN_PROGRESS", "TESTING"].includes(x.status)), "prog"],
    ["Blocked", count(f, (x) => x.status.startsWith("BLOCKED")), "blocked"],
    ["Failed", count(f, (x) => x.status === "FAILED"), "fail"],
    ["Partial", count(f, (x) => x.status === "PARTIAL"), "partial"],
    ["Planned", count(f, (x) => x.status === "PLANNED"), "planned"],
  ] as const;
  const testsPass = b.tests.filter((t) => t.status === "PASS").length;

  return (
    <>
      <h1>Overview</h1>
      <div className="cards">
        <div className="card big">
          <div className="metric">{Math.round((passed / (f.length || 1)) * 100)}%</div>
          <div className="label">completion ({passed}/{f.length} features)</div>
        </div>
        <div className="card">
          <div className="metric">{String(st.current_phase ?? "-")}</div>
          <div className="label">current phase</div>
        </div>
        <div className="card">
          <div className="metric">{testsPass}/{b.tests.length}</div>
          <div className="label">test records PASS</div>
        </div>
      </div>
      <div className="statrow">
        {stats.map(([label, n, cls]) => (
          <div key={label} className={`stat ${cls}`}>
            <div className="n">{n}</div>
            <div>{label}</div>
          </div>
        ))}
      </div>
      <h2>Phase progress</h2>
      <div className="phases">
        {b.milestones.map((m) => (
          <div key={m.phase} className={`phase ${statusClass(m.status)}`}>
            <div className="pn">Phase {m.phase}</div>
            <div className="pname">{m.name}</div>
            <Badge s={m.status} />
            <div className="ptests">{m.passed_tests}/{m.total_tests} tests</div>
          </div>
        ))}
      </div>
      <div className="next"><b>Next action:</b> {String(st.next_action ?? "—")}</div>
    </>
  );
}

function Features({ b }: { b: Bundle }) {
  return (
    <>
      <h1>Features ({b.features.length})</h1>
      <table>
        <thead><tr><th>ID</th><th>Name</th><th>Ph</th><th>Status</th><th>Deps</th><th>Branch</th><th>Worktree</th><th>Blockers</th></tr></thead>
        <tbody>
          {b.features.map((f) => (
            <tr key={f.id}>
              <td className="mono">{f.id}</td>
              <td>{f.name}</td>
              <td>{f.phase}</td>
              <td><Badge s={f.status} /></td>
              <td className="mono small">{f.deps.join(", ") || "—"}</td>
              <td className="mono small">{f.branch}</td>
              <td className="mono small">{f.worktree}</td>
              <td className="mono small">{(f.blockers || []).join(", ") || "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

function Milestones({ b }: { b: Bundle }) {
  return (
    <>
      <h1>Milestones</h1>
      <table>
        <thead><tr><th>Phase</th><th>Name</th><th>Status</th><th>Gate</th><th>Tests</th></tr></thead>
        <tbody>
          {b.milestones.map((m) => (
            <tr key={m.phase}>
              <td>{m.phase}</td><td>{m.name}</td><td><Badge s={m.status} /></td>
              <td className="small">{m.gate}</td><td>{m.passed_tests}/{m.total_tests}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

function Tests({ b }: { b: Bundle }) {
  const pass = b.tests.filter((t) => t.status === "PASS").length;
  return (
    <>
      <h1>Tests — {pass}/{b.tests.length} PASS</h1>
      <table>
        <thead><tr><th>ID</th><th>Ph</th><th>Kind</th><th>Description</th><th>Expected</th><th>Actual</th><th>Result</th></tr></thead>
        <tbody>
          {b.tests.map((t) => (
            <tr key={t.id} className={t.status === "FAIL" ? "rowfail" : ""}>
              <td className="mono">{t.id}</td><td>{t.phase}</td>
              <td className="small">{t.kind}</td><td className="small">{t.description}</td>
              <td className="mono small">{t.expected}</td>
              <td className="mono small">{t.actual}</td>
              <td><Badge s={t.status} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

function Agents({ b }: { b: Bundle }) {
  return (
    <>
      <h1>Agents</h1>
      {b.agents.length === 0 && <p>No subagents recorded.</p>}
      <table>
        <thead><tr><th>ID</th><th>Feature</th><th>Task</th><th>Status</th><th>Report</th></tr></thead>
        <tbody>
          {b.agents.map((a) => (
            <tr key={a.id}>
              <td className="mono">{a.id}</td><td>{a.feature}</td>
              <td className="small">{a.task}</td><td><Badge s={a.status} /></td>
              <td className="small">{a.report || "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

function Git({ b }: { b: Bundle }) {
  const byBranch = new Map<string, Feature[]>();
  b.features.forEach((f) => {
    const arr = byBranch.get(f.branch) || [];
    arr.push(f);
    byBranch.set(f.branch, arr);
  });
  return (
    <>
      <h1>Git / Worktrees</h1>
      {[...byBranch.entries()].map(([branch, feats]) => (
        <div key={branch} className="card wide">
          <div className="mono b">{branch}</div>
          <div className="small">
            worktrees: {[...new Set(feats.map((f) => f.worktree))].join(", ")}
          </div>
          <div className="small">
            features: {feats.map((f) => f.id).join(", ")}
          </div>
        </div>
      ))}
    </>
  );
}

const INFRA = [
  ["Python 3.11+", "core runtime", "AVAILABLE_LOCAL"],
  ["git CLI", "diffs / branches", "AVAILABLE_LOCAL"],
  ["Node / npm", "dashboard", "AVAILABLE_LOCAL"],
  ["Docker", "package the Action", "AVAILABLE_LOCAL"],
  ["OpenAI API", "real LLM + embeddings", "OPTIONAL"],
  ["Anthropic API", "real LLM", "OPTIONAL"],
  ["GitHub token", "real PR / comment", "FREE_TIER"],
];

function Infra({ b }: { b: Bundle }) {
  return (
    <>
      <h1>Infrastructure</h1>
      <table>
        <thead><tr><th>Requirement</th><th>Purpose</th><th>Class</th></tr></thead>
        <tbody>
          {INFRA.map(([r, p, c]) => (
            <tr key={r}><td>{r}</td><td className="small">{p}</td><td><Badge s={c} /></td></tr>
          ))}
        </tbody>
      </table>
      <h2>External blockers</h2>
      {b.blockers.map((bl) => (
        <div key={bl.id} className="small">• {bl.title} — {bl.resolved ? "resolved" : "open"}</div>
      ))}
    </>
  );
}

function Blockers({ b }: { b: Bundle }) {
  return (
    <>
      <h1>Blockers</h1>
      {b.blockers.length === 0 && <p>None.</p>}
      {b.blockers.map((bl) => (
        <div key={bl.id} className={`card wide ${bl.resolved ? "ok" : "blocked"}`}>
          <div className="b">{bl.title} <Badge s={bl.type} /></div>
          <div className="small">{bl.detail}</div>
          <div className="small"><b>You provide:</b> {bl.user_action}</div>
          <div className="small mono">affects: {bl.affects.join(", ")}</div>
        </div>
      ))}
    </>
  );
}

function ActivityView({ b }: { b: Bundle }) {
  const feed = useMemo(() => b.activity.slice(0, 200), [b.activity]);
  return (
    <>
      <h1>Activity</h1>
      <div className="feed">
        {feed.map((a, i) => (
          <div key={i} className="event">
            <span className="ts">{a.ts}</span>
            <span className="mono actor">{a.actor}</span>
            <span className="ft">{a.feature}</span>
            <span>{a.action}</span>
            <span className="res">{a.result}</span>
          </div>
        ))}
      </div>
    </>
  );
}
