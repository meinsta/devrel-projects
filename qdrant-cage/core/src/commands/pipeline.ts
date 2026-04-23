import { readFileSync, writeFileSync, existsSync, mkdirSync } from "fs";
import { execSync } from "child_process";
import path from "path";

export type PipelineState =
  | "spec-created"
  | "spec-approved"
  | "worktree-prepared"
  | "implemented"
  | "tests-passing"
  | "reviewed"
  | "merged";

export interface FeatureEntry {
  state: PipelineState;
  spec?: string;
  branch?: string;
  worktree?: string;
  created: string;
  updated: string;
}

interface PipelineData {
  features: Record<string, FeatureEntry>;
}

// valid forward transitions
const FORWARD_TRANSITIONS: Record<PipelineState, PipelineState[]> = {
  "spec-created": ["spec-approved"],
  "spec-approved": ["worktree-prepared"],
  "worktree-prepared": ["implemented"],
  "implemented": ["tests-passing"],
  "tests-passing": ["reviewed"],
  "reviewed": ["merged"],
  "merged": [],
};

// valid backward transitions (regression)
const BACKWARD_TRANSITIONS: Record<PipelineState, PipelineState[]> = {
  "spec-created": [],
  "spec-approved": [],
  "worktree-prepared": [],
  "implemented": [],
  "tests-passing": ["implemented"],
  "reviewed": ["implemented"],
  "merged": [],
};

function getValidTransitions(state: PipelineState): PipelineState[] {
  return [
    ...(FORWARD_TRANSITIONS[state] || []),
    ...(BACKWARD_TRANSITIONS[state] || []),
  ];
}

// resolve to main worktree's .cage/pipeline.json
function getPipelinePath(): string {
  let mainWorktree: string;
  try {
    // git worktree list --porcelain gives the main worktree first
    const output = execSync("git worktree list --porcelain", { encoding: "utf-8" });
    const firstLine = output.split("\n")[0];
    mainWorktree = firstLine.replace("worktree ", "");
  } catch {
    mainWorktree = process.cwd();
  }

  const cageDir = path.join(mainWorktree, ".cage");
  if (!existsSync(cageDir)) mkdirSync(cageDir, { recursive: true });
  return path.join(cageDir, "pipeline.json");
}

function readPipeline(): PipelineData {
  const pipelinePath = getPipelinePath();
  if (!existsSync(pipelinePath)) {
    return { features: {} };
  }
  try {
    return JSON.parse(readFileSync(pipelinePath, "utf-8"));
  } catch {
    return { features: {} };
  }
}

function writePipeline(data: PipelineData): void {
  const pipelinePath = getPipelinePath();
  writeFileSync(pipelinePath, JSON.stringify(data, null, 2) + "\n");
}

export async function pipelineGet(featureName: string): Promise<void> {
  if (!featureName) {
    console.error("error: feature name required");
    process.exit(1);
  }

  const data = readPipeline();
  const feature = data.features[featureName];

  if (!feature) {
    console.error(`error: feature '${featureName}' not found`);
    console.error("run 'cage-core pipeline list' to see all features");
    process.exit(1);
  }

  console.log(JSON.stringify(feature, null, 2));
}

export async function pipelineTransition(featureName: string, newState: string): Promise<void> {
  if (!featureName || !newState) {
    console.error("error: feature name and new state required");
    process.exit(1);
  }

  const validStates: PipelineState[] = [
    "spec-created", "spec-approved", "worktree-prepared",
    "implemented", "tests-passing", "reviewed", "merged",
  ];

  if (!validStates.includes(newState as PipelineState)) {
    console.error(`error: invalid state '${newState}'`);
    console.error(`valid states: ${validStates.join(", ")}`);
    process.exit(1);
  }

  const data = readPipeline();
  const now = new Date().toISOString();

  // create feature if it doesn't exist (for spec-created)
  if (!data.features[featureName]) {
    if (newState !== "spec-created") {
      console.error(`error: feature '${featureName}' does not exist. create it by transitioning to 'spec-created' first`);
      process.exit(1);
    }
    data.features[featureName] = {
      state: "spec-created",
      created: now,
      updated: now,
    };
    writePipeline(data);
    console.log(`feature '${featureName}' created in state 'spec-created'`);
    return;
  }

  const feature = data.features[featureName];
  const currentState = feature.state;
  const validNext = getValidTransitions(currentState);

  if (!validNext.includes(newState as PipelineState)) {
    console.error(`error: cannot transition '${featureName}' from '${currentState}' to '${newState}'`);
    if (validNext.length > 0) {
      console.error(`valid transitions from '${currentState}': ${validNext.join(", ")}`);
    } else {
      console.error(`'${currentState}' is a terminal state. use 'cage-core pipeline reset ${featureName}' to start over`);
    }
    process.exit(1);
  }

  feature.state = newState as PipelineState;
  feature.updated = now;

  // set branch name on worktree-prepared
  if (newState === "worktree-prepared") {
    feature.branch = `feat/${featureName}`;
  }

  writePipeline(data);
  console.log(`${featureName}: ${currentState} -> ${newState}`);
}

export async function pipelineList(): Promise<void> {
  const data = readPipeline();
  const features = Object.entries(data.features);

  if (features.length === 0) {
    console.log("no features in pipeline");
    return;
  }

  console.log("features:");
  for (const [name, feature] of features) {
    const age = timeSince(feature.updated);
    console.log(`  ${name}: ${feature.state} (${age})`);
    if (feature.branch) console.log(`    branch: ${feature.branch}`);
  }
}

export async function pipelineReset(featureName: string): Promise<void> {
  if (!featureName) {
    console.error("error: feature name required");
    process.exit(1);
  }

  const data = readPipeline();
  if (!data.features[featureName]) {
    console.error(`error: feature '${featureName}' not found`);
    process.exit(1);
  }

  const oldState = data.features[featureName].state;
  data.features[featureName].state = "spec-created";
  data.features[featureName].updated = new Date().toISOString();
  writePipeline(data);
  console.log(`${featureName}: ${oldState} -> spec-created (reset)`);
}

function timeSince(isoDate: string): string {
  const diff = Date.now() - new Date(isoDate).getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}
