import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import CsvUpload from "../components/CsvUpload";
import {
  uploadCsv,
  fetchImportLogs,
  type BatchImportResponse,
  type ImportLog,
} from "../api/client";

function getStatusBadgeClass(status: string): string {
  if (status === "success") return "bg-profit-subtle text-profit";
  if (status === "failed") return "bg-loss-subtle text-loss";
  return "bg-[--color-warning-subtle] text-[--color-warning]";
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
      className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${getStatusBadgeClass(status)}`}
    >
      {status}
    </span>
  );
}

function LastImportResultCard({ result }: { result: BatchImportResponse }) {
  return (
    <div className="bg-surface rounded-lg border border-[--color-border] p-6 space-y-4">
      <h2 className="text-[10px] font-medium text-[--color-text-muted] uppercase tracking-widest">Last Import Result</h2>

      <div className="grid grid-cols-2 sm:grid-cols-5 gap-4 text-sm">
        <div>
          <span className="text-[--color-text-muted] text-[10px] uppercase tracking-widest block mb-1">Status</span>
          <StatusBadge status={result.aggregate.status} />
        </div>
        <div>
          <span className="text-[--color-text-muted] text-[10px] uppercase tracking-widest block mb-1">Files</span>
          <p className="font-medium font-mono text-[--color-text-primary]">{result.aggregate.files_total}</p>
        </div>
        <div>
          <span className="text-[--color-text-muted] text-[10px] uppercase tracking-widest block mb-1">Imported</span>
          <p className="font-medium font-mono text-profit">{result.aggregate.records_imported}</p>
        </div>
        <div>
          <span className="text-[--color-text-muted] text-[10px] uppercase tracking-widest block mb-1">Skipped</span>
          <p className="font-medium font-mono text-[--color-text-secondary]">{result.aggregate.records_skipped_dup}</p>
        </div>
        <div>
          <span className="text-[--color-text-muted] text-[10px] uppercase tracking-widest block mb-1">Failed</span>
          <p className="font-medium font-mono text-loss">{result.aggregate.records_failed}</p>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead>
            <tr className="border-b border-[--color-border]">
              <th className="px-3 py-2 text-left text-[10px] font-medium text-[--color-text-muted] uppercase tracking-widest">File</th>
              <th className="px-3 py-2 text-left text-[10px] font-medium text-[--color-text-muted] uppercase tracking-widest">Status</th>
              <th className="px-3 py-2 text-left text-[10px] font-medium text-[--color-text-muted] uppercase tracking-widest">Total</th>
              <th className="px-3 py-2 text-left text-[10px] font-medium text-[--color-text-muted] uppercase tracking-widest">Imported</th>
              <th className="px-3 py-2 text-left text-[10px] font-medium text-[--color-text-muted] uppercase tracking-widest">Skipped</th>
              <th className="px-3 py-2 text-left text-[10px] font-medium text-[--color-text-muted] uppercase tracking-widest">Failed</th>
              <th className="px-3 py-2 text-left text-[10px] font-medium text-[--color-text-muted] uppercase tracking-widest">Error</th>
            </tr>
          </thead>
          <tbody>
            {result.files.map((fileResult) => (
              <tr
                key={`${fileResult.filename}-${fileResult.import_log_id ?? "none"}`}
                className="border-b border-[--color-border]"
              >
                <td className="px-3 py-2 text-[--color-text-primary]">{fileResult.filename}</td>
                <td className="px-3 py-2"><StatusBadge status={fileResult.status} /></td>
                <td className="px-3 py-2 font-mono text-[--color-text-secondary]">{fileResult.records_total}</td>
                <td className="px-3 py-2 font-mono text-[--color-text-secondary]">{fileResult.records_imported}</td>
                <td className="px-3 py-2 font-mono text-[--color-text-secondary]">{fileResult.records_skipped_dup}</td>
                <td className="px-3 py-2 font-mono text-[--color-text-secondary]">{fileResult.records_failed}</td>
                <td className="px-3 py-2 text-loss text-xs">
                  {fileResult.file_error ?? <span className="text-[--color-text-muted]">&mdash;</span>}
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
    <div className="overflow-x-auto">
      <table className="min-w-full text-sm">
        <thead>
          <tr className="border-b border-[--color-border]">
            <th className="px-3 py-2 text-left text-[10px] font-medium text-[--color-text-muted] uppercase tracking-widest">Date</th>
            <th className="px-3 py-2 text-left text-[10px] font-medium text-[--color-text-muted] uppercase tracking-widest">Broker</th>
            <th className="px-3 py-2 text-left text-[10px] font-medium text-[--color-text-muted] uppercase tracking-widest">Trade Period</th>
            <th className="px-3 py-2 text-left text-[10px] font-medium text-[--color-text-muted] uppercase tracking-widest">Status</th>
            <th className="px-3 py-2 text-left text-[10px] font-medium text-[--color-text-muted] uppercase tracking-widest">Imported</th>
            <th className="px-3 py-2 text-left text-[10px] font-medium text-[--color-text-muted] uppercase tracking-widest">Skipped</th>
            <th className="px-3 py-2 text-left text-[10px] font-medium text-[--color-text-muted] uppercase tracking-widest">Failed</th>
          </tr>
        </thead>
        <tbody>
          {logs.map((log, i) => (
            <tr key={log.id} className={`border-b border-[--color-border] ${i % 2 === 1 ? "bg-[rgba(255,255,255,0.015)]" : ""}`}>
              <td className="px-3 py-2 text-[--color-text-secondary] text-xs">{formatDateTime(log.started_at)}</td>
              <td className="px-3 py-2">
                <span className="inline-block px-2 py-0.5 rounded-full text-xs font-medium bg-accent-subtle text-accent-hover">
                  {log.broker || log.source}
                </span>
              </td>
              <td className="px-3 py-2 text-xs text-[--color-text-secondary]">
                {log.trade_date_from && log.trade_date_to ? (
                  <span className="font-mono">
                    {formatDateTime(log.trade_date_from)}
                    <span className="mx-1 text-[--color-text-muted]">&rarr;</span>
                    {formatDateTime(log.trade_date_to)}
                  </span>
                ) : (
                  <span className="text-[--color-text-muted]">&mdash;</span>
                )}
              </td>
              <td className="px-3 py-2"><StatusBadge status={log.status} /></td>
              <td className="px-3 py-2 font-mono text-[--color-text-secondary]">{log.records_imported}</td>
              <td className="px-3 py-2 font-mono text-[--color-text-secondary]">{log.records_skipped_dup}</td>
              <td className="px-3 py-2 font-mono text-[--color-text-secondary]">{log.records_failed}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function ImportPage() {
  const queryClient = useQueryClient();
  const [lastResult, setLastResult] = useState<BatchImportResponse | null>(null);

  const csvMutation = useMutation({
    mutationFn: uploadCsv,
    onSuccess: (result) => {
      setLastResult(result);
      queryClient.invalidateQueries({ queryKey: ["importLogs"], exact: true });
    },
  });

  const { data: logsData } = useQuery({
    queryKey: ["importLogs"],
    queryFn: () => fetchImportLogs(),
  });

  return (
    <div className="stagger-in space-y-5">
      <h1 className="font-display text-3xl text-[--color-text-primary] tracking-tight">Import Data</h1>

      <div className="bg-surface rounded-lg border border-[--color-border] p-6">
        <h2 className="text-[10px] font-medium text-[--color-text-muted] mb-4 uppercase tracking-widest">CSV Upload</h2>
        <CsvUpload
          onUpload={(files) => csvMutation.mutate(files)}
          isLoading={csvMutation.isPending}
        />
        {csvMutation.error && (
          <p className="mt-2 text-sm text-loss">
            {(csvMutation.error as Error).message}
          </p>
        )}
      </div>

      {lastResult && <LastImportResultCard result={lastResult} />}

      <div className="bg-surface rounded-lg border border-[--color-border] p-6">
        <h2 className="text-[10px] font-medium text-[--color-text-muted] mb-3 uppercase tracking-widest">Import History</h2>
        {logsData && logsData.logs.length > 0 ? (
          <ImportHistoryTable logs={logsData.logs} />
        ) : (
          <div className="flex flex-col items-center py-8 gap-2">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="var(--color-text-muted)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="opacity-40">
              <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
              <polyline points="17 8 12 3 7 8" />
              <line x1="12" y1="3" x2="12" y2="15" />
            </svg>
            <p className="text-[--color-text-muted] text-sm">No imports yet</p>
          </div>
        )}
      </div>
    </div>
  );
}
