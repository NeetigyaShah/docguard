export interface Feature {
  id: string;
  name: string;
  phase: number;
  deps: string[];
  status: string;
  agent: string | null;
  branch: string;
  worktree: string;
  acceptance?: string;
  tests?: string[];
  merge_status?: string;
  blockers?: string[];
  commit?: string | null;
}

export interface Milestone {
  phase: number;
  name: string;
  status: string;
  gate: string;
  passed_tests: number;
  total_tests: number;
}

export interface Blocker {
  id: string;
  type: string;
  title: string;
  detail: string;
  user_action: string;
  affects: string[];
  resolved: boolean;
}

export interface Agent {
  id: string;
  feature: string;
  task: string;
  status: string;
  worktree: string;
  branch: string;
  commit: string | null;
  report: string | null;
}

export interface TestRecord {
  id: string;
  phase: number;
  kind?: string;
  description: string;
  input: string;
  expected: string;
  actual: string;
  status: string;
}

export interface Activity {
  ts: string;
  actor: string;
  feature: string;
  action: string;
  result: string;
  commit?: string;
}

export interface Bundle {
  state: Record<string, unknown>;
  features: Feature[];
  milestones: Milestone[];
  dependencies: { dag: Record<string, string[]> };
  blockers: Blocker[];
  agents: Agent[];
  tests: TestRecord[];
  activity: Activity[];
  generatedAt: string;
}
