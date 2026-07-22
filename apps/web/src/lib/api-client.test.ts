import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  deleteFile,
  getDownloadUrl,
  getFile,
  getPreviewUrl,
} from "./api-client";

type FileKeyOperation = {
  call: (key: string) => Promise<unknown>;
  method: "GET" | "DELETE";
  name: string;
  path: string;
};

// The client only ever addresses a file through the `/files-by-key/*` routes,
// always sending the object key as a query parameter.
const operations: FileKeyOperation[] = [
  { call: getFile, method: "GET", name: "getFile", path: "/files-by-key/metadata" },
  {
    call: getDownloadUrl,
    method: "GET",
    name: "getDownloadUrl",
    path: "/files-by-key/download",
  },
  {
    call: getPreviewUrl,
    method: "GET",
    name: "getPreviewUrl",
    path: "/files-by-key/preview",
  },
  { call: deleteFile, method: "DELETE", name: "deleteFile", path: "/files-by-key" },
];

// Keys with slashes, spaces, reserved route names, and traversal-shaped input:
// all must ride in the query string untouched — never a path segment — so the
// server sees the raw key and applies its own validation/ownership checks.
const keyCases = [
  "folder/file.txt",
  "folder/file #1?.txt",
  "folder/100% complete.txt",
  "../secret.txt",
  "uploads/%2e%2e/secret.txt",
  "stats",
  "stats/activity",
  "tenant-a/reports/download",
  "tenant-a/reports/preview",
].map((key) => ({ key }));

const fetchMock = vi.fn<typeof fetch>();

function jsonResponse(body: unknown) {
  return new Response(JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
    status: 200,
  });
}

function errorResponse(status: number, detail: string) {
  return new Response(JSON.stringify({ detail }), {
    headers: { "Content-Type": "application/json" },
    status,
  });
}

function requestedPath(callIndex = 0) {
  const [input] = fetchMock.mock.calls[callIndex];
  const url = new URL(input as string);
  return `${url.pathname}${url.search}`;
}

async function expectEmptyKeyRejected(call: FileKeyOperation["call"]) {
  try {
    await call("");
    throw new Error("Expected empty key to reject");
  } catch (error) {
    expect(error).toBeInstanceOf(ApiError);
    const apiError = error as ApiError;
    expect(apiError.message).toBe("File key is required");
    expect(apiError.status).toBe(400);
  }
}

beforeEach(() => {
  fetchMock.mockReset();
  fetchMock.mockResolvedValue(jsonResponse({}));
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe.each(operations)("$name", ({ call, method, path }) => {
  it.each(keyCases)("sends '$key' as a query parameter", async ({ key }) => {
    await call(key);

    expect(requestedPath()).toBe(`${path}?${new URLSearchParams({ key })}`);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const init = fetchMock.mock.calls[0][1];
    expect(init?.method ?? "GET").toBe(method);
  });

  it("rejects empty keys before making a request", async () => {
    await expectEmptyKeyRejected(call);

    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("propagates a 404 from the by-key route without any fallback attempt", async () => {
    fetchMock.mockResolvedValueOnce(errorResponse(404, "File not found"));

    await expect(call("uploads/report final.txt")).rejects.toMatchObject({
      message: "File not found",
      status: 404,
    });

    // Exactly one request — there is no second (legacy) route to fall back to.
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
