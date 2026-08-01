import { useState, useRef } from "react";
import IssueForm from "./components/IssueForm";
import PipelineProgress from "./components/PipelineProgress";
import ResultPanel from "./components/ResultPanel";
import axios from "axios";

export default function App() {
  const [status, setStatus]   = useState(null);
  const [result, setResult]   = useState(null);
  const [error, setError]     = useState("");
  const [running, setRunning] = useState(false);
  const intervalRef = useRef(null);

  function stopPolling() {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }

  function reset() {
    stopPolling();
    setStatus(null);
    setResult(null);
    setError("");
    setRunning(false);
  }

  async function handleSubmit(formData) {
    reset();
    setRunning(true);

    let runId;
    try {
      const res = await axios.post("/api/run", formData);
      runId = res.data.run_id;
    } catch (e) {
      setError(e.response?.data?.detail || "Could not connect to the server.");
      setRunning(false);
      return;
    }

    intervalRef.current = setInterval(async () => {
      try {
        const res = await axios.get(`/api/run/${runId}`);
        setStatus(res.data);

        if (res.data.overall === "done") {
          stopPolling();
          setRunning(false);
          const r = await axios.get(`/api/run/${runId}/result`);
          // Server returns {pending: true} if not done yet — shouldn't happen here but guard anyway
          if (!r.data.pending) {
            setResult(r.data);
          }
        } else if (res.data.overall === "failed") {
          stopPolling();
          setRunning(false);
          setError(res.data.error || "Pipeline failed.");
        }
      } catch (e) {
        stopPolling();
        setRunning(false);
        setError("Lost connection to the server.");
      }
    }, 1500);
  }

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 font-mono">
      <header className="border-b border-gray-800 px-4 sm:px-8 py-4">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-xl">🔧</span>
            <div>
              <h1 className="text-base sm:text-lg font-semibold tracking-tight">
                OpenSourceFix AI
              </h1>
              <p className="text-xs text-gray-500 hidden sm:block">
                Paste a GitHub issue URL. Get a patch.
              </p>
            </div>
          </div>
          {/* Show a reset button once a run finishes */}
          {!running && (status || result) && (
            <button
              onClick={reset}
              className="text-xs text-gray-500 hover:text-gray-300 transition-colors px-3 py-1.5 rounded border border-gray-800 hover:border-gray-700"
            >
              New run
            </button>
          )}
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 sm:px-8 py-8 space-y-6">
        {/* Hide the form while running or after a result comes in */}
        {!running && !result && !status && (
          <IssueForm onSubmit={handleSubmit} disabled={false} />
        )}
        {running && !status && (
          <IssueForm onSubmit={handleSubmit} disabled={true} />
        )}

        {error && (
          <div className="bg-red-950 border border-red-800 text-red-300 rounded-lg px-4 py-3 text-sm flex items-start gap-2">
            <span className="flex-shrink-0 mt-0.5">✗</span>
            <span>{error}</span>
          </div>
        )}

        {status && <PipelineProgress status={status} />}
        {result  && <ResultPanel result={result} />}
      </main>
    </div>
  );
}
