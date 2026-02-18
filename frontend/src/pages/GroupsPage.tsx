import { useQuery } from "@tanstack/react-query";
import { useState, useMemo } from "react";
import { fetchGroups, recomputeGroups, type TradeGroup } from "../api/client";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  flexRender,
  type ColumnDef,
  type SortingState,
} from "@tanstack/react-table";

export default function GroupsPage() {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [sorting, setSorting] = useState<SortingState>([]);

  const { data, isLoading } = useQuery({
    queryKey: ["groups", page, statusFilter],
    queryFn: () => fetchGroups(page, statusFilter || undefined),
  });

  const recomputeMutation = useMutation({
    mutationFn: () => recomputeGroups(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["groups"] });
    },
  });

  const columns = useMemo<ColumnDef<TradeGroup>[]>(
    () => [
      {
        accessorKey: "symbol",
        header: "Symbol",
        cell: ({ getValue }) => (
          <span className="font-medium">{getValue() as string}</span>
        ),
      },
      {
        accessorKey: "direction",
        header: "Direction",
        cell: ({ getValue }) => {
          const dir = getValue() as string;
          return (
            <span className={dir === "long" ? "text-green-600" : "text-red-600"}>
              {dir.toUpperCase()}
            </span>
          );
        },
      },
      {
        accessorKey: "status",
        header: "Status",
        cell: ({ getValue }) => {
          const status = getValue() as string;
          return (
            <span
              className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${
                status === "open"
                  ? "bg-blue-100 text-blue-700"
                  : "bg-gray-100 text-gray-700"
              }`}
            >
              {status}
            </span>
          );
        },
      },
      {
        accessorKey: "realized_pnl",
        header: "P&L",
        sortingFn: (rowA, rowB) => {
          const a = Number(rowA.original.realized_pnl) || 0;
          const b = Number(rowB.original.realized_pnl) || 0;
          return a - b;
        },
        cell: ({ getValue }) => {
          const val = getValue() as string | null;
          if (val === null) return <span className="text-gray-400">-</span>;
          const num = Number(val);
          return (
            <span className={num >= 0 ? "text-green-600" : "text-red-600"}>
              ${num.toFixed(2)}
            </span>
          );
        },
      },
      {
        accessorKey: "opened_at",
        header: "Opened",
        cell: ({ getValue }) =>
          new Intl.DateTimeFormat(undefined, { dateStyle: "short" }).format(
            new Date(getValue() as string)
          ),
      },
      {
        accessorKey: "closed_at",
        header: "Closed",
        sortingFn: (rowA, rowB) => {
          const a = rowA.original.closed_at
            ? new Date(rowA.original.closed_at).getTime()
            : 0;
          const b = rowB.original.closed_at
            ? new Date(rowB.original.closed_at).getTime()
            : 0;
          return a - b;
        },
        cell: ({ getValue }) => {
          const val = getValue() as string | null;
          return val
            ? new Intl.DateTimeFormat(undefined, { dateStyle: "short" }).format(
                new Date(val)
              )
            : "-";
        },
      },
      {
        accessorKey: "strategy_tag",
        header: "Tag",
        cell: ({ getValue }) => {
          const val = getValue() as string | null;
          return <span className="text-gray-500">{val || "-"}</span>;
        },
      },
    ],
    []
  );

  const table = useReactTable({
    data: data?.groups ?? [],
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Trade Groups</h1>
        <div className="flex items-center space-x-2">
          <select
            className="border border-gray-300 rounded-md px-3 py-1.5 text-sm"
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(1);
            }}
          >
            <option value="">All Status</option>
            <option value="open">Open</option>
            <option value="closed">Closed</option>
          </select>
          <button
            onClick={() => recomputeMutation.mutate()}
            disabled={recomputeMutation.isPending}
            className="bg-blue-600 text-white px-3 py-1.5 rounded-md text-sm hover:bg-blue-700 disabled:opacity-50"
          >
            {recomputeMutation.isPending ? "Recomputing..." : "Recompute"}
          </button>
        </div>
      </div>

      {isLoading && (
        <div className="text-center py-8 text-gray-400">Loading...</div>
      )}

      {data && (
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead className="bg-gray-50">
              {table.getHeaderGroups().map((headerGroup) => (
                <tr key={headerGroup.id}>
                  {headerGroup.headers.map((header) => (
                    <th
                      key={header.id}
                      onClick={header.column.getToggleSortingHandler()}
                      className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer select-none hover:bg-gray-100"
                    >
                      <div className="flex items-center gap-1">
                        {flexRender(
                          header.column.columnDef.header,
                          header.getContext()
                        )}
                        <span className="text-gray-400">
                          {{ asc: "↑", desc: "↓" }[
                            header.column.getIsSorted() as string
                          ] ?? "⇅"}
                        </span>
                      </div>
                    </th>
                  ))}
                </tr>
              ))}
            </thead>
            <tbody className="divide-y divide-gray-200">
              {table.getRowModel().rows.map((row) => (
                <tr key={row.id} className="hover:bg-gray-50">
                  {row.getVisibleCells().map((cell) => (
                    <td
                      key={cell.id}
                      className="px-4 py-2 whitespace-nowrap"
                    >
                      {flexRender(
                        cell.column.columnDef.cell,
                        cell.getContext()
                      )}
                    </td>
                  ))}
                </tr>
              ))}
              {table.getRowModel().rows.length === 0 && (
                <tr>
                  <td
                    colSpan={columns.length}
                    className="px-4 py-8 text-center text-gray-400"
                  >
                    No trade groups found
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
