# n8n low-code — relatório semanal para Discord

Cumpre §4.9 do desafio ("Low-Code para QA, SRE e agentes"):
> O fluxo deverá possuir ao menos um gatilho, integrar-se à aplicação ou
> a um de seus serviços e produzir uma saída observável.

## O fluxo

```
┌────────────────────┐   ┌──────────────────────┐   ┌────────────────────┐
│ Cron: Seg 09:00    │──▶│ HTTP GET /reports/   │──▶│ Function: build    │
│ (scheduleTrigger)  │   │ weekly?limit=5       │   │ Discord embed      │
└────────────────────┘   └──────────────────────┘   └──────────┬─────────┘
                                                                │
                                                    ┌───────────▼──────────┐
                                                    │ IF skip when empty   │
                                                    └───────────┬──────────┘
                                                                │ (não pula)
                                                    ┌───────────▼──────────┐
                                                    │ POST webhook Discord │
                                                    └──────────────────────┘
```

- **Gatilho:** cron toda segunda 09:00 (America/Sao_Paulo).
- **Integração com a aplicação:** GET `/reports/weekly` — endpoint FastAPI
  em `src/pipeline_watch/api.py` que agrega `IncidentStore.recent_signatures`.
- **Saída observável:** mensagem embed no canal Discord com o top-5 de
  assinaturas de falha da última semana + total de incidents.
- **Lógica principal permanece na aplicação:** o n8n só orquestra
  cron + HTTP + shape do embed. Cálculo de anomalia, autofix, gate — tudo
  no Python. n8n é adaptador, não substituto.

## Reprodução (~10 min)

### 1. Subir o pipeline_watch API localmente

```sh
uv run pipeline_watch serve --port 8000
```

Deixe rodando. Confira:
```sh
curl http://localhost:8000/health
# {"status":"ok"}
```

### 2. Subir o n8n

```sh
cd n8n
docker compose up -d
```

Abra http://localhost:5678 (user `admin` / senha `change-me` — troque
antes de qualquer uso não-local).

### 3. Importar o fluxo

Na UI do n8n:
1. **Workflows → Import from File**
2. Selecione `n8n/workflows/weekly_report.json`
3. Antes de ativar, defina as env vars do container:
   - `PIPELINE_WATCH_URL` (já configurada no compose = `http://host.docker.internal:8000`)
   - `DISCORD_WEBHOOK_URL` — cole seu webhook do Discord

Para setar `DISCORD_WEBHOOK_URL` no compose, adicione no bloco `environment`:
```yaml
- DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/XXX/YYY
```
E reinicie: `docker compose restart n8n`.

### 4. Testar o fluxo

Botão **Execute workflow** (canto superior direito) roda uma vez ignorando
o cron. Veja:
- Node "GET /reports/weekly" → deve mostrar o JSON do endpoint
- Node "Build Discord embed" → deve mostrar o payload formatado
- Node "POST to Discord webhook" → 204 em caso de sucesso

Se não houver incidentes registrados ainda, o fluxo é interrompido no
`IF skip when empty` — comportamento intencional pra não spam-ar canal
vazio.

### 5. Ativar

Toggle **Active** no canto superior da UI. Ele passa a rodar toda segunda
às 09:00.

## Alterações típicas

- **Trocar cadência:** edite o `cronExpression` no primeiro nó
  (`0 9 * * 1` = segunda 09h).
- **Trocar canal:** mude `DISCORD_WEBHOOK_URL` no compose e restart.
- **Trocar limit:** URL do HTTP request → `?limit=10`.

## Extensão opcional (ChatOps)

Para o "extra" mencionado no §4.9 (comunicar resultados via ChatOps):
o mesmo webhook Discord é reusado por `DiscordPublisher` no fluxo síncrono
de triage. Todo notify_only já vai pro canal em tempo real. O n8n cobre o
lado assíncrono/relatório-agregado; o publisher cobre o síncrono/alerta.

## Ver também

- Endpoint que alimenta o fluxo: `src/pipeline_watch/api.py`
- Testes do endpoint: `tests/test_api.py`
- Publisher síncrono complementar: `src/pipeline_watch/publishers/discord.py`
