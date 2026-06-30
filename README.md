# OpenSourceFix AI

Autonomous open-source issue resolution agent.

## Pipeline

```
GitHub Repo + Issue → Clone → Index → Keywords → Rank Files → Localize Bug → LLM Fix
```

## Setup

```bash
pip install -r requirements.txt
cp config/config.yaml config/config.yaml   # edit API keys
```

## Run

```bash
python main.py \
  --repo  https://github.com/tiangolo/fastapi \
  --owner tiangolo \
  --repo-name fastapi \
  --issue 1234
```

## Test

```bash
pytest tests/
```

## Structure

```
repository_analysis/   # clone, scan, parse, index, rank
issue_analysis/        # fetch issue, extract keywords
bug_localization/      # combine signals → suspect files
fix_generation/        # LLM prompt + response
utils/                 # config, logging, LLM adapters
config/                # config.yaml
tests/                 # pytest unit tests
```
repository_analysis/   # Clone, scan, parse, index, and analyze repository structure
issue_analysis/        # Fetch GitHub issue, parse description, extract keywords
retrieval/             # Generate embeddings, build FAISS index, semantic search
bug_localization/      # Rank and identify probable buggy files
fix_generation/        # Generate repository-aware code fixes using LLM
validation/            # Run pytest, validate generated fixes, create feedback
workflow/              # LangGraph orchestration of all AI agents
pr_generator/          # Generate GitHub-style Pull Request summaries
utils/                 # Configuration, logging, LLM adapters
config/                # config.yaml
tests/                 # Pytest unit tests
```
