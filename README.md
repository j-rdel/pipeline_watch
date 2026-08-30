# PipelineWatch

Copiloto de CI/CD que faz **triagem automática de execuções de GitHub Actions
que falharam**. Recebe um `run_id`, investiga o log, classifica a causa raiz,
consulta um runbook (RAG), estima o risco de ser um teste flaky com base no
histórico e decide entre **abrir um PR de correção** (nunca faz merge) ou
**postar um diagnóstico estruturado no Discord**.

> Projeto final do Módulo 2 — SENAI. Evolução do mini-projeto
> `senai-pr-reviewer` (semana 08).

## Status

🚧 Em desenvolvimento. Consulte o
[quadro Kanban](https://github.com/users/jardelurban/projects) e as
issues do repositório para acompanhar o progresso.

## Requisitos

- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/)
- [Ollama](https://ollama.com/) rodando local com o modelo `qwen3:8b`:
  ```sh
  ollama pull qwen3:8b
  ```
- Docker (opcional, apenas para o fluxo n8n)

## Instalação

```sh
uv sync
cp .env.example .env
# edite .env se for apontar para GitHub/Discord reais
```

## Uso (preview)

```sh
# Modo fixture (sem rede, usa logs gravados em fixtures/)
uv run pipeline-watch triage --run-id 42 --source fixture

# Modo GitHub real (requer GITHUB_TOKEN e GITHUB_REPO no .env)
uv run pipeline-watch triage --run-id 987654321 --source github
```

Sem `--post` ou com `PW_DRY_RUN=true`, a aplicação **nunca** abre PR nem posta
no Discord — apenas imprime o payload que seria enviado.

## Documentação

- [Arquitetura e diagrama LangGraph](./docs/architecture.md) *(a criar)*
- [Prompts do agente](./docs/prompts/) *(a criar)*
- [Runbook (fonte do RAG)](./docs/runbook/) *(a criar)*
- [Evidências de execução](./docs/evidencias/) *(a criar)*

## Roadmap resumido

Ver [issues do repositório](../../issues) — cada tarefa vira uma issue no
GitHub Project *PipelineWatch* (colunas: Backlog → A Fazer → Em Andamento →
Bloqueado → Em Revisão → Concluído).

## Licença

Uso educacional — SENAI Módulo 2.
