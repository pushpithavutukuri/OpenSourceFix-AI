const STEP_LABELS = {
  repository_analysis: "Repository Analysis",
  issue_analysis:      "Issue Analysis",
  semantic_retrieval:  "Semantic Retrieval",
  bug_localization:    "Bug Localization",
  patch_generation:    "Patch Generation",
  validation:          "Test Validation",
  pr_generation:       "PR Generation",
};

function StepIcon({ status }) {
  if (status === "running") return <span className="text-blue-400 animate-pulse">◉</span>;
  if (status === "done")    return <span className="text-green-400">✓</span>;
  if (status === "failed")  return <span className="text-red-400">✗</span>;
  return <span className="text-gray-700">○</span>;
}

function StepRow({ step }) {
  const labelColor = {
    pending: "text-gray-600",
    running: "text-blue-200",
    done:    "text-gray-200",
    failed:  "text-red-400",
  }[step.status] || "text-gray-400";

  // Only show elapsed once the step is done
  const showElapsed = step.status === "done" && step.elapsed > 0;

  return (
    <div className="flex items-start gap-3 py-2.5">
      <span className="w-4 text-center flex-shrink-0 mt-0.5 text-sm">
        <StepIcon status={step.status} />
      </span>
      <div className="flex-1 min-w-0">
        <div className="flex items-baseline justify-between gap-2">
          <span className={`text-sm font-medium ${labelColor}`}>
            {STEP_LABELS[step.name] || step.name}
          </span>
          {showElapsed && (
            <span className="text-xs text-gray-600 flex-shrink-0 tabular-nums">
              {step.elapsed}s
            </span>
          )}
        </div>
        {step.detail && (
          <p className={`text-xs mt-0.5 truncate ${step.status === "failed" ? "text-red-400" : "text-gray-500"}`}>
            {step.detail}
          </p>
        )}
      </div>
    </div>
  );
}

export default function PipelineProgress({ status }) {
  const overallColor = {
    running: "text-blue-400",
    done:    "text-green-400",
    failed:  "text-red-400",
  }[status.overall] || "text-gray-500";

  const doneCount = status.steps.filter((s) => s.status === "done").length;
  const total = status.steps.length;

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
      <div className="flex items-center justify-between px-5 py-3 border-b border-gray-800">
        <div className="flex items-center gap-3">
          <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
            Pipeline
          </span>
          {status.overall === "running" && (
            <span className="text-xs text-gray-600">
              {doneCount}/{total}
            </span>
          )}
        </div>
        <div className="flex items-center gap-3">
          {status.elapsed > 0 && (
            <span className="text-xs text-gray-600 tabular-nums">{status.elapsed}s</span>
          )}
          <span className={`text-xs font-semibold ${overallColor}`}>
            {status.overall.toUpperCase()}
          </span>
        </div>
      </div>

      {/* Progress bar — only visible while running */}
      {status.overall === "running" && (
        <div className="h-0.5 bg-gray-800">
          <div
            className="h-full bg-blue-500 transition-all duration-700"
            style={{ width: `${(doneCount / total) * 100}%` }}
          />
        </div>
      )}

      <div className="px-5 divide-y divide-gray-800/60">
        {status.steps.map((step) => (
          <StepRow key={step.name} step={step} />
        ))}
      </div>
    </div>
  );
}
