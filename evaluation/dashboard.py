"""
evaluation/dashboard.py

Generates a professional HTML benchmark report from evaluation results.

Output looks like:
┌─────────────────────────────────────────┐
│       OpenSourceFix AI Dashboard        │
│  File Hit@1: 82%   Function Hit: 71%    │
│  Patch Pass: 64%   Avg Runtime: 18s     │
└─────────────────────────────────────────┘

Saves as evaluation/reports/report_<timestamp>.html
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List

from evaluation.evaluator import EvaluationReport

logger = logging.getLogger(__name__)


class BenchmarkDashboard:
    """
    Generates HTML and Markdown benchmark reports.

    Usage:
        report = Evaluator().evaluate(pipeline_results, ground_truth)
        dashboard = BenchmarkDashboard()
        dashboard.generate(report, output_dir="evaluation/reports")
    """

    def generate(
        self,
        report: EvaluationReport,
        output_dir: str = "evaluation/reports",
        run_metadata: dict = None,
    ) -> Path:
        """
        Generate HTML report and save to disk.

        Args:
            report:       EvaluationReport from Evaluator.evaluate().
            output_dir:   Where to save the report.
            run_metadata: Optional dict with model name, timestamp, etc.

        Returns:
            Path to the saved HTML file.
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        html_file = output_path / f"report_{timestamp}.html"
        md_file   = output_path / f"report_{timestamp}.md"

        metrics = report.to_dict()
        html = self._build_html(report, metrics, run_metadata or {})
        md   = self._build_markdown(report, metrics, run_metadata or {})

        html_file.write_text(html, encoding="utf-8")
        md_file.write_text(md, encoding="utf-8")

        logger.info("Dashboard saved: %s", html_file)
        print(f"\n📊 Report saved:\n   HTML: {html_file}\n   MD:   {md_file}")
        return html_file

    # ── private ────────────────────────────────────────────────────────────

    def _pct(self, value) -> str:
        if value is None: return "N/A"
        return f"{100*value:.1f}%"

    def _build_markdown(self, report: EvaluationReport, metrics: dict, meta: dict) -> str:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        model = meta.get("model", "unknown")

        lines = [
            "# OpenSourceFix AI — Benchmark Report",
            "",
            f"**Generated:** {timestamp}  ",
            f"**Model:** {model}  ",
            f"**Issues evaluated:** {report.total}",
            "",
            "## Results",
            "",
            f"| Metric | Score |",
            f"|--------|-------|",
            f"| File Hit@1 | {self._pct(metrics.get('file_hit_at_1'))} |",
            f"| File Hit@5 | {self._pct(metrics.get('file_hit_at_5'))} |",
            f"| Function Hit Rate | {self._pct(metrics.get('function_hit_rate'))} |",
            f"| Patch Pass Rate | {self._pct(metrics.get('patch_pass_rate'))} |",
            "",
            "## Per-Issue Results",
            "",
            "| Issue | Correct File | Hit@1 | Hit@5 | Function |",
            "|-------|-------------|-------|-------|----------|",
        ]
        for r in report.results:
            lines.append(
                f"| #{r.issue_number} | `{r.correct_file}` "
                f"| {'✅' if r.hit_at_1 else '❌'} "
                f"| {'✅' if r.hit_at_5 else '❌'} "
                f"| {'✅' if r.function_correct else '❌'} |"
            )
        return "\n".join(lines)

    def _build_html(self, report: EvaluationReport, metrics: dict, meta: dict) -> str:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        model = meta.get("model", "unknown")

        def pct_color(val):
            if val is None: return "#6b7280"
            if val >= 0.7: return "#16a34a"
            if val >= 0.4: return "#d97706"
            return "#dc2626"

        metric_cards = ""
        for label, key in [
            ("File Hit@1", "file_hit_at_1"),
            ("File Hit@5", "file_hit_at_5"),
            ("Function Hit", "function_hit_rate"),
            ("Patch Pass", "patch_pass_rate"),
        ]:
            val = metrics.get(key)
            color = pct_color(val)
            metric_cards += f"""
            <div class="card">
                <div class="metric" style="color:{color}">{self._pct(val)}</div>
                <div class="label">{label}</div>
            </div>"""

        rows = ""
        for r in report.results:
            h1 = "✅" if r.hit_at_1 else "❌"
            h5 = "✅" if r.hit_at_5 else "❌"
            fn = "✅" if r.function_correct else "❌"
            rows += f"""
            <tr>
                <td>#{r.issue_number}</td>
                <td><code>{r.correct_file}</code></td>
                <td>{h1}</td>
                <td>{h5}</td>
                <td>{fn}</td>
            </tr>"""

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>OpenSourceFix AI — Benchmark Report</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
          background: #f8fafc; color: #1e293b; padding: 40px; }}
  h1 {{ font-size: 1.8rem; font-weight: 700; margin-bottom: 8px; }}
  .meta {{ color: #64748b; font-size: 0.9rem; margin-bottom: 32px; }}
  .cards {{ display: flex; gap: 20px; margin-bottom: 40px; flex-wrap: wrap; }}
  .card {{ background: white; border-radius: 12px; padding: 24px 32px;
           box-shadow: 0 1px 3px rgba(0,0,0,.1); min-width: 160px; text-align: center; }}
  .metric {{ font-size: 2.5rem; font-weight: 800; }}
  .label  {{ color: #64748b; font-size: 0.85rem; margin-top: 4px; text-transform: uppercase; letter-spacing: .05em; }}
  h2 {{ font-size: 1.2rem; margin-bottom: 16px; }}
  table {{ width: 100%; border-collapse: collapse; background: white;
           border-radius: 12px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,.1); }}
  th {{ background: #1e293b; color: white; padding: 12px 16px; text-align: left; font-size: 0.85rem; }}
  td {{ padding: 12px 16px; border-bottom: 1px solid #f1f5f9; font-size: 0.9rem; }}
  tr:last-child td {{ border-bottom: none; }}
  code {{ background: #f1f5f9; padding: 2px 6px; border-radius: 4px; font-size: 0.8rem; }}
  .footer {{ margin-top: 40px; color: #94a3b8; font-size: 0.8rem; text-align: center; }}
</style>
</head>
<body>
<h1>OpenSourceFix AI — Benchmark Report</h1>
<div class="meta">Generated: {timestamp} &nbsp;·&nbsp; Model: {model} &nbsp;·&nbsp; Issues: {report.total}</div>

<div class="cards">{metric_cards}
</div>

<h2>Per-Issue Results</h2>
<table>
  <thead>
    <tr><th>Issue</th><th>Correct File</th><th>Hit@1</th><th>Hit@5</th><th>Function</th></tr>
  </thead>
  <tbody>{rows}
  </tbody>
</table>

<div class="footer">Generated by OpenSourceFix AI · {timestamp}</div>
</body>
</html>"""
