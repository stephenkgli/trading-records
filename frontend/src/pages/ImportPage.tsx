import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import CsvUpload from "../components/CsvUpload";
import {
  uploadCsv,
  fetchImportLogs,
  type ImportResult,
} from "../api/client";

export default function ImportPage() {
  const queryClient = useQueryClient();
  const [lastResult, setLastResult] = useState<ImportResult | null>(null);

  const csvMutation = useMutation({
    mutationFn: uploadCsv,
    onSuccess: (result) => {
      setLastResult(result);
      queryClient.invalidateQueries({ queryKey: ["trades"] });
      queryClient.invalidateQueries({ queryKey: ["importLogs"] });
    },
  });

  const { data: logsData } = useQuery({
    queryKey: ["importLogs"],
    queryFn: () => fetchImportLogs(),
  });

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Import Data</h1>

      {/* CSV Upload */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-medium mb-4">CSV Upload</h2>
        <CsvUpload
          onUpload={(file) => csvMutation.mutate(file)}
          isLoading={csvMutation.isPending}
        />
        {csvMutation.error && (
          <p className="mt-2 text-sm text-red-500">
            {(csvMutation.error as Error).message}
          </p>
        )}
      </div>

      {/* Last Result */}
      {lastResult && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-medium mb-3">Last Import Result</h2>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
            <div>
              <span className="text-gray-500">Status</span>
              <p className={`font-medium ${lastResult.status === "success" ? "text-green-600" : lastResult.status === "failed" ? "text-red-600" : "text-yellow-600"}`}>
                {lastResult.status}
              </p>
            </div>
            <div>
              <span className="text-gray-500">Total</span>
              <p className="font-medium">{lastResult.records_total}</p>
            </div>
            <div>
              <span className="text-gray-500">Imported</span>
              <p className="font-medium text-green-600">{lastResult.records_imported}</p>
            </div>
            <div>
              <span className="text-gray-500">Skipped (dup)</span>
              <p className="font-medium text-gray-600">{lastResult.records_skipped_dup}</p>
            </div>
          </div>
        </div>
      )}

      {/* Import History */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-medium mb-3">Import History</h2>
        {logsData && logsData.logs.length > 0 ? (
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Date</th>
                <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Broker</th>
                <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Trade Period</th>
                <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Imported</th>
                <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Skipped</th>
                <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Failed</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {logsData.logs.map((log) => (
                <tr key={log.id}>
                  <td className="px-3 py-2">
                    {new Intl.DateTimeFormat(undefined, { dateStyle: "short", timeStyle: "short" }).format(new Date(log.started_at))}
                  </td>
                  <td className="px-3 py-2">
                    <span className="inline-block px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-700">
                      {log.broker || log.source}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-xs text-gray-600">
                    {log.trade_date_from && log.trade_date_to ? (
                      <>
                        {new Intl.DateTimeFormat(undefined, { dateStyle: "short", timeStyle: "short" }).format(new Date(log.trade_date_from))}
                        <span className="mx-1">→</span>
                        {new Intl.DateTimeFormat(undefined, { dateStyle: "short", timeStyle: "short" }).format(new Date(log.trade_date_to))}
                      </>
                    ) : (
                      <span className="text-gray-400">—</span>
                    )}
                  </td>
                  <td className="px-3 py-2">
                    <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${
                      log.status === "success" ? "bg-green-100 text-green-700" :
                      log.status === "failed" ? "bg-red-100 text-red-700" :
                      "bg-yellow-100 text-yellow-700"
                    }`}>
                      {log.status}
                    </span>
                  </td>
                  <td className="px-3 py-2">{log.records_imported}</td>
                  <td className="px-3 py-2">{log.records_skipped_dup}</td>
                  <td className="px-3 py-2">{log.records_failed}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="text-gray-400 text-sm">No imports yet</p>
        )}
      </div>
    </div>
  );
}
