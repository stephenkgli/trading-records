import { useQuery, useMutation, useQueryClient, keepPreviousData } from "@tanstack/react-query";
import { useState, useMemo, useCallback, lazy, Suspense } from "react";
import { createPortal } from "react-dom";
import {
  fetchGroups,
  recomputeGroups,
  type TradeGroup,
} from "../api/client";
import {
  useReactTable,
  getCoreRowModel,
  flexRender,
  type ColumnDef,
  type SortingState,
} from "@tanstack/react-table";
import AssetClassFilter from "../components/AssetClassFilter";
import { useAssetClassFilter } from "../hooks/useAssetClassFilter";
import { useDropdownPortal } from "../hooks/useDropdownPortal";
import { formatDateTime } from "../utils/date";

const TradeChartModal = lazy(() => import("../components/TradeChartModal"));

const preloadChart = () => void import("../components/TradeChartModal");

const STATUS_OPTIONS = [
  { value: "", label: "All Status" },
  { value: "open", label: "Open" },
  { value: "closed", label: "Closed" },
] as const;

type GroupsTableMeta = {
  pageOffset: number;
};

export default function GroupsPage() {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const statusDropdown = useDropdownPortal();

  const {
    availableAssetClasses,
    selectedAssetClasses,
    setSelectedAssetClasses,
    assetClassesParam,
    isInitialized,
  } = useAssetClassFilter("groups_asset_class_filter");
  const [sorting, setSorting] = useState<SortingState>([
    { id: "opened_at", desc: true },
  ]);
  const [selectedGroupId, setSelectedGroupId] = useState<string | null>(null);
  const sortParam = sorting[0]?.id;
  const orderParam: "asc" | "desc" | undefined = sorting[0]
    ? (sorting[0].desc ? "desc" : "asc")
    : undefined;

  const { data, isLoading, isPlaceholderData } = useQuery({
    queryKey: [
      "groups",
      { page, status: statusFilter, sort: sortParam, order: orderParam, assetClasses: assetClassesParam },
    ],
    queryFn: () =>
      fetchGroups(
        page,
        statusFilter || undefined,
        undefined,
        sortParam,
        orderParam,
        assetClassesParam,
      ),
    enabled: isInitialized,
    placeholderData: keepPreviousData,
  });

  const isGroupsLoading = !isInitialized || isLoading;

  const recomputeMutation = useMutation({
    mutationFn: () => recomputeGroups(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["groups"] });
    },
  });

  const perPage = data?.per_page ?? 50;
  const pageOffset = (page - 1) * perPage;
  const handleAssetClassChange = useCallback((acs: string[]) => {
    setSelectedAssetClasses(acs);
    setPage(1);
  }, [setSelectedAssetClasses]);

  const columns = useMemo<ColumnDef<TradeGroup>[]>(
    () => [
      {
        id: "rowNumber",
        header: "#",
        cell: ({ row, table }) =>
          ((table.options.meta as GroupsTableMeta | undefined)?.pageOffset ?? 0) + row.index + 1,
        enableSorting: false,
        size: 48,
      },
      {
        accessorKey: "symbol",
        header: "Symbol",
        cell: ({ getValue }) => (
          <span className="font-medium text-[--color-text-primary]">{getValue() as string}</span>
        ),
      },
      {
        accessorKey: "direction",
        header: "Direction",
        cell: ({ getValue }) => {
          const dir = getValue() as string;
          return (
            <span
              className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${
                dir === "long"
                  ? "bg-profit-subtle text-profit"
                  : "bg-loss-subtle text-loss"
              }`}
            >
              {dir}
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
              className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${
                status === "open"
                  ? "bg-accent-subtle text-accent-hover"
                  : "bg-elevated text-[--color-text-secondary]"
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
        size: 120,
        cell: ({ getValue }) => {
          const val = getValue() as string | null;
          if (val === null) return <span className="text-[--color-text-muted]">&mdash;</span>;
          const num = Number(val);
          return (
            <span
              className={`font-mono font-medium ${num >= 0 ? "text-profit" : "text-loss"}`}
              style={{ fontVariantNumeric: "tabular-nums" }}
            >
              {num >= 0 ? "+" : ""}${num.toFixed(2)}
            </span>
          );
        },
      },
      {
        accessorKey: "opened_at",
        header: "Opened",
        cell: ({ getValue }) => (
          <span className="text-[--color-text-secondary] text-xs">{formatDateTime(getValue() as string)}</span>
        ),
      },
      {
        accessorKey: "closed_at",
        header: "Closed",
        cell: ({ getValue }) => {
          const val = getValue() as string | null;
          return (
            <span className="text-[--color-text-secondary] text-xs">{formatDateTime(val)}</span>
          );
        },
      },

    ],
    []
  );

  const table = useReactTable<TradeGroup>({
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
    meta: { pageOffset },
  });

  const totalPages = data ? Math.ceil(data.total / (data.per_page ?? 50)) : 0;

  return (
    <div className="stagger-in space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <h1 className="font-display text-3xl text-[--color-text-primary] tracking-tight">Trade Groups</h1>
        <div className="flex flex-wrap items-center gap-2">
          <AssetClassFilter
            availableAssetClasses={availableAssetClasses}
            selectedAssetClasses={selectedAssetClasses ?? []}
            onChange={handleAssetClassChange}
          />
          <div className="relative">
            <button
              ref={statusDropdown.triggerRef}
              onClick={statusDropdown.toggle}
              aria-haspopup="listbox"
              aria-expanded={statusDropdown.open}
              aria-label="Filter by status"
              className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border transition-all duration-150 focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none ${
                statusFilter
                  ? "border-accent/40 bg-accent-subtle text-accent-hover hover:bg-accent/20"
                  : "border-[--color-border] bg-elevated text-[--color-text-secondary] hover:bg-[--color-bg-hover]"
              }`}
            >
              {STATUS_OPTIONS.find((o) => o.value === statusFilter)?.label ?? "All Status"}
              <svg
                className={`w-3 h-3 transition-transform ${statusDropdown.open ? "rotate-180" : ""}`}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
                aria-hidden="true"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>
            {statusDropdown.open && createPortal(
              <div
                ref={statusDropdown.dropdownRef}
                className="fixed w-40 bg-surface rounded-lg shadow-lg border border-[--color-border] z-[100] backdrop-blur-xl py-1"
                style={statusDropdown.dropdownStyle}
                onKeyDown={(e) => { if (e.key === "Escape") statusDropdown.close(); }}
              >
                {STATUS_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    onClick={() => {
                      setStatusFilter(opt.value);
                      setPage(1);
                      statusDropdown.close();
                    }}
                    className={`w-full text-left px-3 py-2 text-xs transition-colors focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none ${
                      statusFilter === opt.value
                        ? "bg-accent-subtle text-accent-hover font-medium"
                        : "text-[--color-text-secondary] hover:bg-[--color-bg-hover]"
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>,
              document.body,
            )}
          </div>
          <button
            onClick={() => recomputeMutation.mutate()}
            disabled={recomputeMutation.isPending}
            className="bg-accent text-white px-3 py-1.5 rounded-lg text-xs font-medium hover:bg-accent-hover disabled:opacity-50 transition-colors focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none"
          >
            {recomputeMutation.isPending ? "Recomputing\u2026" : "Recompute"}
          </button>
        </div>
      </div>

      {isGroupsLoading && (
        <div className="bg-surface rounded-lg border border-[--color-border] p-8">
          <div className="space-y-3">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="h-10 bg-elevated animate-pulse rounded" />
            ))}
          </div>
        </div>
      )}

      {data && (
        <div className={`bg-surface rounded-lg border border-[--color-border] overflow-hidden transition-opacity ${isPlaceholderData ? "opacity-60" : ""}`}>
          <div className="px-4 py-2.5 border-b border-[--color-border] flex items-center justify-between">
            <span className="text-xs text-[--color-text-muted] uppercase tracking-wider font-medium">
              {data.total} groups
            </span>
            {totalPages > 1 && (
              <span className="text-xs text-[--color-text-muted] font-mono">
                {page} / {totalPages}
              </span>
            )}
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm" style={{ tableLayout: "fixed" }}>
              <thead>
                {table.getHeaderGroups().map((headerGroup) => (
                  <tr key={headerGroup.id} className="border-b border-[--color-border]">
                    {headerGroup.headers.map((header) => {
                      const canSort = header.column.getCanSort();
                      const sorted = header.column.getIsSorted();
                      const ariaSortValue = sorted === "asc" ? "ascending" as const : sorted === "desc" ? "descending" as const : "none" as const;
                      return (
                      <th
                        key={header.id}
                        onClick={canSort ? header.column.getToggleSortingHandler() : undefined}
                        onKeyDown={canSort ? (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); header.column.getToggleSortingHandler()?.(e); } } : undefined}
                        tabIndex={canSort ? 0 : undefined}
                        role="columnheader"
                        aria-sort={canSort ? ariaSortValue : undefined}
                        style={header.column.columnDef.size ? { width: header.column.getSize() } : undefined}
                        className={`px-4 py-2.5 text-left text-[10px] font-medium text-[--color-text-muted] uppercase tracking-widest select-none transition-colors ${
                          canSort
                            ? "cursor-pointer hover:text-[--color-text-secondary] hover:bg-[--color-bg-hover] focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none"
                            : ""
                        }`}
                      >
                        <div className="flex items-center gap-1">
                          {flexRender(
                            header.column.columnDef.header,
                            header.getContext()
                          )}
                          {canSort && (
                            <span className="text-[--color-text-muted]">
                              {{ asc: "\u2191", desc: "\u2193" }[
                                header.column.getIsSorted() as string
                              ] ?? "\u21C5"}
                            </span>
                          )}
                        </div>
                      </th>
                      );
                    })}
                  </tr>
                ))}
              </thead>
              <tbody>
                {table.getRowModel().rows.map((row, rowIdx) => (
                  <tr
                    key={row.id}
                    className={`table-row-hover border-b border-[--color-border] cursor-pointer transition-colors ${rowIdx % 2 === 1 ? "bg-[rgba(255,255,255,0.015)]" : ""}`}
                    onClick={() => setSelectedGroupId(row.original.id)}
                    onMouseEnter={preloadChart}
                    tabIndex={0}
                    role="button"
                    onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setSelectedGroupId(row.original.id); } }}
                  >
                    {row.getVisibleCells().map((cell) => (
                      <td
                        key={cell.id}
                        className="px-4 py-2.5 whitespace-nowrap text-[--color-text-secondary]"
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
                      className="px-4 py-12 text-center"
                    >
                      <div className="flex flex-col items-center gap-2">
                        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="var(--color-text-muted)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="opacity-50">
                          <path d="M13 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V9z" />
                          <polyline points="13 2 13 9 20 9" />
                        </svg>
                        <p className="text-[--color-text-muted] text-sm">No trade groups found</p>
                      </div>
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {data && totalPages > 1 && (
        <div className="flex items-center justify-center gap-3">
          <button
            disabled={page <= 1}
            onClick={() => setPage((p) => p - 1)}
            aria-label="Previous page"
            className="px-3 py-1.5 text-sm border border-[--color-border] rounded-lg text-[--color-text-secondary] disabled:opacity-30 hover:bg-[--color-bg-hover] transition-colors focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="inline-block" aria-hidden="true"><path d="M10 12L6 8l4-4"/></svg>
          </button>
          <span className="text-xs text-[--color-text-muted] font-mono min-w-[60px] text-center">
            {page} / {totalPages}
          </span>
          <button
            disabled={page >= totalPages}
            onClick={() => setPage((p) => p + 1)}
            aria-label="Next page"
            className="px-3 py-1.5 text-sm border border-[--color-border] rounded-lg text-[--color-text-secondary] disabled:opacity-30 hover:bg-[--color-bg-hover] transition-colors focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="inline-block" aria-hidden="true"><path d="M6 4l4 4-4 4"/></svg>
          </button>
        </div>
      )}

      {selectedGroupId && (
        <Suspense fallback={null}>
          <TradeChartModal
            groupId={selectedGroupId}
            onClose={() => setSelectedGroupId(null)}
          />
        </Suspense>
      )}
    </div>
  );
}
