// Shows the live step-by-step progress of the pipeline.

const STEP_LABELS = {
  repository_analysis: "Repository Analysis",
  issue_analysis:      "Issue Analysis",
  semantic_retrieval:  "Semantic Retrieval",
  bug_localization:    "Bug Localization",
  patch_generation:    "Patch Generation",
  validation:          "Test Validation",
  pr_generation:       "PR Generation",
};

function StepRow({ step }) {
  const icons = {
    pending: <span className="text-gray-600">○</span>,
    running: <span className="text-blue-400 animate-pulse">◉</span>,
    done:    <span className="text-green-400">✓</span>,
    failed:  <span className="text-red-400">✗</span>,
  };

  const colors = {
    pending: "text-gray-600",
    running: "text-blue-300",
    done:    "text-gray-200",
    failed:  "text-red-400",
  };

  return (
    <div className="flex items-start gap-3 py-2">
      <span className="mt-0.5 w-4 text-center flex-shrink-0">{icons[step.status]}</span>
      <div className="flex-1 min-w-0">
        <span className={`text-sm font-medium ${colors[step.status]}`}>
          {STEP_LABELS[step.name] || step.name}
        </span>
        {step.detail && (
          <p className="text-xs text-gray-500 truncate mt-0.5">{step.detail}</p>
        )}
      </div>
    </div>
  );
}

export default function PipelineProgress({ status }) {
  const overallColor = {
    pending: "text-gray-400",
    running: "text-blue-400",
    done:    "text-green-400",
    failed:  "text-red-400",
  }[status.overall] || "text-gray-400";

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-semibold text-gray-300">Pipeline</h2>
        <span className={`text-xs font-medium ${overallColor}`}>
          {status.overall.toUpperCase()}
        </span>
      </div>

      <div className="divide-y divide-gray-800">
        {status.steps.map((step) => (
          <StepRow key={step.name} step={step} />
        ))}
      </div>
    </div>
  );
}
