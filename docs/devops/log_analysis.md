# Análise de logs de CI com IA

Cumpre §4.8 do desafio: "Utilizar IA para analisar e explicar logs de pelo
menos duas etapas entre CI, Dockerfile, lint, testes, build e, quando houver,
CD ou deploy".

## Setup

- **Modelo:** Ollama `qwen3:8b` (local)
- **Prompt (system):**
  > Você é um SRE analisando logs de CI. Para o log abaixo, produza uma
  > explicação markdown curta com três partes: Summary (1 frase),
  > Signals (2-3 excerpts que sustentam), Recommended next step (1 frase
  > imperativa). Se o log mostra sucesso, diga sucesso e não invente
  > problema.
- **Jobs analisados:**
  1. `ruff check` — log **real** de execução local (equivale ao que o CI
     produz — comando idêntico ao workflow)
  2. `pytest` — log **simulado** de falha (4 testes falhando em 3 módulos)
     pra dar ao modelo algo interessante pra explicar

## Job 1 — `ruff check`

### Log de entrada

```
All checks passed!
```

### Análise da IA

> **Summary**
> The CI job passed successfully as all checks completed without errors.
>
> **Signals**
> - `All checks passed!` (explicit confirmation of success)
> - No error messages or failed step indicators in the log.
>
> **Recommended next step**
> Monitor the deployment or check if the build is ready for release.

### Verificação humana

Correto. O modelo não inventou problema num log limpo — isso valida a
regra do system prompt. **Único ponto a ajustar:** "monitor deployment"
é genérico demais; sugestão mais útil seria "proceed to pytest job".

## Job 2 — `pytest` (falha simulada)

### Log de entrada (excerpt)

```
tests/test_policy.py::test_rejects_secret_env_var_reference FAILED       [ 20%]
tests/test_flakiness_e2e.py::test_third_run_flips_is_flaky_on FAILED     [ 45%]
tests/test_flakiness_e2e.py::test_second_run_sees_one_prior_similar FAILED [ 46%]
tests/test_publishers.py::test_discord_retries_on_5xx_then_succeeds FAILED [ 70%]

_____________ test_rejects_secret_env_var_reference _____________
>       assert "GITHUB_TOKEN" in decision.reason
E       AssertionError: assert 'GITHUB_TOKEN' in 'all checks passed'

==================== 4 failed, 73 passed in 12.34s ============================
Error: Process completed with exit code 1.
```

### Análise da IA

> **Summary**
> The CI job failed due to 4 test failures out of 77, primarily related to
> policy checks, flakiness detection, and retry logic.
>
> **Signals**
> 1. `AssertionError: assert 'GITHUB_TOKEN' in 'all checks passed'` (policy test failure)
> 2. `assert False is True` (flakiness test failure)
> 3. `assert 0 == 1` (similar failures count mismatch)
> 4. `assert 1 == 2` (Discord retry count mismatch)
>
> **Recommended next step**
> Investigate the failing tests to determine if the issues stem from code
> changes, test logic errors, or environment mismatches.

### Verificação humana

O modelo:
- **Acertou:** correlacionou as 4 falhas em 3 categorias temáticas (policy /
  flakiness / retry) — leitura que economiza tempo real do plantonista.
- **Não caiu em armadilha:** o log dizia `assert 'GITHUB_TOKEN' in 'all
  checks passed'` — o `all checks passed` do OUTRO job apareceu como
  contexto adversarial no traceback do primeiro. O modelo ignorou.
- **Ponto de melhoria:** recomendação segue genérica ("investigate the
  failing tests"). Prompt v2 poderia pedir uma primeira hipótese
  específica pro cluster mais impactante (ex.: "os dois testes de
  flakiness_e2e falham juntos — provavelmente uma regressão em
  `estimate_flakiness`").

## Reprodução

```sh
uv run python -c "
from pathlib import Path
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

SYSTEM = '''/no_think
You are an SRE analysing CI job logs. For the log below, output markdown with:
- Summary (1 sentence)
- Signals (2-3 log excerpts backing your summary)
- Recommended next step (1 imperative sentence)
Be honest — if the log shows a clean pass, say so and don't invent problems.'''

for path in ['/tmp/pw_ruff.log', '/tmp/pw_pytest_fail.log']:
    log = Path(path).read_text()
    llm = ChatOllama(model='qwen3:8b', temperature=0.2)
    print(llm.invoke([SystemMessage(SYSTEM), HumanMessage(log)]).content)
    print('---')
"
```

## Ver também

- Pipeline em si: [`ci.md`](./ci.md)
- Anomalia + estimativa de risco (usando o próprio flakiness estimator):
  [`anomaly_and_risk.md`](./anomaly_and_risk.md)
