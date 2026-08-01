import { useState } from "react";

// Tabs: Patch | PR Description | Details
export default function ResultPanel({ result }) {
  const [tab, setTab] = useState("patch");

  const tabs = [
    { id: "patch", label: "Patch" },
    { id: "pr", label: "PR Description" },
    { id: "details", label: "Details" },
  ];

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
      {/* Tab bar */}
      <div className="flex border-b border-gray-800">
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`px-5 py-3 text-xs font-semibold transition-colors ${
              tab === t.id
                ? "text-blue-400 border-b-2 border-blue-500"
                : "text-gray-500 hover:text-gray-300"
            }`}
          >
            {t.label}
          </button>
        ))}
        <div className="ml-auto flex items-center px-4">
          <ValidationBadge status={result.validation?.status} />
        </div>
      </div>

      <div className="p-6">
        {tab === "patch" && <PatchTab result={result} />}
        {tab === "pr"    && <PRTab result={result} />}
        {tab === "details" && <DetailsTab result={result} />}
      </div>
    </div>
  );
}

function ValidationBadge({ status }) {
  const colors = {
    PASS: "bg-green-900 text-green-400 border-green-800",
    FAIL: "bg-red-900 text-red-400 border-red-800",
    SKIP: "bg-gray-800 text-gray-400 border-gray-700",
  };
  return (
    <span className={`text-xs px-2 py-1 rounded border font-medium ${colors[status] || colors.SKIP}`}>
      {status || "SKIP"}
    </span>
  );
}

function PatchTab({ result }) {
  const patch = result.patch;
  const fn = result.function_location;

  if (!patch?.diff) {
    return <p className="text-sm text-gray-500">No patch was generated.</p>;
  }

  return (
    <div className="space-y-4">
      {fn && (
        <div className="bg-gray-800 rounded-lg px-4 py-3 text-xs space-y-1">
          <div className="text-gray-400">
            Bug located in <span className="text-blue-300 font-semibold">{fn.file}</span>
            {" → "}
            <span className="text-yellow-300 font-semibold">{fn.function}()</span>
            <span className="ml-2 text-gray-500">[{fn.confidence}]</span>
          </div>
          {fn.reason && <div className="text-gray-500">{fn.reason}</div>}
        </div>
      )}

      {patch.explanation && (
        <p className="text-sm text-gray-400">{patch.explanation}</p>
      )}

      <pre className="bg-gray-950 rounded-lg p-4 overflow-x-auto text-xs leading-relaxed">
        <DiffHighlight diff={patch.diff} />
      </pre>

      <div className="flex gap-4 text-xs text-gray-500">
        <span>Valid: <span className={patch.valid ? "text-green-400" : "text-red-400"}>{String(patch.valid)}</span></span>
        <span>Attempts: {patch.attempts}</span>
      </div>
    </div>
  );
}

// Color the +/- lines in the diff
function DiffHighlight({ diff }) {
  return (
    <>
      {diff.split("\n").map((line, i) => {
        let color = "text-gray-400";
        if (line.startsWith("+") && !line.startsWith("+++")) color = "text-green-400";
        if (line.startsWith("-") && !line.startsWith("---")) color = "text-red-400";
        if (line.startsWith("@@")) color = "text-blue-400";
        if (line.startsWith("---") || line.startsWith("+++")) color = "text-gray-300";
        return <div key={i} className={color}>{line || " "}</div>;
      })}
    </>
  );
}

function PRTab({ result }) {
  const [copied, setCopied] = useState(false);

  function copy() {
    navigator.clipboard.writeText(result.pr_markdown || "");
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <div className="space-y-3">
      <div className="flex justify-end">
        <button
          onClick={copy}
          className="text-xs text-gray-500 hover:text-gray-300 transition-colors"
        >
          {copied ? "Copied!" : "Copy markdown"}
        </button>
      </div>
      <pre className="bg-gray-950 rounded-lg p-4 overflow-x-auto text-xs text-gray-300 leading-relaxed whitespace-pre-wrap">
        {result.pr_markdown || "No PR description generated."}
      </pre>
    </div>
  );
}

function DetailsTab({ result }) {
  return (
    <div className="space-y-4 text-sm">
      <div>
        <p className="text-xs text-gray-500 mb-2">Issue</p>
        <p className="text-gray-300">{result.issue_title}</p>
      </div>

      <div>
        <p className="text-xs text-gray-500 mb-2">Top ranked files</p>
        <ul className="space-y-1">
          {(result.suspect_files || []).map((f) => (
            <li key={f} className="text-xs text-blue-300 font-mono">{f}</li>
          ))}
        </ul>
      </div>

      <div>
        <p className="text-xs text-gray-500 mb-2">Validation</p>
        <p className="text-xs text-gray-400">
          Status: {result.validation?.status} — {result.validation?.message}
        </p>
      </div>
    </div>
  );
}
