/**
 * Import-related API types.
 */

export interface ImportResult {
  import_log_id: string;
  source: string;
  status: string;
  records_total: number;
  records_imported: number;
  records_skipped_dup: number;
  records_failed: number;
  errors: Array<Record<string, unknown>>;
}

export interface FileImportResult {
  filename: string;
  status: string;
  import_log_id: string | null;
  source: string;
  records_total: number;
  records_imported: number;
  records_skipped_dup: number;
  records_failed: number;
  errors: Array<Record<string, unknown>>;
  file_error: string | null;
}

export interface BatchImportAggregate {
  status: string;
  files_total: number;
  files_success: number;
  files_partial: number;
  files_failed: number;
  records_total: number;
  records_imported: number;
  records_skipped_dup: number;
  records_failed: number;
}

export interface BatchImportResponse {
  aggregate: BatchImportAggregate;
  files: FileImportResult[];
}

export interface ImportLog {
  id: string;
  source: string;
  status: string;
  records_total: number;
  records_imported: number;
  records_skipped_dup: number;
  records_failed: number;
  errors: Record<string, unknown> | null;
  started_at: string;
  completed_at: string | null;
  trade_date_from: string | null;
  trade_date_to: string | null;
  broker: string | null;
}

export interface ImportLogListResponse {
  logs: ImportLog[];
  total: number;
  page: number;
  per_page: number;
}
