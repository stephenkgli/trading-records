import { useCallback, useState, useRef, useEffect } from "react";

interface CsvUploadProps {
  onUpload: (files: File[]) => void;
  isLoading: boolean;
  /** Incremented on each successful upload to trigger file list clearing. */
  successCount?: number;
}

export default function CsvUpload({ onUpload, isLoading, successCount = 0 }: CsvUploadProps) {
  const [dragActive, setDragActive] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const prevSuccessCount = useRef(successCount);

  // Clear selected files when successCount increments
  useEffect(() => {
    if (successCount > prevSuccessCount.current) {
      setSelectedFiles([]);
    }
    prevSuccessCount.current = successCount;
  }, [successCount]);

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  }, []);

  const updateSelectedFiles = useCallback((fileList: FileList | null) => {
    const files = Array.from(fileList ?? []);
    if (files.length > 0) {
      setSelectedFiles(files);
    }
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    updateSelectedFiles(e.dataTransfer.files);
  }, [updateSelectedFiles]);

  const handleChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    updateSelectedFiles(e.target.files);
  }, [updateSelectedFiles]);

  const handleSubmit = useCallback(() => {
    if (selectedFiles.length > 0) {
      onUpload(selectedFiles);
    }
  }, [selectedFiles, onUpload]);

  return (
    <div className="space-y-4">
      <div
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        className={`relative border-2 border-dashed rounded-lg p-8 text-center transition-all duration-200 ${
          dragActive
            ? "border-accent bg-accent-subtle scale-[1.01]"
            : "border-[--color-border-strong] hover:border-accent/40 hover:bg-[rgba(99,102,241,0.04)]"
        }`}
      >
        <input
          type="file"
          name="csv-files"
          accept=".csv,.xlsx"
          onChange={handleChange}
          className="hidden"
          id="csv-upload"
          disabled={isLoading}
          multiple
        />
        <label htmlFor="csv-upload" className="cursor-pointer">
          <div className={`w-12 h-12 mx-auto mb-3 rounded-full flex items-center justify-center transition-colors duration-200 ${
            dragActive ? "bg-accent/20" : "bg-accent-subtle"
          }`}>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--color-accent)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
              <polyline points="17 8 12 3 7 8" />
              <line x1="12" y1="3" x2="12" y2="15" />
            </svg>
          </div>
          <p className="text-[--color-text-primary] text-sm">
            {selectedFiles.length > 0
              ? `Selected ${selectedFiles.length} file(s)`
              : "Drag and drop CSV files here, or click to browse\u2026"}
          </p>
          <p className="text-xs text-[--color-text-muted] mt-1">
            Supports IBKR Activity Statement CSV, Tradovate CSV exports, and
            Tradovate Performance reports
          </p>
        </label>
      </div>

      {selectedFiles.length > 0 && (
        <div className="space-y-3">
          <div className="flex flex-wrap gap-2">
            {selectedFiles.map((f, i) => (
              <span key={i} className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-elevated border border-[--color-border] text-xs text-[--color-text-secondary]">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="opacity-50"><path d="M13 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V9z" /><polyline points="13 2 13 9 20 9" /></svg>
                {f.name}
              </span>
            ))}
          </div>
          <button
            onClick={handleSubmit}
            disabled={isLoading}
            className="w-full bg-accent text-white py-2.5 px-4 rounded-lg font-medium hover:bg-accent-hover disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-[--color-bg-surface] focus-visible:outline-none"
          >
            {isLoading ? "Importing\u2026" : `Import ${selectedFiles.length} file(s)`}
          </button>
        </div>
      )}
    </div>
  );
}
