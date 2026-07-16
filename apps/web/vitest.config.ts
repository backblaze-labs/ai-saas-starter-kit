import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

// Resolve the `@/` path alias (mirrors tsconfig `paths`) so unit tests can
// import components/modules that use it. Test discovery and environment stay on
// vitest defaults; the `e2e/**` exclusion is applied via the CLI flag.
export default defineConfig({
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
});
