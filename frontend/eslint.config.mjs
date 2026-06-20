import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";

const eslintConfig = defineConfig([
  ...nextVitals,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
  {
    rules: {
      // Auth bootstrap legitimately sets state from effects (read token from
      // localStorage on mount, fetch the current user) — keep it surfaced as a
      // warning rather than failing the build.
      "react-hooks/set-state-in-effect": "warn",
    },
  },
]);

export default eslintConfig;
