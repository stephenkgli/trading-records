import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import CsvUpload from "../components/CsvUpload";
import {
  uploadCsv,
  fetchImportLogs,
  type BatchImportResponse,
  type ImportLog,
} from "../api/client";

function getStatusTextClass(status: string): string {
  if (status === "success") return "text-green-600";
  if (status === "failed") return "text-red-600";
  return "text-yellow-600";
}

function getStatusBadgeClass(status: string): string {
  if (status === "success") return "bg-green-100 text-green-700";
  if (status === "failed") return "bg-red-100 text-red-700";
  return "bg-yellow-100 text-yellow-700";
}

function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "short",
    timeStyle: "short",
  }).format(new Date(value));
}

function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${getStatusBadgeClass(status)}`}
    >
      {status}
    </span>
  );
}

function LastImportResultCard({ result }: { result: BatchImportResponse }) {
  return (
    <div className="bg-white rounded-lg shadow p-6 space-y-4">
      <h2 className="text-lg font-medium">Last Import Result</h2>

      <div className="grid grid-cols-2 sm:grid-cols-5 gap-4 text-sm">
        <div>
          <span className="text-gray-500">Batch Status</span>
          <p className={`font-medium ${getStatusTextClass(result.aggregate.status)}`}>
            {result.aggregate.status}
          </p>
        </div>
        <div>
          <span className="text-gray-500">Files</span>
          <p className="font-medium">{result.aggregate.files_total}</p>
        </div>
        <div>
          <span className="text-gray-500">Imported</span>
          <p className="font-medium text-green-600">
            {result.aggregate.records_imported}
          </p>
        </div>
        <div>
          <span className="text-gray-500">Skipped (dup)</span>
          <p className="font-medium text-gray-600">
            {result.aggregate.records_skipped_dup}
          </p>
        </div>
        <div>
          <span className="text-gray-500">Failed</span>
          <p className="font-medium text-red-600">{result.aggregate.records_failed}</p>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200 text-sm">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                File
              </th>
              <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                Status
              </th>
              <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                Total
              </th>
              <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                Imported
              </th>
              <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                Skipped
              </th>
              <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                Failed
              </th>
              <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                Error
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {result.files.map((fileResult) => (
              <tr key={`${fileResult.filename}-${fileResult.import_log_id ?? "none"}`}>
                <td className="px-3 py-2">{fileResult.filename}</td>
                <td className="px-3 py-2">
                  <StatusBadge status={fileResult.status} />
                </td>
                <td className="px-3 py-2">{fileResult.records_total}</td>
                <td className="px-3 py-2">{fileResult.records_imported}</td>
                <td className="px-3 py-2">{fileResult.records_skipped_dup}</td>
                <td className="px-3 py-2">{fileResult.records_failed}</td>
                <td className="px-3 py-2 text-red-600">
                  {fileResult.file_error ?? "-"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ImportHistoryTable({ logs }: { logs: ImportLog[] }) {
  return (
    <table className="min-w-full divide-y divide-gray-200 text-sm">
      <thead className="bg-gray-50">
        <tr>
          <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">
            Date
          </th>
          <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">
            Broker
          </th>
          <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">
            Trade Period
          </th>
          <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">
            Status
          </th>
          <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">
            Imported
          </th>
          <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">
            Skipped
          </th>
          <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">
            Failed
          </th>
        </tr>
      </thead>
      <tbody className="divide-y divide-gray-200">
        {logs.map((log) => (
          <tr key={log.id}>
            <td className="px-3 py-2">{formatDateTime(log.started_at)}</td>
            <td className="px-3 py-2">
              <span className="inline-block px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-700">
                {log.broker || log.source}
              </span>
            </td>
            <td className="px-3 py-2 text-xs text-gray-600">
              {log.trade_date_from && log.trade_date_to ? (
                <>
                  {formatDateTime(log.trade_date_from)}
                  <span className="mx-1">→</span>
                  {formatDateTime(log.trade_date_to)}
                </>
              ) : (
                <span className="text-gray-400">—</span>
              )}
            </td>
            <td className="px-3 py-2">
              <StatusBadge status={log.status} />
            </td>
            <td className="px-3 py-2">{log.records_imported}</td>
            <td className="px-3 py-2">{log.records_skipped_dup}</td>
            <td className="px-3 py-2">{log.records_failed}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default function ImportPage() {
  const queryClient = useQueryClient();
  const [lastResult, setLastResult] = useState<BatchImportResponse | null>(null);

  const csvMutation = useMutation({
    mutationFn: uploadCsv,
    onSuccess: (result) => {
      setLastResult(result);
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

      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-medium mb-4">CSV Upload</h2>
        <CsvUpload
          onUpload={(files) => csvMutation.mutate(files)}
          isLoading={csvMutation.isPending}
        />
        {csvMutation.error && (
          <p className="mt-2 text-sm text-red-500">
            {(csvMutation.error as Error).message}
          </p>
        )}
      </div>

      {lastResult && <LastImportResultCard result={lastResult} />}

      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-medium mb-3">Import History</h2>
        {logsData && logsData.logs.length > 0 ? (
          <ImportHistoryTable logs={logsData.logs} />
        ) : (
          <p className="text-gray-400 text-sm">No imports yet</p>
        )}
      </div>
    </div>
  );
}
