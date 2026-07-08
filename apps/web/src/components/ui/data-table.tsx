"use client";

import {
  flexRender,
  getCoreRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type SortingState,
} from "@tanstack/react-table";
import { useState } from "react";
import { ChevronDown, ChevronUp, ChevronsUpDown } from "lucide-react";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";

interface DataTableProps<TData, TValue> {
  columns: ColumnDef<TData, TValue>[];
  data: TData[];
  pageSize?: number;
  emptyTitle?: string;
  emptyDescription?: string;
}

/**
 * Reusable sortable + paginated table wrapper built on @tanstack/react-table.
 * Use for any list with > ~25 rows. For small static lists, stick with the
 * bare <Table> primitive.
 */
export function DataTable<TData, TValue>({
  columns,
  data,
  pageSize = 10,
  emptyTitle = "No results",
  emptyDescription,
}: DataTableProps<TData, TValue>) {
  const [sorting, setSorting] = useState<SortingState>([]);
  // TanStack Table v8 returns mutable functions that the React Compiler
  // can't memoize safely; the team is aware and this is the documented
  // workaround. Re-evaluate when migrating to a future Compiler-friendly
  // version of @tanstack/react-table.
  // eslint-disable-next-line react-hooks/incompatible-library
  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    onSortingChange: setSorting,
    state: { sorting },
    initialState: { pagination: { pageSize } },
  });

  const totalRows = data.length;
  const { pageIndex, pageSize: ps } = table.getState().pagination;
  const from = totalRows === 0 ? 0 : pageIndex * ps + 1;
  const to = Math.min((pageIndex + 1) * ps, totalRows);

  return (
    <div className="space-y-3">
      <div className="rounded-md border border-border overflow-hidden">
        <Table className="table-fixed">
          <TableHeader>
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow
                key={headerGroup.id}
                className="bg-muted/40 hover:bg-muted/40"
              >
                {headerGroup.headers.map((header) => {
                  const sort = header.column.getIsSorted();
                  const canSort = header.column.getCanSort();
                  // Respect explicit column sizes from the column def
                  // (e.g. `size: 280`) to keep header+body widths in sync.
                  const width = header.getSize();
                  const hasExplicitSize =
                    header.column.columnDef.size !== undefined;
                  return (
                    <TableHead
                      key={header.id}
                      style={hasExplicitSize ? { width } : undefined}
                      className="text-xs font-semibold uppercase tracking-wider text-muted-foreground"
                    >
                      {header.isPlaceholder ? null : canSort ? (
                        <button
                          type="button"
                          onClick={header.column.getToggleSortingHandler()}
                          className="flex items-center gap-1 hover:text-foreground transition-colors"
                        >
                          {flexRender(
                            header.column.columnDef.header,
                            header.getContext()
                          )}
                          {sort === "asc" ? (
                            <ChevronUp className="h-3 w-3" />
                          ) : sort === "desc" ? (
                            <ChevronDown className="h-3 w-3" />
                          ) : (
                            <ChevronsUpDown className="h-3 w-3 opacity-40" />
                          )}
                        </button>
                      ) : (
                        flexRender(
                          header.column.columnDef.header,
                          header.getContext()
                        )
                      )}
                    </TableHead>
                  );
                })}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows.length === 0 ? (
              <TableRow>
                <TableCell colSpan={columns.length}>
                  <EmptyState
                    title={emptyTitle}
                    description={emptyDescription}
                  />
                </TableCell>
              </TableRow>
            ) : (
              table.getRowModel().rows.map((row) => (
                <TableRow key={row.id} className="table-row-hover">
                  {row.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id}>
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span className="tabular-nums">
          {totalRows === 0
            ? "No results"
            : `Showing ${from}–${to} of ${totalRows}`}
        </span>
        <div className="flex items-center gap-1">
          <Button
            variant="outline"
            size="sm"
            onClick={() => table.previousPage()}
            disabled={!table.getCanPreviousPage()}
            className="h-7 text-xs"
          >
            Previous
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => table.nextPage()}
            disabled={!table.getCanNextPage()}
            className="h-7 text-xs"
          >
            Next
          </Button>
        </div>
      </div>
    </div>
  );
}
