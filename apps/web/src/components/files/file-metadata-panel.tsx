"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import type { FileMetadataDetail } from "@ai-media-saas-starter/shared";

interface FileMetadataPanelProps {
  metadata: FileMetadataDetail;
}

function MetaRow({ label, value }: { label: string; value: string | number }) {
  const displayValue = value === "" ? "none" : String(value);

  return (
    <div className="grid min-w-0 grid-cols-[minmax(6rem,0.45fr)_minmax(0,1fr)] gap-3 text-sm">
      <span className="min-w-0 text-muted-foreground">{label}</span>
      <span
        className="min-w-0 break-all text-right font-mono text-xs tabular-nums text-foreground sm:text-sm"
        title={displayValue}
      >
        {displayValue}
      </span>
    </div>
  );
}

function formatTimestamp(value: string) {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

export function FileMetadataPanel({ metadata }: FileMetadataPanelProps) {
  return (
    <Card className="overflow-hidden">
      <CardHeader className="pb-3 px-5 pt-5">
        <CardTitle className="card-title">File Details</CardTitle>
      </CardHeader>
      <CardContent className="min-w-0 space-y-3 px-5 pb-5">
        <MetaRow label="Filename" value={metadata.filename} />
        <MetaRow label="Size" value={metadata.size_human} />
        <MetaRow label="Type" value={metadata.mime_type} />
        <MetaRow label="Extension" value={metadata.extension || "none"} />

        <Separator />
        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
          Checksums
        </p>
        <MetaRow label="MD5" value={metadata.md5} />
        <MetaRow label="SHA-256" value={metadata.sha256} />

        {/* Image metadata */}
        {metadata.image_width && metadata.image_height && (
          <>
            <Separator />
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
              Image
            </p>
            <MetaRow
              label="Dimensions"
              value={`${metadata.image_width} x ${metadata.image_height}`}
            />
            {metadata.exif && (
              <div className="space-y-1">
                {Object.entries(metadata.exif)
                  .slice(0, 8)
                  .map(([key, val]) => (
                    <MetaRow key={key} label={key} value={val} />
                  ))}
              </div>
            )}
          </>
        )}

        {/* PDF metadata */}
        {metadata.pdf_pages !== null && (
          <>
            <Separator />
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
              PDF
            </p>
            <MetaRow label="Pages" value={metadata.pdf_pages} />
            {metadata.pdf_author && (
              <MetaRow label="Author" value={metadata.pdf_author} />
            )}
            {metadata.pdf_title && (
              <MetaRow label="Title" value={metadata.pdf_title} />
            )}
          </>
        )}

        {/* Audio/Video metadata */}
        {metadata.duration_seconds !== null && (
          <>
            <Separator />
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
              Media
            </p>
            <MetaRow
              label="Duration"
              value={`${metadata.duration_seconds.toFixed(1)}s`}
            />
            {metadata.codec && <MetaRow label="Codec" value={metadata.codec} />}
            {metadata.bitrate && (
              <MetaRow label="Bitrate" value={`${metadata.bitrate} bps`} />
            )}
          </>
        )}

        <Separator />
        <MetaRow
          label="Uploaded"
          value={formatTimestamp(metadata.uploaded_at)}
        />
      </CardContent>
    </Card>
  );
}
