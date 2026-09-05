# Agent RAG evaluation sets

This directory contains version-controlled evaluation definitions for the Chaldea Agent knowledge-retrieval experiments. The cases describe what to check; they do not contain live model answers.

`rag_cases.json` is the immutable exploratory evaluation set created for the pre-curation legacy-corpus baseline. `rag_cases_curated_v1.json` is the authority-aware set for Curated Corpus v1 after Phase 15C.6A. The original set and the external baseline output remain unchanged.

For a controlled PRE-RAG versus POST-RAG comparison, use `rag_cases_curated_v1.json` for both runs and keep the generation model, prompt, model parameters, and case order constant. Knowledge Retrieval should be the principal experimental change. Do not overwrite `D:\pyweb\chaldea-reports\phase15b-rag-baseline.json`; it belongs to the exploratory pre-curation experiment and is not the direct comparison baseline for Curated Corpus v1.

The initial corpus targets authored, unstructured FGO explanations (mechanics, beginner guidance, strategy, and reviewed lore). Structured servant facts such as IDs, classes, rarities, skills, and Noble Phantasms are intentionally marked `out_of_scope_structured_fact` because they belong to the future Tool Calling path backed by the V2 servant service/API, not ordinary RAG retrieval.

## Case format and context

Each case in `rag_cases.json` includes an ID, category, question, source reference, concise expected factual checkpoints, and relevant forbidden claims. `rag_cases_curated_v1.json` adds `authority_scope` and `expected_scope_behavior` so reviewers can check whether an answer preserves current-official, historical, editorial, or Tool Calling boundaries. Factual checkpoints originate from the curated repository documents; they are not intended to be essay answers.

Cases without `conversation_group` are independent. The evaluation runner starts each one with `conversation_id = None`, so one case cannot influence another. Cases in the same `conversation_group` share only the provider-returned conversation ID: the first turn starts fresh, and later turns reuse that group’s ID. Groups never share IDs.

## Scoring after baseline capture

The runner records raw answers and metadata only. Human review can later assign:

- `2` — correct and grounded;
- `1` — partially correct or incomplete;
- `0` — incorrect, unsupported, or fabricated.

Also record `hallucination` (`true`/`false`) and `retrieval_used` (`true`/`false`). The retrieval flag is experiment metadata supplied by the operator, not an automatic statement about remote workflow structure. A clear limitation response for an out-of-scope case is a successful grounded behavior; a confident invented answer is a failure.

## Running the raw baseline

From `v2/`, using the project environment:

```text
..\.venv\Scripts\python.exe manage.py evaluate_agent \
  --cases evals/rag_cases.json \
  --output D:\pyweb\chaldea-reports\phase15b-rag-baseline.json
```

The output path is explicit and should remain outside Git. Existing output is never overwritten unless `--overwrite` is supplied. The evaluator uses its evaluation-only streaming adapter to capture execution metadata; the production Agent API continues to use `apps.agent.services.chat()`. It does not write credentials, headers, raw provider payloads, or automatic scores.

## Experiment metadata and pacing

The evaluator does not inspect Dify or infer retrieval state. These are operator-supplied experiment metadata fields:

- **Pre-RAG:** omit `--retrieval-used` (it defaults to `false`).
- **Post-RAG:** include `--retrieval-used` to record `true`.
- `--experiment-label` optionally records a human-readable run label.
- `--delay-seconds` accepts a non-negative float and waits between evaluation requests; it defaults to `0` and performs no automatic retry.

Example curated PRE-RAG run:

```text
..\.venv\Scripts\python.exe manage.py evaluate_agent \
  --cases evals/rag_cases_curated_v1.json \
  --output D:\pyweb\chaldea-reports\curated-v1-pre-rag.json \
  --experiment-label curated-v1-pre-rag
```

Example curated POST-RAG run with explicit pacing:

```text
..\.venv\Scripts\python.exe manage.py evaluate_agent \
  --cases evals/rag_cases_curated_v1.json \
  --output D:\pyweb\chaldea-reports\curated-v1-post-rag.json \
  --retrieval-used \
  --experiment-label curated-v1-post-rag \
  --delay-seconds 7
```

## Tool-routing evaluation

The Agent has three information paths:

- Knowledge Retrieval for archive, mechanics, strategy, and world-setting explanations;
- `lookup_servant` for exact structured Servant facts;
- `tavily_search` for current, recent, or time-sensitive web information.

Knowledge Retrieval remains always-on before the Agent. Tool-routing evaluations
therefore measure Tool selection, not exclusive branching between RAG and Tools.

`tool_routing_cases_v1.json` is a small curated set for checking whether the
Agent routes structured Servant facts to `lookup_servant`, general FGO
knowledge to RAG, and boundary questions to the appropriate combination or
controlled outcome. Run it with the same `evaluate_agent` command and an
output path outside Git:

```text
..\.venv\Scripts\python.exe manage.py evaluate_agent \
  --cases evals/tool_routing_cases_v1.json \
  --output D:\pyweb\chaldea-reports\tool-routing-v1.json \
  --retrieval-used \
  --experiment-label tool-routing-v1
```

Routing expectations are case metadata (`servant_tool`, `rag`, or `both`). The
current Chatflow runs Knowledge Retrieval before the Agent for every query, so
the physical `actual_routing` may be `both` even for a structured servant
question. The primary deterministic metric is `tool_routing_match`: it compares
the expected `expected_tool_invoked` value (`true` for `servant_tool`/`both`,
`false` for `rag`) with the observed `tool_invoked` value. The legacy
`routing_match` field remains an exclusive-source comparison for backward
compatibility and should not be used as the primary metric. The runner records
both routing fields, tool name/input/response metadata, retrieval metadata,
compact executed-node summaries, final answer, status, success,
`elapsed_seconds`/`latency_seconds`, and sanitized error details when the
provider supplies them. Duplicate Tool traces are collapsed by `tool_call_id`
or by deterministic tool name/input identity, and reasoning or full execution
payloads are not persisted. It does not judge factual answer quality or infer
routing from answer text. If the provider supplies no routing metadata,
`actual_routing` is `unknown` and both routing checks are `false`.

## Web Search routing evaluation

`web_search_routing_cases_v1.json` contains current-information, structured
Servant, stable archive, and mixed-source cases. Cases declare
`expected_tools` as a list (possibly empty). The evaluator records a
deduplicated `actual_tools` list from the structured SSE trace and sets
`tool_selection_match` when the two sets are equal. Repeated calls to one Tool,
such as Tavily query reformulation, remain visible in the compact per-call
inputs and response metadata while counting once in `actual_tools`.

Run it with an output path outside Git:

```text
..\.venv\Scripts\python.exe manage.py evaluate_agent \
  --cases evals/web_search_routing_cases_v1.json \
  --output D:\pyweb\chaldea-reports/web-search-routing-v1.json \
  --retrieval-used \
  --experiment-label web-search-routing-v1
```
