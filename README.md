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
