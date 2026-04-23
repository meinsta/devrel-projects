import { readFileSync, existsSync } from "fs";
import path from "path";

export interface PolicyRule {
  action: "block" | "prompt" | "allow";
  pattern: string[];  // tokenized command prefix
  alternative?: string;
  line: number;
}

export interface PolicyCheckResult {
  permissionDecision: "deny" | "ask";
  message: string;
}

export function parseRulesFile(filePath: string): PolicyRule[] {
  if (!existsSync(filePath)) {
    throw new Error(`cage.rules not found: ${filePath}`);
  }

  const content = readFileSync(filePath, "utf-8");
  const rules: PolicyRule[] = [];
  const lines = content.split("\n");

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();

    // skip comments and empty lines
    if (line.startsWith("#") || line === "") continue;

    const tokens = line.split(/\s+/);
    const action = tokens[0];

    if (action !== "block" && action !== "prompt" && action !== "allow") {
      throw new Error(`cage.rules:${i + 1}: invalid action '${action}' (expected block|prompt|allow)`);
    }

    // find the pattern and alternative
    // pattern is everything after action until we hit a known alternative prefix
    // alternatives are detected by finding "cage" as a token boundary
    let patternTokens: string[] = [];
    let alternativeTokens: string[] = [];
    let inAlternative = false;

    for (let j = 1; j < tokens.length; j++) {
      if (!inAlternative && tokens[j] === "cage" && patternTokens.length > 0) {
        inAlternative = true;
      }

      if (inAlternative) {
        alternativeTokens.push(tokens[j]);
      } else {
        patternTokens.push(tokens[j]);
      }
    }

    if (patternTokens.length === 0) {
      throw new Error(`cage.rules:${i + 1}: rule has no pattern`);
    }

    rules.push({
      action: action as PolicyRule["action"],
      pattern: patternTokens,
      alternative: alternativeTokens.length > 0 ? alternativeTokens.join(" ") : undefined,
      line: i + 1,
    });
  }

  return rules;
}

// tokenized matching: "block kill" matches "kill 1234" but NOT "killall"
function matchesRule(commandTokens: string[], rulePattern: string[]): boolean {
  if (commandTokens.length < rulePattern.length) return false;

  for (let i = 0; i < rulePattern.length; i++) {
    if (commandTokens[i] !== rulePattern[i]) return false;
  }

  return true;
}

export function findCageRules(): string | null {
  let dir = process.cwd();
  while (dir !== "/") {
    const candidate = path.join(dir, "cage.rules");
    if (existsSync(candidate)) return candidate;
    dir = path.dirname(dir);
  }
  return null;
}

export async function policyParse(rulesFile?: string): Promise<void> {
  const filePath = rulesFile || findCageRules();
  if (!filePath) {
    console.error("no cage.rules found");
    process.exit(1);
  }

  const rules = parseRulesFile(filePath);
  console.log(`parsed ${rules.length} rules from ${filePath}`);

  const blocked = rules.filter(r => r.action === "block");
  const prompted = rules.filter(r => r.action === "prompt");

  if (blocked.length > 0) {
    console.log(`\nblocked (${blocked.length}):`);
    for (const r of blocked) {
      const alt = r.alternative ? ` -> ${r.alternative}` : "";
      console.log(`  ${r.pattern.join(" ")}${alt}`);
    }
  }

  if (prompted.length > 0) {
    console.log(`\nprompted (${prompted.length}):`);
    for (const r of prompted) {
      console.log(`  ${r.pattern.join(" ")}`);
    }
  }
}

export async function policyCheck(command: string): Promise<PolicyCheckResult | null> {
  const rulesFile = findCageRules();
  if (!rulesFile) return null;

  const rules = parseRulesFile(rulesFile);
  const commandTokens = command.trim().split(/\s+/);

  for (const rule of rules) {
    if (matchesRule(commandTokens, rule.pattern)) {
      if (rule.action === "block") {
        let msg = `BLOCKED by cage.rules: '${rule.pattern.join(" ")}'`;
        if (rule.alternative) msg += `. use '${rule.alternative}' instead`;
        return { permissionDecision: "deny", message: msg };
      }
      if (rule.action === "prompt") {
        let msg = `cage.rules requires confirmation for: '${rule.pattern.join(" ")}'`;
        if (rule.alternative) msg += `. consider using '${rule.alternative}' instead`;
        return { permissionDecision: "ask", message: msg };
      }
    }
  }

  return null;
}
