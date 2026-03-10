# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This project implements a **self-validating multi-LLM pipeline** for constraint-satisfaction problems. The core idea: one LLM generates a Python verifier function from a problem spec, another LLM iteratively generates candidate outputs, and the verifier's feedback is fed back as corrective prompts until all constraints are satisfied or max iterations is reached.

## Running the Pipelines

Each pipeline must be run from **within its own directory**, as both use relative paths for `outputs/`, `logs/`, etc.

```bash
# Mason pipeline
cd mason_pipeline
python pipeline.py

# Chinmay pipeline
cd chinmay_pipeline
python pipeline.py
```

**Environment setup** (Python 3.9 venv at repo root):
```bash
source venv/bin/activate
```

**Dependencies:** `ollama` Python package. Ollama must be running locally, and any referenced models (e.g. `glm-4.7:cloud`, `gemma3:27b-cloud`, `gemma2:2b`, `qwen2.5:1.5b`) must be available via the Ollama client.

**Standalone verifiers** (run from repo root):
```bash
python verify_500digit.py   # manual check for 700-digit string problem
python verify_1024bit.py    # manual check for 1024-bit string problem
python validate.py
```

## Architecture

### Two parallel pipeline implementations

Both implement a `SelfValidatingPipeline` class with the same two-phase loop:

**Phase 1** — Verifier generation: An LLM (mason uses `glm-4.7:cloud`; chinmay uses the configured `model`) is prompted to write a `verify(output: str)` function that checks all problem constraints and returns a tuple.

**Phase 2** — Iterative output generation: A second LLM (mason uses `gemma3:27b-cloud`; chinmay uses the same configured `model`) generates candidate outputs. After each attempt, the verifier is executed (with a 10s SIGALRM timeout) and its diagnostic message is appended as a new user turn, forming a self-correcting conversation loop.

### Key differences between the two pipelines

| | `mason_pipeline/` | `chinmay_pipeline/` |
|---|---|---|
| Problem input | JSON files (`cases/*.json`) | Markdown files (`prompts/*.md`) |
| Verifier model | `glm-4.7:cloud` | Configured `model` arg |
| Output model | `gemma3:27b-cloud` | Configured `model` arg |
| Verifier tuple order | `(is_valid, score, message)` | `(is_valid, message, score)` |
| Verifier validation | None | Runs 3 smoke-test inputs before accepting |
| Context trimming | Yes — keeps system + problem + last 12 msgs | No |

### Case/problem schema (mason_pipeline)

JSON files in `mason_pipeline/cases/` must have:
```json
{
  "case_number": int,
  "genre": str,
  "prompt": str,
  "constraints": [str, ...],
  "objective": str,
  "output_format": str,
  "full_content": str   // full problem text sent to LLMs
}
```

### Verifier contract

The generated `verify(output: str)` function must return:
- **mason**: `(is_valid: bool, score: float, message: str)` — 3-tuple
- **chinmay**: `(is_valid: bool, message: str, score: float[, details: dict])` — 3 or 4-tuple

Both pipelines cap output length at 50,000 chars and enforce a 10-second execution timeout via SIGALRM (Unix/macOS only).

### Output artifacts

After each run, both pipelines write:
- `outputs/verifier.py` — the generated verifier code (overwritten each run unless `reuse_verifier=True`)
- `outputs/iterations/iter_N.json` — per-iteration snapshot
- `outputs/final/result_TIMESTAMP.json` — full result including verifier code, all iterations, final output
- `outputs/final/latest_output.txt` — raw final output string
- `logs/iteration_N.json` — feedback sent to the model at each step
