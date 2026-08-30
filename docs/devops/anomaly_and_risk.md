# Detecção de anomalia + estimativa de risco de falha

Cumpre §4.8 do desafio:
- "Detectar e explicar pelo menos uma anomalia (erro recorrente,
  latência alta, falha de tool, aumento da taxa de erro)"
- "Produzir uma estimativa simples de tendência, risco ou probabilidade
  de falha, utilizando dados reais ou simulados e documentados"

## Dogfood: o próprio estimador de flakiness

O pipeline_watch já implementa exatamente essa lógica em
`src/pipeline_watch/memory.py::IncidentStore` +
`nodes/estimate_flakiness.py`. Vou usar ele mesmo pra analisar risco no
CI histórico.

### Modelo (simples e explícito)

```
score           = similar_failures_7d / total_runs_7d
is_flaky        = score > 0.4  AND  similar_failures_7d >= 2
error_signature = primeiro token conhecido do log
                  ("ruff:E501", "pytest:AssertionError", "http:503", ...)
```

Threshold **0.4** foi escolhido conservadoramente: um flake precisa
aparecer em quase metade das runs recentes pra virar sinalização — evita
alarmar em ruído de 1-2 falhas isoladas.

O `AND similar_failures_7d >= 2` é o requisito extra: 1 falha isolada
nunca é flake, é bug real. Precisamos ver **repetição** pra classificar
como flaky.

## Cenário simulado (dados documentados)

História simulada de 7 dias — 8 runs do workflow `ci.yml`:

| Run | Signature | Outcome |
|---|---|---|
| #1 | `ruff:E501` | autofix |
| #2 | `pytest:AssertionError` | notify_only |
| #3 | `http:503` | notify_only |
| #4 | `http:503` | notify_only |
| #5 | `http:503` | notify_only |
| #6 | `ruff:E501` | autofix |
| #7 | `pytest:AssertionError` | notify_only |
| #8 (novo) | `http:503` | ??? |

Rodamos o estimador no run #8:

```python
similar_failures_7d = 3   # runs #3, #4, #5
total_runs_7d       = 7   # runs #1-#7
score               = 3/7 = 0.428
is_flaky            = True   # 0.428 > 0.4 AND 3 >= 2
```

### Anomalia detectada

**Assinatura `http:503` aparece em 4 de 8 runs (50%) na última semana.**
Isto é o cenário exato coberto pela regra do runbook
`docs/runbook/external_deps.md`:

> 3+ falhas similares em 24 h → abrir issue contra a client library,
> tagar oncall SRE.

O agent, com esse score, força `decision=notify_only` mesmo que o resto
do fluxo tivesse decidido autofix. Documentado em
`nodes/decide_action.py::decide_action`.

### Como reproduzir

```bash
python -c "
from pipeline_watch.memory import IncidentStore
from pathlib import Path
s = IncidentStore(db_path=Path('/tmp/demo.sqlite'))
for sig, out in [
    ('ruff:E501', 'autofix'),
    ('pytest:AssertionError', 'notify_only'),
    ('http:503', 'notify_only'),
    ('http:503', 'notify_only'),
    ('http:503', 'notify_only'),
    ('ruff:E501', 'autofix'),
    ('pytest:AssertionError', 'notify_only'),
]:
    s.record(run_id='demo', workflow='ci.yml', job_name='j',
             error_signature=sig, outcome=out, decision=out)

print('similar http:503:', s.count_similar('http:503'))
print('total runs 7d:  ', s.count_runs('ci.yml'))
print('score:          ', s.count_similar('http:503') / s.count_runs('ci.yml'))
print('recent top-k:   ', s.recent_signatures(limit=5))
"
```

**Saída esperada:**

```
similar http:503: 3
total runs 7d:   7
score:           0.42857142857142855
recent top-k:    [
    {'error_signature': 'http:503', 'n': 3, 'last_seen': '...'},
    {'error_signature': 'ruff:E501', 'n': 2, 'last_seen': '...'},
    {'error_signature': 'pytest:AssertionError', 'n': 2, 'last_seen': '...'},
]
```

## Evidência de tendência

`IncidentStore.recent_signatures(limit=N)` já expõe o top-N em ordem
decrescente. É exatamente o dado que o fluxo n8n consome semanalmente
pra postar no Discord (ver task #13).

Numa versão real, essa mesma consulta pode gerar um gráfico simples de
"top failures da semana" — a query já retorna o `last_seen`, o que dá
timeline suficiente pra ranking.

## Justificativa da conclusão

Não é magia estatística. O critério é:

> Se uma mesma assinatura de erro é responsável por > 40% das falhas em 7
> dias E foi vista pelo menos 2x, é evidência suficiente pra tratar como
> pattern (flake OU regressão sistêmica), não bug pontual.

Esse limiar surgiu da leitura dos runbooks (external_deps.md especifica
"3+ em 24 h" pra escalar). 0.4 sobre janela de 7 dias é mais forgiving
que a regra de 24 h — a intenção é sinalizar cedo sem alarmar tarde.

## Ver também

- Testes que provam a implementação: `tests/test_flakiness_e2e.py`
- Cobertura de assinaturas: `tests/test_memory.py::test_signature_*`
