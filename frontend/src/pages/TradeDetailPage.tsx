import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { fetchTradeDetail } from "../api/client";

export default function TradeDetailPage() {
  const { id = "" } = useParams();
  const { data, isLoading, error } = useQuery({
    queryKey: ["tradeDetail", id],
    queryFn: () => fetchTradeDetail(id),
    enabled: Boolean(id),
  });

  if (isLoading) return <div className="text-gray-400">Loading trade...</div>;
  if (error) return <div className="text-red-500">Error: {(error as Error).message}</div>;
  if (!data) return <div className="text-gray-400">Trade not found.</div>;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Trade Detail</h1>
        <Link to="/trades" className="text-sm text-blue-600 hover:text-blue-700">
          Back to Trades
        </Link>
      </div>
      <div className="bg-white rounded-lg shadow p-6 text-sm space-y-2">
        <p><span className="text-gray-500">Symbol:</span> {data.symbol}</p>
        <p><span className="text-gray-500">Broker:</span> {data.broker}</p>
        <p><span className="text-gray-500">Side:</span> {data.side}</p>
        <p><span className="text-gray-500">Quantity:</span> {data.quantity}</p>
        <p><span className="text-gray-500">Price:</span> {data.price}</p>
        <p><span className="text-gray-500">Executed:</span> {new Date(data.executed_at).toLocaleString()}</p>
        <p><span className="text-gray-500">Account:</span> {data.account_id}</p>
        <p><span className="text-gray-500">Exec ID:</span> {data.broker_exec_id}</p>
      </div>
    </div>
  );
}
