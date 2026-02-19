import { useQuery } from "@tanstack/react-query";
import { fetchGroupChart } from "../api/endpoints/groups";
import CandlestickChart from "./CandlestickChart";

interface Props {
  groupId: string;
  onClose: () => void;
}

export default function TradeChartModal({ groupId, onClose }: Props) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["groupChart", groupId],
    queryFn: () => fetchGroupChart(groupId),
  });

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-lg shadow-xl w-[920px] max-h-[90vh] overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <div className="flex items-center gap-3">
            <h2 className="text-lg font-semibold">
              {data?.symbol ?? "Loading..."}
            </h2>
            {data?.group && (
              <>
                <span
                  className={
                    data.group.direction === "long"
                      ? "text-green-600"
                      : "text-red-600"
                  }
                >
                  {data.group.direction.toUpperCase()}
                </span>
                <span className="text-sm text-gray-500">
                  P&L: {data.group.realized_pnl ?? "open"}
                </span>
              </>
            )}
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 text-xl leading-none"
          >
            &times;
          </button>
        </div>

        <div className="p-4">
          {isLoading && (
            <div className="flex items-center justify-center h-[400px] text-gray-400">
              Loading chart data...
            </div>
          )}
          {error && (
            <div className="flex flex-col items-center justify-center h-[400px] text-red-500 gap-2">
              <span>Failed to load chart data</span>
              <span className="text-sm text-gray-400">
                This may be a temporary issue (rate limit) or the symbol may not
                be available. Please try again later.
              </span>
            </div>
          )}
          {data && (
            <CandlestickChart candles={data.candles} markers={data.markers} />
          )}
        </div>
      </div>
    </div>
  );
}
