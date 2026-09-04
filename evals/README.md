# Agent RAG evaluation set

This directory contains the version-controlled evaluation definitions for the first Chaldea Agent knowledge-retrieval experiment. The cases describe what to check; they do not contain live model answers.

The initial corpus targets authored, unstructured FGO explanations (mechanics, beginner guidance, strategy, and reviewed lore). Structured servant facts such as IDs, classes, rarities, skills, and Noble Phantasms are intentionally marked `out_of_scope_structured_fact` because they belong to the future Tool Calling path backed by the V2 servant service/API, not ordinary RAG retrieval.

## Case format and context

Each case in `rag_cases.json` includes an ID, category, question, source reference, concise expected factual checkpoints, and relevant forbidden claims. Factual checkpoints originate from the repository pages identified in the Phase 15A assessment; they are not intended to be essay answers.

Cases without `conversation_group` are independent. The evaluation runner starts each one with `conversation_id = None`, so one case cannot influence another. Cases in the same `conversation_group` share only the provider-returned conversation ID: the first turn starts fresh, and later turns reuse that group’s ID. Groups never share IDs.

## Scoring after baseline capture

The runner records raw answers and metadata only. Human review can later assign:

- `2` — correct and grounded;
- `1` — partially correct or incomplete;
- `0` — incorrect, unsupported, or fabricated.

Also record `hallucination` (`true`/`false`) and `retrieval_used` (`true`/`false`). For the pre-RAG baseline, `retrieval_used` is conceptually `false` because no Knowledge Retrieval node is active yet. A clear limitation response for an out-of-scope case is a successful grounded behavior; a confident invented answer is a failure.

## Running the raw baseline

From `v2/`, using the project environment:

```text
..\.venv\Scripts\python.exe manage.py evaluate_agent \
  --cases evals/rag_cases.json \
  --output D:\pyweb\chaldea-reports\phase15b-rag-baseline.json
```

The output path is explicit and should remain outside Git. Existing output is never overwritten unless `--overwrite` is supplied. The command calls only `apps.agent.services.chat()`; it does not call Dify directly and does not write credentials, headers, raw provider payloads, or automatic scores.
