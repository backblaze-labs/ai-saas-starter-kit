#!/usr/bin/env node
// Probe loopbacks (not wildcards) because uvicorn binds 127.0.0.1 by
// default, and on macOS a 127.0.0.1 conflict doesn't show up via a
// 0.0.0.0 probe — the two don't overlap there.
//
// Usage:  node scripts/pick-port.mjs [start]   (default start=8000)

import { createServer } from "node:net";

const RANGE = 10;
const LOOPBACKS = ["127.0.0.1", "::1"];
const start = Number.parseInt(process.argv[2] ?? "8000", 10);

function isFreeOn(port, host) {
  return new Promise((res) => {
    const server = createServer();
    server.once("error", () => res(false));
    server.once("listening", () => server.close(() => res(true)));
    server.listen(port, host);
  });
}

async function isFree(port) {
  const results = await Promise.all(LOOPBACKS.map((h) => isFreeOn(port, h)));
  return results.every(Boolean);
}

for (let p = start; p < start + RANGE; p++) {
  if (await isFree(p)) {
    process.stdout.write(String(p));
    process.exit(0);
  }
}

console.error(`pick-port: no free port in ${start}..${start + RANGE - 1}`);
process.exit(1);
