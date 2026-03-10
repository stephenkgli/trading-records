import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { fetchGroupDetail } from "../api/client";
import { formatDateTime } from "../utils/date";

export default function GroupDetailPage() {
  const { id = "" } = useParams();
  const { data, isLoading, error } = useQuery({
    queryKey: ["groupDetail", id],
    queryFn: () => fetchGroupDetail(id),
    enabled: Boolean(id),
  });

  if (isLoading) return <div className="text-gray-400">Loading group\u2026</div>;
  if (error) return <div className="text-red-500">Error: {(error as Error).message}</div>;
  if (!data) return <div className="text-gray-400">Group not found.</div>;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Group Detail</h1>
        <Link to="/groups" className="text-sm text-blue-600 hover:text-blue-700">
          Back to Groups
        </Link>
      </div>
      <div className="bg-white rounded-lg shadow p-6 text-sm space-y-2">
        <p><span className="text-gray-500">Symbol:</span> {data.symbol}</p>
        <p><span className="text-gray-500">Direction:</span> {data.direction}</p>
        <p><span className="text-gray-500">Status:</span> {data.status}</p>
        <p><span className="text-gray-500">P&L:</span> {data.realized_pnl ?? "-"}</p>
        <p><span className="text-gray-500">Opened:</span> {formatDateTime(data.opened_at)}</p>
        <p><span className="text-gray-500">Closed:</span> {formatDateTime(data.closed_at)}</p>
      </div>

      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-sm font-medium text-gray-500 mb-3">Legs</h2>
        <ul className="text-sm space-y-1">
          {data.legs.map((leg) => (
            <li key={leg.id} className="text-gray-700">
              {leg.role} - {leg.trade_id}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
