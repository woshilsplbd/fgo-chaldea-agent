# Chaldea Agent — Django + Dify FGO Knowledge Agent

Chaldea Agent is a Django application that connects an FGO knowledge experience to a Dify Chatflow.

## Core technologies

- Python and Django
- Dify
- RAG / knowledge retrieval
- Query rewriting
- Tool Calling / Function Calling
- Agent memory
- Tavily web search
- SSE transport

## Architecture

```text
Browser
  ↓
Django
  ↓
Dify Chatflow
  ├─ Query Rewriter
  ├─ Knowledge Retrieval / RAG
  ├─ lookup_servant
  ├─ Tavily Search
  └─ Memory
```

## Engineering results

The project includes conversation-aware RAG, anonymous-user isolation, conversation continuity, and stale-conversation recovery. The verified historical baseline is 148 passing Django tests.

Transport streaming is implemented, but the current Dify graph does not provide true token-level output.

