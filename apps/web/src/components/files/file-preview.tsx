"use client";

import Image from "next/image";
import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { usePreviewUrl } from "@/lib/queries";
import type { FileMetadata } from "@ai-saas-starter-kit/shared";

interface FilePreviewProps {
  file: FileMetadata | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function PreviewMetaRow({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="grid min-w-0 grid-cols-[5.5rem_minmax(0,1fr)] gap-3 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span
        className={`min-w-0 break-all text-right ${
          mono ? "font-mono text-xs tabular-nums" : ""
        }`}
        title={value}
      >
        {value}
      </span>
    </div>
  );
}

function formatPreviewDate(value: string) {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

export function FilePreview({ file, open, onOpenChange }: FilePreviewProps) {
  // Fetch a presigned preview URL only while the dialog is open. Falls
  // back to the file's stored URL if the API call fails (e.g. the
  // `/preview` endpoint is unreachable but we still have a static URL).
  const { data, isLoading, isError } = usePreviewUrl(
    file?.key,
    open && !!file,
  );
  const previewUrl = data?.url ?? file?.url ?? null;

  // Track which URL has finished painting. The full-resolution original can be
  // large (the bucket holds a 25.7 MB image), and the presigned URL arrives
  // well before the bytes do — so keep a spinner over the box until the <img>
  // actually loads, instead of sitting on a blank/partial frame. Keyed by URL
  // so it auto-resets when a different file's preview opens.
  const [loadedUrl, setLoadedUrl] = useState<string | null>(null);
  const imageReady = !!previewUrl && loadedUrl === previewUrl;

  if (!file) return null;

  const isImage = file.content_type.startsWith("image/");
  const isPdf = file.content_type === "application/pdf";
  const previewError = "The preview link could not be created.";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85svh] w-[calc(100vw-2rem)] max-w-3xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="min-w-0 break-words pr-6">
            {file.filename}
          </DialogTitle>
        </DialogHeader>
        <div className="grid min-w-0 gap-4 md:grid-cols-2">
          <div className="flex min-w-0 items-center justify-center overflow-hidden rounded-lg border bg-muted/30 min-h-[220px]">
            {isLoading ? (
              <div
                className="w-full p-3"
                role="status"
                aria-live="polite"
                aria-label="Loading file preview"
              >
                <p className="sr-only">Loading file preview…</p>
                <Skeleton className="h-[min(55svh,400px)] min-h-[220px] w-full" />
              </div>
            ) : isImage && previewUrl ? (
              <div className="relative h-[min(55svh,400px)] min-h-[220px] w-full">
                {!imageReady && (
                  <div
                    className="absolute inset-0 z-10"
                    role="status"
                    aria-live="polite"
                    aria-label="Loading preview image"
                  >
                    <p className="sr-only">Loading preview image…</p>
                    <Skeleton className="h-full w-full" />
                  </div>
                )}
                {/* `unoptimized` because presigned URLs carry their own
                    short-lived expiry and we don't want Next's image
                    optimizer caching them past that window. */}
                <Image
                  src={previewUrl}
                  alt={file.filename}
                  fill
                  sizes="(max-width: 768px) 100vw, 600px"
                  className={`object-contain rounded transition-opacity duration-200 ${
                    imageReady ? "opacity-100" : "opacity-0"
                  }`}
                  unoptimized
                  onLoad={() => setLoadedUrl(previewUrl)}
                  // Stop the spinner on error too, so a broken/expired URL
                  // falls through to the box background rather than spinning.
                  onError={() => setLoadedUrl(previewUrl)}
                />
              </div>
            ) : isPdf && previewUrl ? (
              <iframe
                src={previewUrl}
                className="h-[min(55svh,400px)] min-h-[220px] w-full rounded"
                title={`Preview of ${file.filename}`}
              />
            ) : (
              <div className="max-w-sm p-8 text-center text-muted-foreground">
                <p className="text-sm font-medium text-foreground">
                  {isError ? "Preview URL unavailable" : "Preview not available"}
                </p>
                <p className="mt-1 text-xs break-words">
                  {isError ? previewError : file.content_type}
                </p>
              </div>
            )}
          </div>
          <div className="min-w-0 space-y-4">
            <div className="space-y-2 text-sm">
              <PreviewMetaRow label="Size" value={file.size_human} mono />
              <PreviewMetaRow label="Type" value={file.content_type} />
              <PreviewMetaRow
                label="Uploaded"
                value={formatPreviewDate(file.uploaded_at)}
              />
              <PreviewMetaRow label="Key" value={file.key} mono />
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
