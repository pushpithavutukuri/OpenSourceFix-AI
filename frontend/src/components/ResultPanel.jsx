import { useState } from "react";

function CopyButton({ text, label = "Copy" }) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      // Clipboard API unavailable in some browsers/contexts
    }
  }

  return (
    <button
      onClick={handleCopy}
      className="text-xs text-gray-500 hover:text-gray-300 transition-colors px-2 py-1 rounded hover:bg-gray-800"
    >
      {copied ? "✓ Copied" : label}
    </button>
  );
}

function ValidationBadge({ status }) {
  const styles = {
    PASS: "bg-green-950 text-green-400 border-green-800",
    FAIL: "bg-red-950 text-red-400 border-red-800",
    SKIP: "bg-gray-800 text-gray-500 border-gray-700",
  };
  return (
    <span className={`text-xs px-2 py-0.5 rounded border font-medium ${styles[status] || styles.SKIP}`}>
      {status || "SKIP"}
    </span>
  );
}

function DiffView({ diff }) {
  return (
    <code className="block">
      {diff.split("\n").map((line, i) => {
        let cls = "text-gray-400";
        if (line.startsWith("+") && !line.startsWith("+++")) cls = "text-green-400";
        if (line.startsWith("-") && !line.startsWith("---")) cls = "text-red-400";
        if (line.startsWith("@@"))  cls = "text-blue-400";
        if (line.startsWith("---") || line.startsWith("+++")) cls = "text-gray-300";
        return (
          <div key={i} className={`${cls} leading-5`}>
            {line || "\u00a0"}
          </div>
        );
      })}
    </code>
  );
}

function ConfidenceBadge({ confidence }) {
  const styles = {
    high:   "bg-green-950 text-green-400",
    medium: "bg-yellow-950 text-yellow-400",
    low:    "bg-gray-800 text-gray-400",
  };
  return (
    <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${styles[confidence] || styles.low}`}>
      {confidence}
    </span>
  );
}

// ── Tabs ──────────────────────────────────────────────────────────────────────

function PatchTab({ result }) {
  const { patch, function_location: fn } = result;

  if (!patch?.diff) {
    return (
      <div className="py-4 space-y-2">
        <p className="text-sm text-gray-500">No patch was generated.</p>
        {!fn && (
          <p className="text-xs text-gray-600">
            The pipeline could not identify a specific function responsible for the bug.
          </p>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {fn && (
        <div className="bg-gray-800/50 rounded-lg px-4 py-3 text-xs space-y-1.5">
          <div className="flex flex-wrap items-center gap-1.5 text-gray-400">
            <span>Bug in</span>
            <span className="text-blue-300 font-semibold font-mono">{fn.file}</span>
            <span>→</span>
            <span className="text-yellow-300 font-semibold font-mono">{fn.function}()</span>
            <span className="text-gray-600">lines {fn.start_line}–{fn.end_line}</span>
            <ConfidenceBadge confidence={fn.confidence} />
          </div>
          {fn.reason && (
            <p className="text-gray-500">{fn.reason}</p>
          )}
        </div>
      )}

      {patch.explanation && (
        <p className="text-sm text-gray-400 leading-relaxed">{patch.explanation}</p>
      )}

      <div className="relative">
        <div className="absolute top-3 right-3 z-10">
          <CopyButton text={patch.diff} label="Copy diff" />
        </div>
        <pre className="bg-gray-950 border border-gray-800/60 rounded-lg p-4 pr-24 overflow-x-auto text-xs leading-relaxed">
          <DiffView diff={patch.diff} />
        </pre>
      </div>

      <div className="flex gap-4 text-xs text-gray-600">
        <span>
          Valid:{" "}
          <span className={patch.valid ? "text-green-400" : "text-red-400"}>
            {patch.valid ? "yes" : "no"}
          </span>
        </span>
        <span>Attempts: {patch.attempts}</span>
      </div>
    </div>
  );
}

function PRTab({ result }) {
  const md = result.pr_markdown || "";

  if (!md) {
    return (
      <p className="text-sm text-gray-500 py-4">
        No PR description generated.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex justify-end">
        <CopyButton text={md} label="Copy markdown" />
      </div>
      <pre className="bg-gray-950 border border-gray-800/60 rounded-lg p-4 overflow-x-auto text-xs text-gray-300 leading-relaxed whitespace-pre-wrap">
        {md}
      </pre>
    </div>
  );
}

function DetailsTab({ result }) {
  const files = result.suspect_files || [];
  const val   = result.validation || {};

  return (
    <div className="space-y-5">
      {result.issue_title && (
        <div>
          <p className="text-xs text-gray-500 mb-1">Issue</p>
          <p className="text-sm text-gray-300">{result.issue_title}</p>
          {result.issue_body && (
            // Tailwind 3.3+ has line-clamp built-in
            <p className="text-xs text-gray-600 mt-1.5 line-clamp-3 leading-relaxed">
              {result.issue_body}
            </p>
          )}
        </div>
      )}

      {files.length > 0 && (
        <div>
          <p className="text-xs text-gray-500 mb-2">Ranked files</p>
          <ul className="space-y-1.5">
            {files.map((f) => (
              <li key={f.path} className="flex items-center justify-between gap-4">
                <span className="text-xs text-blue-300 font-mono truncate">{f.path}</span>
                <span className="text-xs text-gray-600 flex-shrink-0 tabular-nums">
                  {f.score}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div>
        <p className="text-xs text-gray-500 mb-1.5">Validation</p>
        <div className="flex items-center gap-2">
          <ValidationBadge status={val.status} />
          {val.message && (
            <span className="text-xs text-gray-500">{val.message}</span>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────────────────

const TABS = [
  { id: "patch",   label: "Patch" },
  { id: "pr",      label: "PR Description" },
  { id: "details", label: "Details" },
];

export default function ResultPanel({ result }) {
  // Start on patch tab if there's a diff, otherwise details
  const [tab, setTab] = useState(result.patch?.diff ? "patch" : "details");

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
      <div className="flex items-center border-b border-gray-800">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`px-4 sm:px-5 py-3 text-xs font-semibold transition-colors whitespace-nowrap ${
              tab === t.id
                ? "text-blue-400 border-b-2 border-blue-500"
                : "text-gray-500 hover:text-gray-300"
            }`}
          >
            {t.label}
          </button>
        ))}
        <div className="ml-auto px-4 flex-shrink-0">
          <ValidationBadge status={result.validation?.status} />
        </div>
      </div>

      <div className="p-5 sm:p-6">
        {tab === "patch"   && <PatchTab result={result} />}
        {tab === "pr"      && <PRTab result={result} />}
        {tab === "details" && <DetailsTab result={result} />}
      </div>
    </div>
  );
}
