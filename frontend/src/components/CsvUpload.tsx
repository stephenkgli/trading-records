import { useCallback, useState } from "react";

interface CsvUploadProps {
  onUpload: (files: File[]) => void;
  isLoading: boolean;
}

export default function CsvUpload({ onUpload, isLoading }: CsvUploadProps) {
  const [dragActive, setDragActive] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);

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
        className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
          dragActive
            ? "border-blue-400 bg-blue-50"
            : "border-gray-300 hover:border-gray-400"
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
          <p className="text-gray-600">
            {selectedFiles.length > 0
              ? `Selected ${selectedFiles.length} file(s)`
              : "Drag and drop CSV files here, or click to browse\u2026"}
          </p>
          <p className="text-xs text-gray-400 mt-1">
            Supports IBKR Activity Statement CSV, Tradovate CSV exports, and
            Tradovate Performance reports
          </p>
        </label>
      </div>

      {selectedFiles.length > 0 && (
        <button
          onClick={handleSubmit}
          disabled={isLoading}
          className="w-full bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-[color,background-color,border-color,opacity]"
        >
          {isLoading ? "Importing\u2026" : `Import ${selectedFiles.length} file(s)`}
        </button>
      )}
    </div>
  );
}
