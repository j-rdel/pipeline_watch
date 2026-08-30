# Arquitetura do pipeline_watch

Cumpre §5.2 do README obrigatório (classificação + diagrama).

## Classificação: sistema híbrido

**Não é agente puro** — o fluxo é um DAG com edges deterministicamente
declaradas em `src/pipeline_watch/graph.py`. O LLM não escolhe o próximo
passo, o grafo escolhe.

**Não é workflow determinístico** — três nós delegam *decisão* ao modelo
(classify_failure, synthesize_diagnosis, propose_patch), com output
restringido por schema Pydantic. A qualidade do report depende do LLM,
não só de regras.

**É híbrido:** roteamento e enforcement (decide_action, enforce_policy)
são determinísticos; classificação, síntese e geração de patch são LLM.
A PolicyGate é o safety-net que impede o LLM de causar ação irreversível.

## Diagrama LangGraph

```
                        ┌───────────────────┐
                        │ fetch_run_context │  ← MCP tool (get_workflow_run
                        └─────────┬─────────┘    + get_job_logs) OU fixture
                                  │
                        ┌─────────┴─────────┐   ← parallel super-step
                        ▼                   ▼
              ┌─────────────────┐  ┌──────────────────┐
              │ classify_failure│  │ retrieve_runbook │  ← FAISS + fastembed
              │       (LLM)     │  │       (RAG)      │
              └────────┬────────┘  └────────┬─────────┘
                       └──────────┬─────────┘  ← fan-in
                                  ▼
                        ┌───────────────────┐
                        │ estimate_flakiness│  ← SQLite lookup
                        │  (deterministic)  │
                        └─────────┬─────────┘
                                  ▼
                      ┌───────────────────────┐
                      │ synthesize_diagnosis  │  ← LLM (structured output)
                      └───────────┬───────────┘
                                  ▼
                         ┌────────────────┐
                         │ decide_action  │  ← rule: classify + flakiness
                         │ (deterministic)│
                         └───┬────────┬───┘
             "autofix" ──────┘        └────── "notify_only"
                             ▼                ▼
                    ┌────────────────┐        │
                    │ propose_patch  │        │
                    │     (LLM)      │        │
                    └────────┬───────┘        │
                             ▼                │
                    ┌────────────────┐        │
                    │ enforce_policy │  ← PolicyGate: allowlist +
                    │(defense-in-depth)│    injection markers + verbs
                    └───┬────────┬───┘        │
      "autofix" ────────┘        └──── "notify_only"
                       │                      │
                       ▼                      ▼
                  ┌─────────┐        ┌────────────────┐
                  │ open_pr │        │ notify_discord │  ← webhook (real)
                  │(dry-run)│        └───────┬────────┘
                  └────┬────┘                │
                       └────────┬────────────┘
                                ▼
                     ┌──────────────────┐
                     │ persist_incident │  ← SQLite write
                     └────────┬─────────┘
                              ▼
                            END
```

## Estado compartilhado

`src/pipeline_watch/state.py::TriageState` — TypedDict com `total=False` (cada
nó preenche só uma fatia). Nós paralelos escrevem chaves **distintas**
(`classification` vs `runbook_snippets`) → sem race no merge.

## Responsabilidades por componente

| Componente | Local | Determinístico? |
|---|---|---|
| `fetch_run_context` | `nodes/fetch_run_context.py` | Sim (chama tool) |
| `classify_failure` | `nodes/classify_failure.py` | **LLM** |
| `retrieve_runbook` | `nodes/retrieve_runbook.py` | Sim (RAG) |
| `estimate_flakiness` | `nodes/estimate_flakiness.py` | Sim (SQL) |
| `synthesize_diagnosis` | `nodes/synthesize_diagnosis.py` | **LLM** |
| `decide_action` | `nodes/decide_action.py` | Sim (regra) |
| `propose_patch` | `nodes/propose_patch.py` | **LLM** |
| `enforce_policy` | `nodes/enforce_policy.py` | Sim (PolicyGate) |
| `open_pr` | `nodes/open_pr.py` | Sim (dry-run) |
| `notify_discord` | `nodes/notify_discord.py` | Sim (webhook) |
| `persist_incident` | `nodes/persist_incident.py` | Sim (SQL write) |

## Módulos de suporte

| Módulo | Responsabilidade |
|---|---|
| `state.py` | `TriageState` (TypedDict) |
| `schema.py` | `IncidentReport`, `Classification`, `Evidence`, `FlakinessScore`, `ProposedPatch`, enums |
| `config.py` | Settings via pydantic-settings (`.env`) |
| `llm.py` | Wrapper Ollama com structured output |
| `prompts.py` | System prompts dos 3 nós LLM |
| `rag.py` | FAISS + fastembed sobre `docs/runbook/` |
| `memory.py` | SQLite `IncidentStore` + `signature_from_logs` |
| `policy.py` | `PolicyGate` (allowlist, injection, verbs) |
| `observability.py` | structlog JSON + OTel spans + decorator `traced_node` |
| `tools/github_client.py` | httpx client (fixture + real GitHub) |
| `tools/mcp_server.py` | MCP server (2 read tools) |
| `publishers/discord.py` | Webhook Discord (real quando não dry-run) |
| `publishers/github_pr.py` | PR opener (sempre dry-run neste build) |
| `api.py` | FastAPI `/health` + `/reports/weekly` (para n8n) |
| `cli.py` | Typer app (`triage`, `serve`) |

## Fluxos de dados críticos

**Correlation ID** flui: CLI → state → structlog contextvars → OTel span
attribute → IncidentReport → SQLite → Discord footer. Um único ID conecta
todos os artefatos de uma execução.

**Error signature** é derivada de logs em `memory.signature_from_logs()`
por regex ordenada (ruff > pytest > py errors > http > build > timeout).
Chave estável usada tanto pra flakiness quanto pra agregação semanal.

## Fronteiras de confiança

- **Confiável:** `.env`, prompts, código do projeto, runbook markdown
- **Não confiável:** logs de CI, respostas do LLM, resposta da GitHub API

Todo dado não confiável passa por Pydantic (validação) ou PolicyGate
(enforcement) antes de virar side-effect.

## Extensão

- Novo tipo de failure → adicionar entrada em `_SIGNATURE_PATTERNS` +
  novo `.md` em `docs/runbook/` (o índice reconstrói sozinho).
- Novo destino de notificação → novo módulo em `publishers/` + wire no
  nó apropriado.
- Novo tipo de decisão → adicionar em `FailureClass` enum e testar
  o roteamento em `decide_action`.
