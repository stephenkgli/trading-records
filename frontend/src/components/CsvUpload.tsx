import { useCallback, useState } from "react";

interface CsvUploadProps {
  onUpload: (file: File) => void;
  isLoading: boolean;
}

export default function CsvUpload({ onUpload, isLoading }: CsvUploadProps) {
  const [dragActive, setDragActive] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0];
      setSelectedFile(file);
    }
  }, []);

  const handleChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
    }
  }, []);

  const handleSubmit = useCallback(() => {
    if (selectedFile) {
      onUpload(selectedFile);
    }
  }, [selectedFile, onUpload]);

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
          accept=".csv,.xlsx"
          onChange={handleChange}
          className="hidden"
          id="csv-upload"
          disabled={isLoading}
        />
        <label htmlFor="csv-upload" className="cursor-pointer">
          <p className="text-gray-600">
            {selectedFile
              ? selectedFile.name
              : "Drag and drop a CSV file here, or click to browse"}
          </p>
          <p className="text-xs text-gray-400 mt-1">
            Supports IBKR Activity Statement CSV and Tradovate CSV exports
          </p>
        </label>
      </div>

      {selectedFile && (
        <button
          onClick={handleSubmit}
          disabled={isLoading}
          className="w-full bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {isLoading ? "Importing..." : `Import ${selectedFile.name}`}
        </button>
      )}
    </div>
  );
}
