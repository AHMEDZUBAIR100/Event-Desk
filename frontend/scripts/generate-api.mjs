import { existsSync } from "node:fs";
import { execFileSync } from "node:child_process";
import path from "node:path";

const localSchema = path.resolve(process.cwd(), "../backend/openapi.json");
const schema =
  process.env.OPENAPI_SCHEMA ??
  (existsSync(localSchema)
    ? localSchema
    : "http://localhost:8000/api/v1/openapi.json");

console.log(`Generating API types from ${schema}`);
execFileSync("npx", ["openapi-typescript", schema, "-o", "types/api.ts"], {
  stdio: "inherit",
});
