# Evaluation Framework

## Scope

- End-to-end RAG answer quality
- Correct PDF and page citations
- Raw retrieval Top-1/Top-3 success
- Reranker impact and false positives
- Rewrite impact
- No-answer fallback
- Consent-based cross-conversation memory
- SQL route response
- SSE token/source/done behavior

## Required Environment

Use a dedicated evaluation account. The account must own the documents referenced
by the datasets.

```powershell
$env:EVAL_EMAIL="evaluation@example.com"
$env:EVAL_PASSWORD="your-evaluation-password"
$env:EVAL_BASE_URL="http://localhost:8000"
$env:EVAL_TIMEOUT_SECONDS="120"
```

Do not place credentials in evaluation scripts or commit them to source control.

For local development, copy the committed template:

```powershell
Copy-Item .env.evaluation.example .env.evaluation
```

Then edit `.env.evaluation`. The real file is ignored by Git and loaded
automatically. Shell environment variables still take priority over file values.

## RAG API Evaluation

The evaluator discovers every `*_dataset*.json` file, creates a separate temporary
conversation for each question, and deletes it afterward.

```powershell
.\venv\Scripts\python.exe -m evaluation.evaluate_rag
```

Quick smoke test:

```powershell
.\venv\Scripts\python.exe -m evaluation.evaluate_rag --limit 5
```

Report:

```text
evaluation/reports/rag_evaluation_report.json
```

The logistics dataset contains placeholder expected answers such as
`Policy Statement 1`. Those cases are excluded from answer-accuracy calculations
but remain included in exact PDF/page citation evaluation.

## Direct Retrieval Audit

```powershell
.\venv\Scripts\python.exe -m evaluation.audit_retrieval_quality
```

Report:

```text
evaluation/reports/retrieval_quality_audit.json
```

## Memory, SQL, and Streaming Evaluation

Memory evaluation writes and deletes `favorite_color` for the evaluation user.
Run it only with a dedicated account:

```powershell
$env:EVAL_ALLOW_MEMORY_MUTATION="true"
$env:EVAL_SECONDARY_EMAIL="second-evaluation-user@example.com"
$env:EVAL_SECONDARY_PASSWORD="second-user-password"
.\venv\Scripts\python.exe -m evaluation.evaluate_capabilities
```

Without `EVAL_ALLOW_MEMORY_MUTATION=true`, the memory suite is safely skipped;
SQL and streaming checks still run.

Secondary credentials are optional. When provided, the evaluator verifies that a
memory saved by the primary user cannot be recalled by the secondary user.

Report:

```text
evaluation/reports/capability_evaluation_report.json
```

## Interpretation

- `answer_accuracy` uses normalized expected-answer containment plus token F1.
- `citation_file_and_page_accuracy` requires the expected PDF and page in the same
  returned source item.
- `cross_document_top_1_rate` measures an actual wrong-document Top-1 result.
- Placeholder ground truth is never reported as a failed answer.
- Capability checks report skipped tests separately from executed tests.

## Legacy Reports

`evaluation/reports/logistics_report.json` was produced by the previous evaluator.
Its `0%` answer accuracy is based on placeholder ground truth and must not be used
as the canonical answer-quality score. New runs write `rag_evaluation_report.json`.
