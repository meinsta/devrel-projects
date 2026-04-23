import { existsSync, mkdirSync, writeFileSync, readFileSync } from "fs";
import { execSync } from "child_process";
import path from "path";

const TEMPLATES: Record<string, () => Record<string, string>> = {
  default: generateDefaultTemplate,
  fullstack: generateFullstackTemplate,
  api: generateApiTemplate,
  monorepo: generateMonorepoTemplate,
};

export async function init(targetDir: string, template: string): Promise<void> {
  const absTarget = path.resolve(targetDir);
  const projectName = path.basename(absTarget);

  if (!TEMPLATES[template]) {
    console.error(`unknown template: ${template}`);
    console.error(`available templates: ${Object.keys(TEMPLATES).join(", ")}`);
    process.exit(1);
  }

  // check git
  try {
    execSync("git rev-parse --git-dir", { cwd: existsSync(absTarget) ? absTarget : process.cwd(), stdio: "ignore" });
  } catch {
    console.error("error: not a git repository. run 'git init' first");
    process.exit(1);
  }

  console.log(`initializing CAGE in ${absTarget} (template: ${template})\n`);

  const files = TEMPLATES[template]();
  let created = 0;
  let skipped = 0;

  for (const [relativePath, content] of Object.entries(files)) {
    const fullPath = path.join(absTarget, relativePath);
    const dir = path.dirname(fullPath);

    if (!existsSync(dir)) mkdirSync(dir, { recursive: true });

    if (existsSync(fullPath)) {
      console.log(`  skip: ${relativePath} (already exists)`);
      skipped++;
    } else {
      // replace PROJECT_NAME placeholder
      const finalContent = content.replace(/\{\{PROJECT_NAME\}\}/g, projectName);
      writeFileSync(fullPath, finalContent);
      console.log(`  created: ${relativePath}`);
      created++;
    }
  }

  // create .cage directory
  mkdirSync(path.join(absTarget, ".cage"), { recursive: true });

  console.log(`\n${created} files created, ${skipped} skipped`);
  console.log("\nnext steps:");
  console.log("  pre-commit install");
  console.log("  cage index");
}

function generateDefaultTemplate(): Record<string, string> {
  return {
    ...sharedContracts(),
    ...docsStructure(),
    ...cageRulesDefault(),
    ...preCommitConfig(),
    ...claudeMd("default"),
    ...agentsMd("default"),
    ...gitignoreAdditions(),
  };
}

function generateFullstackTemplate(): Record<string, string> {
  return {
    ...sharedContracts(),
    ...docsStructure(),
    ...cageRulesFullstack(),
    ...preCommitConfig(),
    ...claudeMd("fullstack"),
    ...agentsMd("fullstack"),
    ...gitignoreAdditions(),
    ...cageInfraFullstack(),
  };
}

function generateApiTemplate(): Record<string, string> {
  return {
    ...sharedContracts(),
    ...docsStructure(),
    ...cageRulesApi(),
    ...preCommitConfig(),
    ...claudeMd("api"),
    ...agentsMd("api"),
    ...gitignoreAdditions(),
    ...cageInfraApi(),
  };
}

function generateMonorepoTemplate(): Record<string, string> {
  return {
    ...sharedContracts(),
    ...docsStructure(),
    ...cageRulesDefault(),
    ...preCommitConfig(),
    ...claudeMd("monorepo"),
    ...agentsMd("monorepo"),
    ...gitignoreAdditions(),
  };
}

// shared building blocks

function sharedContracts(): Record<string, string> {
  return {
    "shared/domain-values.json": JSON.stringify({
      _comment: "centralized domain values consumed by all services. pre-commit hooks enforce sync.",
      values: {},
    }, null, 2) + "\n",
    "shared/api-field-snapshots.json": JSON.stringify({
      _comment: "API response shape snapshots. pre-commit hooks enforce coverage.",
      endpoints: {},
    }, null, 2) + "\n",
    "shared/schemas.json": JSON.stringify({
      _comment: "data schemas shared across services. pre-commit hooks enforce sync.",
      schemas: {},
    }, null, 2) + "\n",
  };
}

function docsStructure(): Record<string, string> {
  return {
    "docs/features/README.md": `# features\n\npermanent implementation knowledge lives here. one file per feature.\nif you learned something painful to fix a bug or understand a subsystem,\nwrite it back here before the task is considered done.\n`,
    "docs/features/implementation-decisions/README.md": `# implementation decisions\n\neach feature gets a decisions doc explaining WHY choices were made.\nthe /cage-review skill reads these during code review.\n`,
    "docs/designs/README.md": `# designs\n\ntemporary technical plans live here. delete after implementation.\neach design doc should reference the feature it implements.\n`,
    "docs/bugs.md": `# active bugs\n\nunresolved issues go here. move to bugs-archive/ when resolved.\n\n## template\n\n### [BUG-NNN] short description\n- **reported**: YYYY-MM-DD\n- **severity**: critical | high | medium | low\n- **surfaces**: which services/pages affected\n- **repro**: steps to reproduce\n- **root cause**: (fill in during investigation)\n- **fix**: (fill in when resolved)\n`,
    "docs/bugs-archive/README.md": `# resolved bugs\n\nbugs move here from ../bugs.md when resolved.\nkeep for institutional knowledge.\n`,
  };
}

function cageRulesDefault(): Record<string, string> {
  return {
    "cage.rules": `# cage execution policy
# format: ACTION PATTERN [ALTERNATIVE]
#   block   - reject outright
#   prompt  - ask user before executing
#   allow   - always allow (default for unlisted commands)

# destructive operations - require confirmation
prompt  rm -rf
prompt  git merge
prompt  git push
prompt  git reset --hard
prompt  git push --force
prompt  git checkout .
prompt  git clean

# infrastructure - use cage commands
block   lsof                          cage infra stop
block   kill                          cage infra stop
block   killall                       cage infra stop
block   pkill                         cage infra stop
`,
  };
}

function cageRulesFullstack(): Record<string, string> {
  return {
    "cage.rules": `# cage execution policy
# format: ACTION PATTERN [ALTERNATIVE]

# build commands - use scripted lifecycle
block   next build                    cage infra start
block   npx next build                cage infra start
block   npm run build                 cage infra start

# infrastructure - use cage commands
block   lsof                          cage infra stop
block   kill                          cage infra stop
block   killall                       cage infra stop
block   pkill                         cage infra stop

# destructive operations - require confirmation
prompt  rm -rf
prompt  git merge
prompt  git push
prompt  git reset --hard
prompt  git push --force
prompt  git checkout .
prompt  git clean
`,
  };
}

function cageRulesApi(): Record<string, string> {
  return {
    "cage.rules": `# cage execution policy
# format: ACTION PATTERN [ALTERNATIVE]

# direct server commands - use cage infra
block   uvicorn                       cage infra start
block   gunicorn                      cage infra start

# infrastructure - use cage commands
block   lsof                          cage infra stop
block   kill                          cage infra stop
block   killall                       cage infra stop
block   pkill                         cage infra stop

# destructive operations - require confirmation
prompt  rm -rf
prompt  git merge
prompt  git push
prompt  git reset --hard
prompt  git push --force
`,
  };
}

function preCommitConfig(): Record<string, string> {
  return {
    ".pre-commit-config.yaml": `repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-json
      - id: check-added-large-files
        args: ['--maxkb=500']
      - id: detect-private-key
      - id: no-commit-to-branch
        args: ['--branch', 'main', '--branch', 'develop']

  - repo: local
    hooks:
      - id: cage-contract-sync
        name: cage contract sync
        entry: cage check contracts
        language: system
        pass_filenames: false
        always_run: true

      - id: cage-architectural-checks
        name: cage architectural checks
        entry: cage check architecture
        language: system
        pass_filenames: false
        always_run: true
`,
  };
}

function claudeMd(template: string): Record<string, string> {
  const templateNote = template !== "default" ? `\ntemplate: ${template}\n` : "";
  return {
    "CLAUDE.md": `# {{PROJECT_NAME}}

## cage project

this project uses CAGE (contract-enforced agent-guided engineering).${templateNote}

### commands

use scripted lifecycle commands, never raw commands:
- \`cage infra start\` - start all services
- \`cage infra stop\` - stop all services
- \`cage worktree prepare\` - bootstrap a new worktree
- \`cage merge <branch>\` - safe merge from worktree
- \`cage status\` - audit staleness, contract health
- \`cage check\` - run architectural checks
- \`cage index\` - index codebase for semantic search
- \`cage search <query>\` - semantic code search

### execution policy

read \`cage.rules\` before running shell commands. blocked commands have sanctioned alternatives.

### contracts

cross-service truth lives in \`shared/\`. never duplicate these values in service code.
pre-commit hooks enforce sync automatically.

- \`shared/domain-values.json\` - domain constants
- \`shared/api-field-snapshots.json\` - API response shapes
- \`shared/schemas.json\` - data schemas

### docs

- \`docs/features/\` - permanent implementation knowledge
- \`docs/features/implementation-decisions/\` - WHY decisions were made
- \`docs/designs/\` - temporary technical plans (delete after implementation)
- \`docs/bugs.md\` - active unresolved issues
- \`docs/bugs-archive/\` - resolved issues

if you learned something painful during a fix, write it back into docs before the task is done.

### skills

- \`/cage-spec\` - create feature spec (product manager workflow)
- \`/cage-feature\` - implement a feature on a worktree
- \`/cage-review\` - code review with product + architectural context
- \`/cage-audit\` - run audits with git tag tracking

### semantic search

run \`cage search <query>\` to find relevant code before implementing.
example: \`cage search "authentication middleware"\`
`,
  };
}

function agentsMd(template: string): Record<string, string> {
  // identical content to CLAUDE.md for Codex compatibility
  const claudeContent = claudeMd(template)["CLAUDE.md"];
  return {
    "AGENTS.md": claudeContent,
  };
}

function gitignoreAdditions(): Record<string, string> {
  return {
    ".gitignore": `.cage/
*.env
.env.*
!.env.example
node_modules/
__pycache__/
.next/
dist/
`,
  };
}

function cageInfraFullstack(): Record<string, string> {
  return {
    "cage-infra.yaml": `services:
  backend:
    command: uv run uvicorn main:app --host 0.0.0.0 --port $PORT --reload
    port: 4000
    dir: backend/
  frontend:
    command: pnpm dev --port $PORT
    port: 4010
    dir: frontend/
`,
  };
}

function cageInfraApi(): Record<string, string> {
  return {
    "cage-infra.yaml": `services:
  api:
    command: uv run uvicorn main:app --host 0.0.0.0 --port $PORT --reload
    port: 4000
    dir: backend/
`,
  };
}
