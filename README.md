# OpenSourceFix AI

A pipeline that takes a GitHub issue and tries to fix it — automatically.

It clones the repo, finds the relevant files, localizes the bug to a specific function, generates a unified diff patch, runs the tests, and if they fail, retries with the error as feedback. At the end it produces a pull request description.

---

## Demo

```
$ python main.py --repo https://github.com/pallets/flask --owner pallets --repo-name flask --issue 4556

[1/7] Loading repository...
[2/7] Building repository index...      214 files indexed.
[3/7] Fetching issue #4556...           Session cookie not set when SECRET_KEY changes
[4/7] Building semantic retrieval index... 1,840 chunks indexed.
[5/7] Ranking files and localizing bug...
      [0.923]  src/flask/sessions.py
      [0.711]  src/flask/app.py
[6/7] Function-level localization + patch generation...
      → src/flask/sessions.py::open_session() [high]
[7/7] Generating PR summary...
```

---

## Architecture

```
GitHub Issue URL
        │
        ▼
┌───────────────────┐
│  Issue Analysis   │  fetch → classify → summarize → extract keywords
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│ Repository Index  │  clone → scan → AST parse → dependency graph
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│ Semantic Retrieval│  BGE embeddings → FAISS → ranked file list
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│  Bug Localization │  file-level → function-level (LLM)
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│  Patch Generation │  unified diff → diff validator → patch applier
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│   Repair Agent    │  run tests → analyze failure → retry (up to 5x)
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│   PR Generator    │  PR title + description in GitHub markdown
└───────────────────┘
```

---

## Folder Structure

```
OpenSourceFix-AI/
├── agent/                  # repair loop
│   ├── repair_agent.py
│   └── retry_manager.py
├── api/                    # FastAPI backend for the web UI
│   ├── server.py
│   └── pipeline_runner.py
├── bug_localization/       # file-level and function-level localization
├── evaluation/             # evaluator, benchmark runner, HTML dashboard
├── fix_generation/         # patch generator, applier, diff validator
├── frontend/               # React + Tailwind web UI
├── issue_analysis/         # fetcher, classifier, summarizer, keyword extractor
├── memory/                 # repository cache (skip re-parsing on repeat runs)
├── pr_generator/           # PR description writer
├── repository_analysis/    # clone, scan, AST parse, dependency graph
├── retrieval/              # BGE embeddings, FAISS index, semantic ranker
├── sandbox/                # Docker runner for isolated test execution
├── tests/                  # pytest unit tests
├── utils/                  # config, logging, LLM client adapters
├── validation/             # pytest runner, failure analyzer, feedback loop
├── workflow/               # LangGraph graph + nodes
├── config/config.yaml
├── main.py
└── requirements.txt
```

---

## Features

- **Semantic retrieval** — BGE embeddings + FAISS to find relevant files
- **Function-level localization** — narrows the bug from file to exact function
- **Patch generation** — produces a real unified diff, not prose
- **Iterative repair** — reads test failures and retries with that context
- **Stack trace parsing** — extracts file/line from tracebacks in issue bodies
- **Issue classification** — bug / feature / performance / docs
- **Repository cache** — skips re-parsing repos it has already seen
- **Docker sandbox** — optional isolated test execution
- **Evaluation framework** — measures File Hit@1, Hit@5, Patch Pass Rate
- **Web UI** — paste an issue URL and watch the pipeline run step by step

---

## Tech Stack

| Layer | Tools |
|---|---|
| Embeddings | `BAAI/bge-small-en-v1.5` (sentence-transformers) |
| Vector search | FAISS |
| LLM | Gemini 1.5 Flash (or any OpenAI-compatible endpoint) |
| AST parsing | Python `ast` module |
| Orchestration | LangGraph |
| Backend API | FastAPI |
| Frontend | React + Tailwind CSS |
| Testing | pytest |
| Sandbox | Docker |

---

## Installation

```bash
git clone https://github.com/YOUR_USERNAME/OpenSourceFix-AI
cd OpenSourceFix-AI

python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

Set your API keys in `config/config.yaml` or via environment variables:

```bash
export GEMINI_API_KEY=your_key_here
export GITHUB_TOKEN=your_token_here
```

---

## Usage

### Command line

```bash
python main.py \
  --repo https://github.com/pallets/flask \
  --owner pallets \
  --repo-name flask \
  --issue 4556
```

Add `--apply-patch` to actually write the fix to disk (default is dry-run).

### Web UI

```bash
# Terminal 1 — backend
cd api && uvicorn server:app --reload --port 8000

# Terminal 2 — frontend
cd frontend && npm install && npm run dev
```

Open `http://localhost:5173`

### Run tests

```bash
pytest tests/ -v -m "not slow"
```

---

## Example Output

```
PATCH for src/flask/sessions.py::open_session()
======================================================
--- a/src/flask/sessions.py
+++ b/src/flask/sessions.py
@@ -72,6 +72,9 @@ class SecureCookieSessionInterface(SessionInterface):
     def open_session(self, app, request):
+        if not app.secret_key:
+            return None
         s = self.get_signing_serializer(app)
         if s is None:
             return None

Validation passed  : True
Applies cleanly    : True (dry-run)
Attempts needed    : 1
```

---

## Evaluation

Run the benchmark on a set of known issues:

```bash
python -m evaluation.benchmark_runner --benchmark evaluation/sample_benchmark.json
```

Output:

```
==================================================
  OpenSourceFix AI — Evaluation Report
==================================================
  Issues evaluated    : 10
  File Hit@1          : 7/10 = 70.0%
  File Hit@5          : 9/10 = 90.0%
  Function Hit Rate   : 6/10 = 60.0%
  Patch Pass Rate     : 5/8  = 62.5%
==================================================
```

An HTML dashboard is saved to `evaluation/reports/`.

---

## Future Work

- GitHub PR agent (create branch, commit, open PR via GitHub API)
- SWE-bench Lite evaluation
- VS Code extension
- Multi-language support (Java, Go, Rust)
- Knowledge graph for repository structure
