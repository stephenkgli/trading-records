import { useQuery } from "@tanstack/react-query";
import { useState, useMemo } from "react";
import { fetchGroups, recomputeGroups, type TradeGroup } from "../api/client";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  useReactTable,
  getCoreRowModel,
  flexRender,
  type ColumnDef,
  type SortingState,
} from "@tanstack/react-table";
import TradeChartModal from "../components/TradeChartModal";
import { formatDateTime } from "../utils/date";

export default function GroupsPage() {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [sorting, setSorting] = useState<SortingState>([
    { id: "opened_at", desc: true },
  ]);
  const [selectedGroupId, setSelectedGroupId] = useState<string | null>(null);
  const sortParam = sorting[0]?.id;
  const orderParam: "asc" | "desc" | undefined = sorting[0]
    ? (sorting[0].desc ? "desc" : "asc")
    : undefined;

  const { data, isLoading } = useQuery({
    queryKey: ["groups", page, statusFilter, sortParam, orderParam],
    queryFn: () =>
      fetchGroups(
        page,
        statusFilter || undefined,
        undefined,
        sortParam,
        orderParam
      ),
  });

  const recomputeMutation = useMutation({
    mutationFn: () => recomputeGroups(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["groups"] });
    },
  });

  const perPage = data?.per_page ?? 50;
  const pageOffset = (page - 1) * perPage;

  const columns = useMemo<ColumnDef<TradeGroup>[]>(
    () => [
      {
        id: "rowNumber",
        header: "#",
        cell: ({ row }) => pageOffset + row.index + 1,
        enableSorting: false,
      },
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
        cell: ({ getValue }) => formatDateTime(getValue() as string),
      },
      {
        accessorKey: "closed_at",
        header: "Closed",
        cell: ({ getValue }) => {
          const val = getValue() as string | null;
          return formatDateTime(val);
        },
      },

    ],
    [pageOffset]
  );

  const table = useReactTable({
    data: data?.groups ?? [],
    columns,
    state: { sorting },
    onSortingChange: (updater) => {
      setSorting((prev) => {
        const next = typeof updater === "function" ? updater(prev) : updater;
        setPage(1);
        return next;
      });
    },
    manualSorting: true,
    getCoreRowModel: getCoreRowModel(),
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
          <div className="px-4 py-2 bg-gray-50 border-b text-sm text-gray-500">
            共 {data.total} 个交易组
          </div>
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
                <tr
                  key={row.id}
                  className="hover:bg-gray-50 cursor-pointer"
                  onClick={() => setSelectedGroupId(row.original.id)}
                >
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

      {data && data.total > (data.per_page ?? 50) && (
        <div className="flex items-center justify-between">
          <button
            disabled={page <= 1}
            onClick={() => setPage((p) => p - 1)}
            className="px-3 py-1.5 text-sm border rounded-md disabled:opacity-50 hover:bg-gray-50"
          >
            上一页
          </button>
          <span className="text-sm text-gray-500">
            第 {page} / {Math.ceil(data.total / (data.per_page ?? 50))} 页
          </span>
          <button
            disabled={page >= Math.ceil(data.total / (data.per_page ?? 50))}
            onClick={() => setPage((p) => p + 1)}
            className="px-3 py-1.5 text-sm border rounded-md disabled:opacity-50 hover:bg-gray-50"
          >
            下一页
          </button>
        </div>
      )}

      {selectedGroupId && (
        <TradeChartModal
          groupId={selectedGroupId}
          onClose={() => setSelectedGroupId(null)}
        />
      )}
    </div>
  );
}
