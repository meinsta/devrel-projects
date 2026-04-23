import { readFileSync, readdirSync, existsSync } from "fs";
import path from "path";

interface ValidationResult {
  file: string;
  valid: boolean;
  error?: string;
}

export async function contractValidate(sharedDir: string): Promise<boolean> {
  if (!existsSync(sharedDir)) {
    console.log("skip: no shared/ directory");
    return true;
  }

  const files = readdirSync(sharedDir).filter(f => f.endsWith(".json"));

  if (files.length === 0) {
    console.log("skip: no JSON files in shared/");
    return true;
  }

  console.log("validating contracts...");

  const results: ValidationResult[] = [];
  let allValid = true;

  for (const file of files) {
    const filePath = path.join(sharedDir, file);
    try {
      const content = readFileSync(filePath, "utf-8");
      JSON.parse(content);
      results.push({ file, valid: true });
      console.log(`  ok: ${file}`);
    } catch (err: any) {
      results.push({ file, valid: false, error: err.message });
      console.log(`  FAIL: ${file}: ${err.message}`);
      allValid = false;
    }
  }

  // check for empty contracts (only have _comment)
  for (const file of files) {
    const filePath = path.join(sharedDir, file);
    try {
      const data = JSON.parse(readFileSync(filePath, "utf-8"));
      const keys = Object.keys(data).filter(k => !k.startsWith("_"));
      if (keys.length === 0) {
        console.log(`  warn: ${file} has no entries (only comments)`);
      } else {
        // check each non-comment key for empty objects/arrays
        for (const key of keys) {
          const val = data[key];
          if (typeof val === "object" && Object.keys(val).length === 0) {
            console.log(`  warn: ${file}.${key} is empty`);
          }
        }
      }
    } catch {
      // already reported above
    }
  }

  if (allValid) {
    console.log(`\nall ${files.length} contracts valid`);
  } else {
    const failed = results.filter(r => !r.valid).length;
    console.log(`\n${failed}/${files.length} contracts invalid`);
  }

  return allValid;
}
