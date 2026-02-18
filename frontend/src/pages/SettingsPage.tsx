import { useState, useEffect } from "react";

export default function SettingsPage() {
  const [apiKey, setApiKey] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    const storedKey = localStorage.getItem("apiKey") || "";
    setApiKey(storedKey);
  }, []);

  const handleSave = () => {
    if (apiKey.trim()) {
      localStorage.setItem("apiKey", apiKey.trim());
    } else {
      localStorage.removeItem("apiKey");
    }
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Settings</h1>

      <div className="bg-white rounded-lg shadow p-6 max-w-lg">
        <h2 className="text-lg font-medium mb-4">API Configuration</h2>

        <div className="space-y-4">
          <div>
            <label
              htmlFor="apiKey"
              className="block text-sm font-medium text-gray-700 mb-1"
            >
              API Key
            </label>
            <input
              id="apiKey"
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="Enter your API key"
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm"
            />
            <p className="text-xs text-gray-400 mt-1">
              Stored in browser localStorage. Required if the server has API_KEY configured.
            </p>
          </div>

          <button
            onClick={handleSave}
            className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 text-sm transition-colors"
          >
            {saved ? "Saved" : "Save Settings"}
          </button>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow p-6 max-w-lg">
        <h2 className="text-lg font-medium mb-4">About</h2>
        <dl className="text-sm space-y-2">
          <div className="flex justify-between">
            <dt className="text-gray-500">Version</dt>
            <dd>0.1.0</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-gray-500">Backend</dt>
            <dd>FastAPI + PostgreSQL</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-gray-500">Frontend</dt>
            <dd>React + TypeScript</dd>
          </div>
        </dl>
      </div>
    </div>
  );
}
