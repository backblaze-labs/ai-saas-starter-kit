"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { FolderOpen, RefreshCw, Upload } from "lucide-react";
import { toast } from "sonner";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { FilePreview } from "./file-preview";
import { FileTreeRow } from "./file-tree-row";
import { getDownloadUrl } from "@/lib/api-client";
import { useDeleteFile, useFiles } from "@/lib/queries";
import { buildFileTree, type TreeFolder } from "@/lib/file-tree";
import type { FileMetadata } from "@ai-saas-starter-kit/shared";

// Fetch up to the API's max (it caps `limit` at 1000). The previous default of
// 100 silently hid every file past the first hundred with no indication; at the
// cap we now tell the user the list is truncated instead of pretending it's all.
const FILE_LIST_LIMIT = 1000;

export function FileBrowser() {
  const { data: files = [], isLoading, isFetching, error, refetch } = useFiles(
    "",
    FILE_LIST_LIMIT,
  );
  const deleteMutation = useDeleteFile();
  const truncated = files.length >= FILE_LIST_LIMIT;

  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [previewFile, setPreviewFile] = useState<FileMetadata | null>(null);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<FileMetadata | null>(null);

  const tree = useMemo(() => buildFileTree(files), [files]);

  // Auto-expand top-level folders the first time data arrives. The guard
  // on `prev.size > 0` makes this idempotent across refetches — once the
  // user has toggled anything, their expansion state is preserved (this
  // is a deliberate UX improvement over the pre-TanStack-Query version,
  // which clobbered expansion state on every refresh).
  useEffect(() => {
    if (files.length === 0) return;
    // Syncing initial UI state once when async data first arrives is the
    // documented escape hatch for react-hooks/set-state-in-effect.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setExpanded((prev) => {
      if (prev.size > 0) return prev;
      const topFolders = tree
        .filter((n): n is TreeFolder => n.type === "folder")
        .map((f) => f.path);
      return new Set(topFolders);
    });
  }, [files.length, tree]);

  const toggleFolder = useCallback((path: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  }, []);

  const handleDownload = async (file: FileMetadata) => {
    try {
      const { url } = await getDownloadUrl(file.key);
      window.open(url, "_blank");
    } catch {
      toast.error("Couldn't get the download link. Please try again.");
    }
  };

  const confirmDelete = () => {
    if (!deleteTarget) return;
    const target = deleteTarget;
    deleteMutation.mutate(target.key, {
      onSuccess: () => {
        toast.success(`${target.filename} deleted`);
      },
      onError: () => {
        toast.error("Couldn't delete the file. Please try again.");
      },
      onSettled: () => setDeleteTarget(null),
    });
  };

  const handlePreview = (file: FileMetadata) => {
    setPreviewFile(file);
    setPreviewOpen(true);
  };

  return (
    <>
      <Card>
        <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-3 border-b border-border px-5 py-4 space-y-0">
          <CardTitle className="card-title">All files</CardTitle>
          <Button
            variant="outline"
            size="sm"
            onClick={() => refetch()}
            className="touch-target h-7 shrink-0 text-xs"
            disabled={isFetching}
            aria-label={isFetching ? "Refreshing file list" : "Refresh file list"}
          >
            <RefreshCw
              aria-hidden="true"
              className={`h-3.5 w-3.5 mr-1 ${isFetching ? "animate-spin" : ""}`}
            />
            Refresh
          </Button>
        </CardHeader>
        <CardContent className="p-3" aria-busy={isLoading || isFetching}>
          {isLoading ? (
            <div
              className="space-y-2 px-1 py-1"
              role="status"
              aria-live="polite"
              aria-label="Loading files"
            >
              <p className="sr-only">Loading files…</p>
              {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-8 w-full" />
              ))}
            </div>
          ) : error ? (
            <ErrorState
              error={error}
              title="Couldn't load files"
              onRetry={() => refetch()}
              className="px-4"
            />
          ) : files.length === 0 ? (
            <EmptyState
              icon={FolderOpen}
              title="This bucket is empty"
              description="Upload some files to see them listed here."
              action={
                <Button asChild size="sm">
                  <Link href="/upload">
                    <Upload aria-hidden="true" className="h-3.5 w-3.5" />
                    Upload files
                  </Link>
                </Button>
              }
              className="px-4"
            />
          ) : (
            <div className="space-y-0.5 overflow-hidden" aria-label="Files in bucket">
              {tree.map((node) => (
                <FileTreeRow
                  key={node.type === "folder" ? node.path : node.data.key}
                  node={node}
                  depth={0}
                  expanded={expanded}
                  onToggle={toggleFolder}
                  onPreview={handlePreview}
                  onDownload={handleDownload}
                  onDelete={setDeleteTarget}
                />
              ))}
              {truncated && (
                <p className="px-2 pt-2 text-xs text-muted-foreground" role="status">
                  Showing the first {FILE_LIST_LIMIT.toLocaleString()} files. Use
                  Upload/folders to organize; older items may not appear here.
                </p>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      <FilePreview
        file={previewFile}
        open={previewOpen}
        onOpenChange={setPreviewOpen}
      />

      <AlertDialog open={!!deleteTarget} onOpenChange={(open) => !open && setDeleteTarget(null)}>
        <AlertDialogContent className="max-w-[calc(100vw-2rem)] sm:max-w-lg">
          <AlertDialogHeader>
            <AlertDialogTitle>Delete file?</AlertDialogTitle>
            <AlertDialogDescription className="break-words">
              This will permanently delete{" "}
              <strong className="break-all font-semibold text-foreground">
                {deleteTarget?.filename}
              </strong>
              . This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleteMutation.isPending}>
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={confirmDelete}
              disabled={deleteMutation.isPending}
              // Use the destructive variant so the confirm gets white-on-red
              // (AA in both themes); AlertDialogAction merges this over its
              // default variant.
              className={buttonVariants({ variant: "destructive" })}
            >
              {deleteMutation.isPending ? "Deleting…" : "Delete"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
