# Estratégia de testes

Cumpre §4.7 do desafio: cobertura por camada + pelo menos um teste de
integração/E2E, com IA usada tanto para gerar testes quanto para revisar
código.

## Categorias

| Categoria | Marker pytest | Como rodar | Depende de |
|---|---|---|---|
| Unit | (nenhum) | `uv run pytest -q -m "not integration"` | nada externo |
| Integration / E2E | `integration` | `uv run pytest -q -m integration` | Ollama local + fastembed download |

Autouse fixtures em `tests/conftest.py` substituem LLM real (`_stub_llm`),
RAG real (`_stub_rag`) e memória real (`_isolated_memory`) para todo teste
NÃO marcado como `@pytest.mark.integration`. Isso mantém o suite unit em
< 5s e reprodutível offline.

## Cobertura por módulo (unit)

| Módulo | Arquivo de teste | # testes | Cobre |
|---|---|---|---|
| `schema` | `test_schema.py` | 7 | Pydantic bounds, roundtrip, required fields |
| `state` | (implícito em graph) | – | TypedDict shape via graph |
| `graph` | `test_graph.py` | 4 | topologia (fan-out, fan-in, condicional), correlation_id |
| `tools/github_client` | `test_github_client.py` | 8 | fixture backend, respx-mocked HTTP, retry-on-5xx, fail |
| `tools/mcp_server` | `test_mcp_server.py` | 3 | tool registration, invocation, response payload |
| `nodes/fetch_run_context` | `test_fetch_run_context.py` | 4 | integração com GitHubClient, filtro de failed jobs |
| `rag` | `test_rag.py` | 6 | chunking, build, cache, rebuild-on-stale, query |
| `memory` | `test_memory.py` | 13 | signature parsing (7 famílias), CRUD, janela 7d, ranking |
| `policy` | `test_policy.py` | 8 | cada regra de rejeição em isolamento |
| `nodes/enforce_policy` | `test_enforce_policy.py` | 4 | transições de estado, routing |
| `observability` | `test_observability.py` | 6 | logs JSON, spans OTel, correlation_id, exceção |
| `publishers` | `test_publishers.py` | 10 | dry-run, POST real, retry, embed color/title |
| Flakiness E2E | `test_flakiness_e2e.py` | 3 | grafo 3x sobre mesma fixture, `is_flaky` flipa em run #3 |
| **Adversarial E2E (prioridade)** | `test_adversarial_e2e.py` | 3 | prompt injection não abre PR — ver [priority_test.md](./priority_test.md) |

**Total unit: 79.** Todos passam em < 8 s.

## Integração / E2E

| Arquivo | Requer | O que valida |
|---|---|---|
| `test_llm_integration.py` | Ollama + qwen3:8b | Classify em log real produz label `LINT` |
| `test_rag_integration.py` | fastembed download (~90MB, 1x) | Ranking real do FAISS: "ruff E501" → lint.md, "AssertionError" → test_failures.md |

**Total integration: 3.** Rodam em ~40 s (dependendo do modelo).

## Uso de IA para QA

- **Geração de testes com IA**: os fixtures adversariais (`adversarial-fixture*`)
  foram desenhados iterativamente com auxílio de LLM para maximizar a
  cobertura de vetores de manipulação (verbos suspeitos, marcadores de
  chat template, referências a env vars sensíveis).
- **Revisão de código com IA**: uma revisão do módulo `policy.py` gerada
  pelo Ollama qwen3:8b está registrada em
  [`ai_code_review.md`](./ai_code_review.md), incluindo pontos fortes,
  issues por severidade e sugestões concretas.

## Priorização por risco

Critério: **impacto se falhar** > **frequência de execução** > **cobertura**.

Ranking (do maior risco pro menor):

1. **`test_prompt_injected_run_never_opens_a_pr`** — falha = agent
   comprometido pode abrir PRs maliciosos. Ver [priority_test.md](./priority_test.md).
2. `test_flakiness_e2e::test_third_run_flips_is_flaky_on` — falha = flakes
   crônicos deixam de ser detectados, degradando qualidade da triagem.
3. `test_github_client::test_github_mode_retries_on_5xx_then_succeeds` —
   falha = qualquer instabilidade transiente da GitHub API vira falha do
   agente inteiro.
4. `test_policy::test_rejects_secret_env_var_reference` — falha = secret
   leakage via output do agente.

## Como interpretar falhas

- **Unit failure** → bug local; leia o traceback, corrija, re-rode.
- **Integration failure** → Ollama offline, modelo não baixado, ou fastembed
  não conseguiu baixar. Verifique `curl http://localhost:11434/api/tags`.
- **Adversarial priority test failure** → **BLOQUEIA MERGE**. Investigue
  como um regressor comprometeu o PolicyGate antes de qualquer outra coisa.
