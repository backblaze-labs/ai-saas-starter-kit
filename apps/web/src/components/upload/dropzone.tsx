"use client";

import { useCallback, useId } from "react";
import { useDropzone, type FileRejection } from "react-dropzone";
import { Upload, FileIcon } from "lucide-react";

interface DropzoneProps {
  onFilesSelected: (files: File[]) => void;
  onFilesRejected: (rejections: FileRejection[]) => void;
  disabled?: boolean;
}

const MAX_SIZE = 100 * 1024 * 1024; // 100MB

export function Dropzone({
  onFilesSelected,
  onFilesRejected,
  disabled,
}: DropzoneProps) {
  const descriptionId = useId();
  const onDrop = useCallback(
    (accepted: File[]) => {
      if (accepted.length > 0) {
        onFilesSelected(accepted);
      }
    },
    [onFilesSelected]
  );

  const onDropRejected = useCallback(
    (rejections: FileRejection[]) => {
      onFilesRejected(rejections);
    },
    [onFilesRejected]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    onDropRejected,
    maxSize: MAX_SIZE,
    disabled,
    multiple: true,
  });

  const active = isDragActive && !disabled;
  let title = "Drag & drop files here, or click to browse";
  let description = "Max file size: 100 MB per file";

  if (disabled) {
    title = "Uploads in progress";
    description = "New files can be added when the current queue finishes.";
  } else if (active) {
    title = "Drop files here";
    description = "Release to add files to the upload queue.";
  }

  let stateClasses = "border-border hover:border-primary/60 hover:bg-muted/60";
  if (disabled) {
    stateClasses = "border-border";
  } else if (active) {
    stateClasses = "border-primary bg-[var(--accent-subtle)] dropzone-active";
  }
  const disabledClasses = disabled
    ? "cursor-not-allowed bg-muted/40 text-muted-foreground opacity-80"
    : "cursor-pointer";

  return (
    <div
      {...getRootProps({
        "aria-describedby": descriptionId,
        "aria-disabled": disabled,
        "aria-label": "Upload files",
        role: "button",
      })}
      className={[
        "flex min-h-48 flex-col items-center justify-center rounded-md",
        "border-2 border-dashed px-4 py-8 text-center transition-colors",
        "sm:min-h-56 sm:p-10",
        stateClasses,
        disabledClasses,
      ].join(" ")}
    >
      <input
        {...getInputProps({
          "aria-describedby": descriptionId,
          "aria-label": "Choose files to upload",
        })}
      />
      <div className="flex flex-col items-center gap-3">
        {active ? (
          <>
            <div className="stat-icon-wrap !w-12 !h-12">
              <FileIcon className="h-5 w-5" aria-hidden="true" />
            </div>
            <p className="text-base font-semibold">{title}</p>
            <p
              id={descriptionId}
              className="max-w-sm text-xs text-muted-foreground"
            >
              {description}
            </p>
          </>
        ) : (
          <>
            <div className="flex items-center justify-center w-12 h-12 rounded-md bg-muted border border-border">
              <Upload
                className="h-5 w-5 text-muted-foreground"
                aria-hidden="true"
              />
            </div>
            <div className="min-w-0 max-w-full">
              <p className="text-base font-semibold [overflow-wrap:anywhere]">
                {title}
              </p>
              <p
                id={descriptionId}
                className="mt-1 text-xs text-muted-foreground"
              >
                {description}
              </p>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
