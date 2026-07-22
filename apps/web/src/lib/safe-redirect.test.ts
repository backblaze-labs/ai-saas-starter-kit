import { describe, expect, it } from "vitest";
import { safeNextPath } from "./safe-redirect";

describe("safeNextPath", () => {
  it("allows same-site relative paths", () => {
    expect(safeNextPath("/files")).toBe("/files");
    expect(safeNextPath("/account?tab=billing")).toBe("/account?tab=billing");
  });

  it("falls back to / for missing or empty input", () => {
    expect(safeNextPath(null)).toBe("/");
    expect(safeNextPath(undefined)).toBe("/");
    expect(safeNextPath("")).toBe("/");
  });

  it("rejects protocol-relative and absolute URLs", () => {
    expect(safeNextPath("//evil.com")).toBe("/");
    expect(safeNextPath("https://evil.com")).toBe("/");
    expect(safeNextPath("javascript:alert(1)")).toBe("/");
  });

  it("rejects backslash tricks that browsers resolve to another origin", () => {
    // "/\evil.com" resolves to http://evil.com in a browser.
    expect(safeNextPath("/\\evil.com")).toBe("/");
    expect(safeNextPath("\\\\evil.com")).toBe("/");
  });

  it("rejects control chars the URL parser strips before resolving", () => {
    // The WHATWG URL parser drops tab/newline/CR, so these collapse to a
    // protocol-relative "//evil.com" and must be rejected pre-parse.
    expect(safeNextPath("/\n/evil.com")).toBe("/");
    expect(safeNextPath("/\r/evil.com")).toBe("/");
    expect(safeNextPath("/\t/evil.com")).toBe("/");
    expect(safeNextPath("/\x00/evil.com")).toBe("/");
  });
});
