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
  legacyPath: (key: string) => string;
  method: "GET" | "DELETE";
  name: string;
  path: string;
  unsafeFallbackKeys: { key: string }[];
};

const operations: FileKeyOperation[] = [
  {
    call: getFile,
    legacyPath: (key) => `/files/${encodeURIComponent(key)}`,
    method: "GET",
    name: "getFile",
    path: "/files-by-key/metadata",
    unsafeFallbackKeys: [
      "stats",
      "stats/activity",
      "payroll/download",
      "payroll/preview",
      "reports/download",
      "reports/preview",
      "../secret.txt",
      "uploads/%2e%2e/secret.txt",
    ].map((key) => ({ key })),
  },
  {
    call: getDownloadUrl,
    legacyPath: (key) => `/files/${encodeURIComponent(key)}/download`,
    method: "GET",
    name: "getDownloadUrl",
    path: "/files-by-key/download",
    unsafeFallbackKeys: ["../secret.txt", "uploads/%2e%2e/secret.txt"].map((key) => ({
      key,
    })),
  },
  {
    call: getPreviewUrl,
    legacyPath: (key) => `/files/${encodeURIComponent(key)}/preview`,
    method: "GET",
    name: "getPreviewUrl",
    path: "/files-by-key/preview",
    unsafeFallbackKeys: ["../secret.txt", "uploads/%2e%2e/secret.txt"].map((key) => ({
      key,
    })),
  },
  {
    call: deleteFile,
    legacyPath: (key) => `/files/${encodeURIComponent(key)}`,
    method: "DELETE",
    name: "deleteFile",
    path: "/files-by-key",
    unsafeFallbackKeys: ["../secret.txt", "uploads/%2e%2e/secret.txt"].map((key) => ({
      key,
    })),
  },
];

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

describe.each(operations)(
  "$name",
  ({ call, legacyPath, method, path, unsafeFallbackKeys }) => {
    it.each(keyCases)("sends '$key' as a query parameter", async ({ key }) => {
      await call(key);

      expect(requestedPath()).toBe(`${path}?${new URLSearchParams({ key })}`);
      const init = fetchMock.mock.calls[0][1];
      expect(init?.method ?? "GET").toBe(method);
    });

    it("rejects empty keys before making a request", async () => {
      await expectEmptyKeyRejected(call);

      expect(fetchMock).not.toHaveBeenCalled();
    });

    it("falls back to the legacy route when the query route is unavailable", async () => {
      const key = "uploads/report final.txt";
      fetchMock
        .mockResolvedValueOnce(errorResponse(404, "Not Found"))
        .mockResolvedValueOnce(jsonResponse({ key }));

      await call(key);

      expect(requestedPath(0)).toBe(`${path}?${new URLSearchParams({ key })}`);
      expect(requestedPath(1)).toBe(legacyPath(key));
      expect(fetchMock).toHaveBeenCalledTimes(2);
    });

    it("does not fall back when the current API reports a missing file", async () => {
      const key = "stats";
      fetchMock.mockResolvedValueOnce(errorResponse(404, "File not found"));

      await expect(call(key)).rejects.toMatchObject({
        message: "File not found",
        status: 404,
      });

      expect(fetchMock).toHaveBeenCalledTimes(1);
    });

    it.each(unsafeFallbackKeys)(
      "does not fall back for unsafe legacy path key '$key'",
      async ({ key }) => {
        fetchMock.mockResolvedValueOnce(errorResponse(404, "Not Found"));

        await expect(call(key)).rejects.toMatchObject({
          message: "Current API version required for this file key",
          status: 404,
        });

        expect(fetchMock).toHaveBeenCalledTimes(1);
      }
    );
  }
);
