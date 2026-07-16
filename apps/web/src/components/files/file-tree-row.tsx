"use client";

import {
  ChevronDown,
  ChevronRight,
  Download,
  Eye,
  FileArchiveIcon,
  FileAudioIcon,
  FileIcon,
  FileTextIcon,
  FileVideoIcon,
  Folder,
  FolderOpen,
  ImageIcon,
  MoreHorizontal,
  Trash2,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { formatDate } from "@/lib/utils";
import type { TreeFolder, TreeNode } from "@/lib/file-tree";
import type { FileMetadata } from "@ai-media-saas-starter/shared";

const MAX_VISIBLE_TREE_DEPTH = 8;

function FileTypeIcon({
  contentType,
  className,
}: {
  contentType: string;
  className?: string;
}) {
  if (contentType.startsWith("image/")) return <ImageIcon className={className} />;
  if (contentType === "application/pdf") return <FileTextIcon className={className} />;
  if (contentType.startsWith("video/")) return <FileVideoIcon className={className} />;
  if (contentType.startsWith("audio/")) return <FileAudioIcon className={className} />;
  if (contentType === "application/zip") return <FileArchiveIcon className={className} />;
  return <FileIcon className={className} />;
}

function countFiles(node: TreeFolder): number {
  let count = 0;

  for (const child of node.children) {
    if (child.type === "file") count++;
    else count += countFiles(child);
  }

  return count;
}

function treeIndent(depth: number, base: number) {
  return Math.min(depth, MAX_VISIBLE_TREE_DEPTH) * 20 + base;
}

function formatFileCount(count: number) {
  const formatted = new Intl.NumberFormat(undefined, {
    notation: count >= 10_000 ? "compact" : "standard",
  }).format(count);

  return `${formatted} ${count === 1 ? "file" : "files"}`;
}

interface FileTreeRowProps {
  node: TreeNode;
  depth: number;
  expanded: Set<string>;
  onToggle: (path: string) => void;
  onPreview: (file: FileMetadata) => void;
  onDownload: (file: FileMetadata) => void;
  onDelete: (file: FileMetadata) => void;
}

export function FileTreeRow({
  node,
  depth,
  expanded,
  onToggle,
  onPreview,
  onDownload,
  onDelete,
}: FileTreeRowProps) {
  if (node.type === "folder") {
    const isOpen = expanded.has(node.path);
    const countLabel = formatFileCount(countFiles(node));

    return (
      <>
        <button
          type="button"
          aria-expanded={isOpen}
          aria-label={`${isOpen ? "Collapse" : "Expand"} folder ${node.path}`}
          onClick={() => onToggle(node.path)}
          title={node.path}
          className="tree-row group flex w-full min-w-0 items-center gap-2 rounded-md px-3 py-2.5 text-left text-sm transition-colors hover:bg-accent/60 focus-visible:bg-accent/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/45"
          style={{ paddingInlineStart: `${treeIndent(depth, 12)}px` }}
        >
          {isOpen ? (
            <ChevronDown
              aria-hidden="true"
              className="h-4 w-4 shrink-0 text-muted-foreground"
            />
          ) : (
            <ChevronRight
              aria-hidden="true"
              className="h-4 w-4 shrink-0 text-muted-foreground"
            />
          )}
          {isOpen ? (
            <FolderOpen
              aria-hidden="true"
              className="h-4 w-4 shrink-0 text-[var(--attention)]"
            />
          ) : (
            <Folder
              aria-hidden="true"
              className="h-4 w-4 shrink-0 text-[var(--attention)]"
            />
          )}
          <span className="min-w-0 flex-1 truncate font-medium">{node.name}</span>
          <span className="ml-auto shrink-0 text-xs tabular-nums text-muted-foreground">
            {countLabel}
          </span>
        </button>
        {isOpen &&
          node.children.map((child) => (
            <FileTreeRow
              key={child.type === "folder" ? child.path : child.data.key}
              node={child}
              depth={depth + 1}
              expanded={expanded}
              onToggle={onToggle}
              onPreview={onPreview}
              onDownload={onDownload}
              onDelete={onDelete}
            />
          ))}
      </>
    );
  }

  const file = node.data;

  return (
    <div
      className="tree-row group flex w-full min-w-0 items-center gap-2 rounded-md px-3 py-2.5 text-sm transition-colors hover:bg-accent/60 focus-within:bg-accent/60"
      style={{ paddingInlineStart: `${treeIndent(depth, 32)}px` }}
    >
      <FileTypeIcon
        contentType={file.content_type}
        className="h-4 w-4 shrink-0 text-muted-foreground"
      />
      <span className="min-w-0 flex-1 truncate" title={file.key}>
        {node.name}
      </span>
      <span className="ml-auto flex shrink-0 items-center gap-2 sm:gap-4">
        <span className="hidden font-mono text-xs tabular-nums text-muted-foreground sm:inline">
          {file.size_human}
        </span>
        <span className="hidden text-xs text-muted-foreground md:inline">
          {formatDate(file.uploaded_at)}
        </span>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              className="touch-target h-8 w-8 shrink-0 opacity-100 transition-opacity sm:h-7 sm:w-7 sm:opacity-0 sm:group-focus-within:opacity-100 sm:group-hover:opacity-100 data-[state=open]:opacity-100"
              aria-label={`Open actions for ${file.filename}`}
              title={`Actions for ${file.filename}`}
            >
              <MoreHorizontal aria-hidden="true" className="h-3.5 w-3.5" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={() => onPreview(file)}>
              <Eye className="mr-2 h-4 w-4" />
              Preview
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => onDownload(file)}>
              <Download className="mr-2 h-4 w-4" />
              Download
            </DropdownMenuItem>
            <DropdownMenuItem
              onClick={() => onDelete(file)}
              className="text-destructive"
            >
              <Trash2 className="mr-2 h-4 w-4" />
              Delete
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </span>
    </div>
  );
}
