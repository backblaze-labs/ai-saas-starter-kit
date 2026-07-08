"use client";

import { Inbox, FileIcon } from "lucide-react";
import type { ColumnDef } from "@tanstack/react-table";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { DataTable } from "@/components/ui/data-table";
import { ApiError } from "@/lib/api-client";
import { Section } from "./section";

// Demo errors for the ErrorState showcase. These are constructed, not
// thrown — `ErrorState` reads `status` to derive the right copy.
const offlineError = new ApiError("Network error — check your connection", 0);
const serverError = new ApiError("Internal Server Error", 500);

type Row = { name: string; size: string; type: string };

const sampleRows: Row[] = [
  { name: "diagram.png", size: "124 KB", type: "Image" },
  { name: "report.pdf", size: "892 KB", type: "PDF" },
  { name: "budget.csv", size: "18 KB", type: "CSV" },
  { name: "demo.mp4", size: "42.1 MB", type: "Video" },
  { name: "notes.txt", size: "2 KB", type: "Text" },
  { name: "archive.zip", size: "7.3 MB", type: "Archive" },
  { name: "avatar.jpg", size: "89 KB", type: "Image" },
  { name: "script.py", size: "4 KB", type: "Text" },
  { name: "slides.pdf", size: "1.2 MB", type: "PDF" },
  { name: "music.mp3", size: "3.8 MB", type: "Audio" },
  { name: "cover.png", size: "212 KB", type: "Image" },
  { name: "spec.md", size: "11 KB", type: "Text" },
];

const columns: ColumnDef<Row>[] = [
  {
    accessorKey: "name",
    header: "Filename",
    size: 320,
    cell: ({ row }) => (
      <span className="flex items-center gap-2">
        <FileIcon className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
        <span className="font-medium truncate">{row.original.name}</span>
      </span>
    ),
  },
  {
    accessorKey: "size",
    header: "Size",
    size: 120,
    cell: ({ row }) => (
      <span className="font-mono text-xs text-muted-foreground tabular-nums">
        {row.original.size}
      </span>
    ),
  },
  {
    accessorKey: "type",
    header: "Type",
    size: 120,
    cell: ({ row }) => (
      <span className="text-muted-foreground">{row.original.type}</span>
    ),
  },
];

export function DesignPatterns() {
  return (
    <Section
      id="patterns"
      title="Patterns"
      description="Composed building blocks — empty states, sortable tables, page headers."
    >
      <div className="grid gap-4">
        <Card>
          <CardHeader className="border-b border-border py-4 px-5">
            <CardTitle className="card-title">Empty state</CardTitle>
          </CardHeader>
          <CardContent className="p-5">
            <EmptyState
              icon={Inbox}
              title="No uploads yet"
              description="Drop files in the Upload page to see them here."
              action={
                <Button size="sm" variant="outline">
                  Go to Upload
                </Button>
              }
            />
          </CardContent>
        </Card>

        <div className="grid gap-4 md:grid-cols-2">
          <Card>
            <CardHeader className="border-b border-border py-4 px-5">
              <CardTitle className="card-title">Error state — offline</CardTitle>
            </CardHeader>
            <CardContent className="p-5">
              <ErrorState error={offlineError} onRetry={() => {}} />
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="border-b border-border py-4 px-5">
              <CardTitle className="card-title">Error state — backend 5xx</CardTitle>
            </CardHeader>
            <CardContent className="p-5">
              <ErrorState error={serverError} onRetry={() => {}} />
            </CardContent>
          </Card>
        </div>

        <Card>
          <CardHeader className="border-b border-border py-4 px-5">
            <CardTitle className="card-title">
              Sortable data table
            </CardTitle>
          </CardHeader>
          <CardContent className="p-5">
            <DataTable
              columns={columns}
              data={sampleRows}
              pageSize={5}
              emptyTitle="No files"
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="border-b border-border py-4 px-5">
            <CardTitle className="card-title">
              Command palette
            </CardTitle>
          </CardHeader>
          <CardContent className="p-5 text-sm text-muted-foreground">
            Press{" "}
            <kbd className="text-[10px] font-mono border border-border rounded px-1 py-0.5">
              ⌘K
            </kbd>{" "}
            or{" "}
            <kbd className="text-[10px] font-mono border border-border rounded px-1 py-0.5">
              /
            </kbd>{" "}
            anywhere to search files and jump between routes.
          </CardContent>
        </Card>
      </div>
    </Section>
  );
}
