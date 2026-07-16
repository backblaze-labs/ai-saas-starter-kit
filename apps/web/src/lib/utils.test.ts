import { describe, expect, it } from "vitest";

import { humanizeBytes, formatDate } from "./utils";

describe("humanizeBytes", () => {
  it("formats bytes with no decimals", () => {
    expect(humanizeBytes(0)).toBe("0 B");
    expect(humanizeBytes(512)).toBe("512 B");
  });

  it("formats KB/MB/GB with one decimal", () => {
    expect(humanizeBytes(1024)).toBe("1.0 KB");
    expect(humanizeBytes(1536)).toBe("1.5 KB");
    expect(humanizeBytes(1024 * 1024)).toBe("1.0 MB");
    expect(humanizeBytes(1024 * 1024 * 1024)).toBe("1.0 GB");
  });

  it("falls back to TB above GB", () => {
    expect(humanizeBytes(1024 ** 4)).toBe("1.0 TB");
  });
});

describe("formatDate", () => {
  it("renders the month for an ISO timestamp", () => {
    // Month is stable across realistic timezones for a mid-month date;
    // day/time are locale/tz-dependent so we don't assert them exactly.
    expect(formatDate("2026-02-14T09:05:00Z")).toContain("Feb");
  });
});
