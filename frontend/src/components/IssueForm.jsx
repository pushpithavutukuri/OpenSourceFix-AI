import { useState } from "react";

// Parse a GitHub issue URL like https://github.com/owner/repo/issues/123
function parseIssueUrl(url) {
  const match = url.match(/github\.com\/([^\/]+)\/([^\/]+)\/issues\/(\d+)/);
  if (!match) return null;
  return { owner: match[1], repo_name: match[2], issue_number: parseInt(match[3]) };
}

export default function IssueForm({ onSubmit, disabled }) {
  const [url, setUrl] = useState("");
  const [applyPatch, setApplyPatch] = useState(false);
  const [parseError, setParseError] = useState("");

  function handleSubmit(e) {
    e.preventDefault();
    setParseError("");

    const parsed = parseIssueUrl(url.trim());
    if (!parsed) {
      setParseError("Could not parse URL. Expected: https://github.com/owner/repo/issues/123");
      return;
    }

    onSubmit({
      repo_url: `https://github.com/${parsed.owner}/${parsed.repo_name}`,
      owner: parsed.owner,
      repo_name: parsed.repo_name,
      issue_number: parsed.issue_number,
      apply_patch: applyPatch,
    });
  }

  return (
    <form onSubmit={handleSubmit} className="bg-gray-900 border border-gray-800 rounded-xl p-6 space-y-4">
      <div>
        <label className="block text-xs text-gray-400 mb-2">GitHub Issue URL</label>
        <input
          type="url"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://github.com/pallets/flask/issues/4556"
          disabled={disabled}
          className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:border-blue-500 disabled:opacity-50"
          required
        />
        {parseError && <p className="mt-1 text-xs text-red-400">{parseError}</p>}
      </div>

      <div className="flex items-center gap-3">
        <input
          type="checkbox"
          id="apply"
          checked={applyPatch}
          onChange={(e) => setApplyPatch(e.target.checked)}
          disabled={disabled}
          className="w-4 h-4 accent-blue-500"
        />
        <label htmlFor="apply" className="text-xs text-gray-400">
          Apply patch to disk (default: dry-run only)
        </label>
      </div>

      <button
        type="submit"
        disabled={disabled || !url}
        className="w-full bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed text-white font-semibold rounded-lg py-3 text-sm transition-colors"
      >
        {disabled ? "Running..." : "Analyze & Fix"}
      </button>
    </form>
  );
}
