import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { fetchGroups, recomputeGroups, type TradeGroup } from "../api/client";
import { useMutation, useQueryClient } from "@tanstack/react-query";

export default function GroupsPage() {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState<string>("");

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

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Trade Groups</h1>
        <div className="flex items-center space-x-2">
          <select
            className="border border-gray-300 rounded-md px-3 py-1.5 text-sm"
            value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
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

      {isLoading && <div className="text-center py-8 text-gray-400">Loading...</div>}

      {data && (
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Symbol</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Direction</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">P&L</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Opened</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Closed</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Tag</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {data.groups.map((group: TradeGroup) => (
                <tr key={group.id} className="hover:bg-gray-50">
                  <td className="px-4 py-2 font-medium">{group.symbol}</td>
                  <td className="px-4 py-2">
                    <span className={group.direction === "long" ? "text-green-600" : "text-red-600"}>
                      {group.direction.toUpperCase()}
                    </span>
                  </td>
                  <td className="px-4 py-2">
                    <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${
                      group.status === "open" ? "bg-blue-100 text-blue-700" : "bg-gray-100 text-gray-700"
                    }`}>
                      {group.status}
                    </span>
                  </td>
                  <td className="px-4 py-2">
                    {group.realized_pnl !== null ? (
                      <span className={Number(group.realized_pnl) >= 0 ? "text-green-600" : "text-red-600"}>
                        ${Number(group.realized_pnl).toFixed(2)}
                      </span>
                    ) : (
                      <span className="text-gray-400">-</span>
                    )}
                  </td>
                  <td className="px-4 py-2 text-gray-500">
                    {new Intl.DateTimeFormat(undefined, { dateStyle: "short" }).format(new Date(group.opened_at))}
                  </td>
                  <td className="px-4 py-2 text-gray-500">
                    {group.closed_at
                      ? new Intl.DateTimeFormat(undefined, { dateStyle: "short" }).format(new Date(group.closed_at))
                      : "-"}
                  </td>
                  <td className="px-4 py-2 text-gray-500">{group.strategy_tag || "-"}</td>
                </tr>
              ))}
              {data.groups.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-gray-400">
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
