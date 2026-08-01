import { useState } from "react";
import IssueForm from "./components/IssueForm";
import PipelineProgress from "./components/PipelineProgress";
import ResultPanel from "./components/ResultPanel";
import axios from "axios";

export default function App() {
  const [runId, setRunId] = useState(null);
  const [status, setStatus] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [polling, setPolling] = useState(false);

  async function handleSubmit(formData) {
    setError("");
    setResult(null);
    setStatus(null);

    try {
      const res = await axios.post("/api/run", formData);
      const id = res.data.run_id;
      setRunId(id);
      startPolling(id);
    } catch (e) {
      setError(e.response?.data?.detail || "Failed to start run.");
    }
  }

  function startPolling(id) {
    setPolling(true);
    const interval = setInterval(async () => {
      try {
        const res = await axios.get(`/api/run/${id}`);
        setStatus(res.data);

        if (res.data.overall === "done") {
          clearInterval(interval);
          setPolling(false);
          const r = await axios.get(`/api/run/${id}/result`);
          setResult(r.data);
        } else if (res.data.overall === "failed") {
          clearInterval(interval);
          setPolling(false);
          setError(res.data.error || "Pipeline failed.");
        }
      } catch (e) {
        clearInterval(interval);
        setPolling(false);
        setError("Lost connection to server.");
      }
    }, 1500);
  }

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 font-mono">
      {/* Header */}
      <header className="border-b border-gray-800 px-8 py-5">
        <div className="max-w-5xl mx-auto flex items-center gap-3">
          <span className="text-2xl">🔧</span>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">OpenSourceFix AI</h1>
            <p className="text-xs text-gray-500">Paste a GitHub issue. Get a patch.</p>
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-8 py-10 space-y-8">
        <IssueForm onSubmit={handleSubmit} disabled={polling} />

        {error && (
          <div className="bg-red-950 border border-red-800 text-red-300 rounded-lg px-4 py-3 text-sm">
            {error}
          </div>
        )}

        {status && <PipelineProgress status={status} />}

        {result && <ResultPanel result={result} />}
      </main>
    </div>
  );
}
