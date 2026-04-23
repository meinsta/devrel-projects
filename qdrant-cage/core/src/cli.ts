#!/usr/bin/env bun

import { parseArgs } from "util";
import { policyParse, policyCheck } from "./commands/policy";
import { contractValidate } from "./commands/contract";
import { checkRun, checkList } from "./commands/check";
import { infraStart, infraStop, infraStatus } from "./commands/infra";
import { portAssign } from "./commands/port";
import { pipelineGet, pipelineTransition, pipelineList, pipelineReset } from "./commands/pipeline";
import { scan } from "./commands/scan";
import { doctor } from "./commands/doctor";
import { init } from "./commands/init";
import { index, search } from "./commands/index-cmd";
import { status } from "./commands/status";

const USAGE = `cage-core - CAGE binary engine

usage: cage-core <command> [args]

commands:
  policy parse <rules-file>           parse and validate cage.rules
  policy check <command-string>       check a command against cage.rules
  contract validate <shared-dir>      validate contract files
  check run [--name <check>] <root>   run architectural checks
  check list                          list available checks
  infra start <config-yaml>           start services
  infra stop <pid-dir>                stop services
  infra status <pid-dir>              show service status
  port assign <service> <worktree-idx> calculate port for service+worktree
  pipeline get <feature>              get feature pipeline state
  pipeline transition <feature> <st>  transition feature state
  pipeline list                       list all features
  pipeline reset <feature>            reset feature to spec-created
  scan <project-root>                 detect services, generate agent context
  doctor <project-root>               diagnose project setup
  init --template <T> <target-dir>    initialize a CAGE project
  index <project-root>                index codebase into Qdrant
  search <query>                      semantic code search
  status                              show cage status dashboard
`;

async function main() {
  const args = process.argv.slice(2);

  if (args.length === 0 || args[0] === "--help" || args[0] === "-h") {
    console.log(USAGE);
    process.exit(0);
  }

  const command = args[0];
  const subcommand = args[1];
  const rest = args.slice(2);

  try {
    switch (command) {
      case "policy":
        if (subcommand === "parse") {
          await policyParse(rest[0]);
        } else if (subcommand === "check") {
          const result = await policyCheck(rest.join(" "));
          if (result) {
            console.log(JSON.stringify(result));
          }
        } else {
          die(`unknown policy subcommand: ${subcommand}`);
        }
        break;

      case "contract":
        if (subcommand === "validate") {
          const ok = await contractValidate(rest[0] || "shared");
          process.exit(ok ? 0 : 1);
        } else {
          die(`unknown contract subcommand: ${subcommand}`);
        }
        break;

      case "check":
        if (subcommand === "run") {
          const nameIdx = rest.indexOf("--name");
          let checkName: string | undefined;
          let projectRoot: string;
          if (nameIdx >= 0) {
            checkName = rest[nameIdx + 1];
            projectRoot = rest.filter((_, i) => i !== nameIdx && i !== nameIdx + 1)[0] || ".";
          } else {
            projectRoot = rest[0] || ".";
          }
          const ok = await checkRun(projectRoot, checkName);
          process.exit(ok ? 0 : 1);
        } else if (subcommand === "list") {
          await checkList();
        } else {
          die(`unknown check subcommand: ${subcommand}`);
        }
        break;

      case "infra":
        if (subcommand === "start") {
          await infraStart(rest[0]);
        } else if (subcommand === "stop") {
          await infraStop(rest[0] || ".cage/pids");
        } else if (subcommand === "status") {
          await infraStatus(rest[0] || ".cage/pids");
        } else {
          die(`unknown infra subcommand: ${subcommand}`);
        }
        break;

      case "port":
        if (subcommand === "assign") {
          await portAssign(rest[0], parseInt(rest[1] || "0", 10));
        } else {
          die(`unknown port subcommand: ${subcommand}`);
        }
        break;

      case "pipeline":
        if (subcommand === "get") {
          await pipelineGet(rest[0]);
        } else if (subcommand === "transition") {
          await pipelineTransition(rest[0], rest[1]);
        } else if (subcommand === "list") {
          await pipelineList();
        } else if (subcommand === "reset") {
          await pipelineReset(rest[0]);
        } else {
          die(`unknown pipeline subcommand: ${subcommand}`);
        }
        break;

      case "scan":
        await scan(rest[0] || ".");
        break;

      case "doctor":
        await doctor(rest[0] || ".");
        break;

      case "init": {
        // parse init args: cage-core init --template fullstack /path
        const initArgs = [subcommand, ...rest].filter(Boolean);
        const tIdx = initArgs.indexOf("--template");
        const tmpl = tIdx >= 0 ? initArgs[tIdx + 1] : "default";
        const tgt = initArgs.filter((_, i) => i !== tIdx && i !== (tIdx >= 0 ? tIdx + 1 : -1))[0] || ".";
        await init(tgt, tmpl);
        break;
      }

      case "index":
        await index(rest[0] || ".");
        break;

      case "search":
        await search([subcommand, ...rest].filter(Boolean).join(" "));
        break;

      case "status":
        await status();
        break;

      default:
        die(`unknown command: ${command}`);
    }
  } catch (err: any) {
    console.error(`error: ${err.message}`);
    process.exit(1);
  }
}

function die(msg: string): never {
  console.error(`error: ${msg}`);
  console.error("run 'cage-core --help' for usage");
  process.exit(1);
}

main();
