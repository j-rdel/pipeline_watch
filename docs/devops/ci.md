# CI pipeline

Cumpre §4.8 do desafio: pipeline que executa **lint, testes e build**.
Deploy é opcional e não implementado (o projeto é uma CLI, não um serviço).

## Workflow

`.github/workflows/ci.yml` roda em `push` e `pull_request` contra `main` e
`develop`. Concurrency configurada pra cancelar runs anteriores da mesma
ref (economia de minutos).

### Jobs

| Job | Comando | Dispara em | Duração típica |
|---|---|---|---|
| `lint` | `uv run ruff check src tests` | sempre | ~10 s |
| `test` | `uv run pytest -q -m "not integration"` | sempre | ~15 s |
| `build` | `uv build --wheel` | após lint + test | ~5 s |

Integration tests (`-m integration`) **não rodam no CI** — dependem de
Ollama local + download de fastembed (~90 MB). Rodam sob demanda:

```sh
uv run pytest -m integration
```

## Reprodução local (sanity antes de push)

```sh
uv run ruff check src tests && \
uv run pytest -q -m "not integration" && \
uv build --wheel
```

Se essas três passam localmente, o CI passa. Todas as três são as MESMAS
comandos executados no workflow — sem "funciona pra mim".

## Artefato produzido

`build` publica o wheel em `dist/*.whl` como artifact da run
(retention 7 dias). Downloadable via
`gh run download <run-id> -n pipeline_watch-wheel`.

## Fail-fast

`build` tem `needs: [lint, test]` — não gasta tempo empacotando código que
já falhou nas etapas anteriores.

## Como o CI vê logs desta app

Rodando `pipeline_watch triage --source github --run-id <workflow-run-id>`
contra um GITHUB_TOKEN com escopo `actions:read` traz os logs dos jobs do
CI de volta pro fluxo — literalmente pipeline_watch analisando seu próprio
pipeline. Ver [`log_analysis.md`](./log_analysis.md) pro exemplo.
