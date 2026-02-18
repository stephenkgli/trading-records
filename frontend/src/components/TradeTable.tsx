import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  flexRender,
  type ColumnDef,
  type SortingState,
} from "@tanstack/react-table";
import { useState, useMemo } from "react";
import type { Trade } from "../api/client";

interface TradeTableProps {
  trades: Trade[];
}

export default function TradeTable({ trades }: TradeTableProps) {
  const [sorting, setSorting] = useState<SortingState>([]);

  const columns = useMemo<ColumnDef<Trade>[]>(
    () => [
      {
        accessorKey: "executed_at",
        header: "Date/Time",
        cell: ({ getValue }) => {
          const dt = new Date(getValue() as string);
          return new Intl.DateTimeFormat(undefined, {
            dateStyle: "short",
            timeStyle: "medium",
          }).format(dt);
        },
      },
      { accessorKey: "symbol", header: "Symbol" },
      { accessorKey: "side", header: "Side",
        cell: ({ getValue }) => {
          const side = getValue() as string;
          return (
            <span className={side === "buy" ? "text-green-600 font-medium" : "text-red-600 font-medium"}>
              {side.toUpperCase()}
            </span>
          );
        },
      },
      { accessorKey: "quantity", header: "Qty" },
      {
        accessorKey: "price",
        header: "Price",
        cell: ({ getValue }) => Number(getValue()).toFixed(2),
      },
      {
        accessorKey: "commission",
        header: "Comm",
        cell: ({ getValue }) => Number(getValue()).toFixed(2),
      },
      { accessorKey: "asset_class", header: "Asset" },
      { accessorKey: "broker", header: "Broker" },
      { accessorKey: "account_id", header: "Account" },
    ],
    []
  );

  const table = useReactTable({
    data: trades,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          {table.getHeaderGroups().map((headerGroup) => (
            <tr key={headerGroup.id}>
              {headerGroup.headers.map((header) => (
                <th
                  key={header.id}
                  onClick={header.column.getToggleSortingHandler()}
                  className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer select-none hover:bg-gray-100"
                >
                  {flexRender(header.column.columnDef.header, header.getContext())}
                  {{ asc: " ↑", desc: " ↓" }[header.column.getIsSorted() as string] ?? ""}
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody className="bg-white divide-y divide-gray-200">
          {table.getRowModel().rows.map((row) => (
            <tr key={row.id} className="hover:bg-gray-50">
              {row.getVisibleCells().map((cell) => (
                <td key={cell.id} className="px-4 py-2 text-sm whitespace-nowrap">
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </td>
              ))}
            </tr>
          ))}
          {table.getRowModel().rows.length === 0 && (
            <tr>
              <td colSpan={columns.length} className="px-4 py-8 text-center text-gray-400">
                No trades found
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
