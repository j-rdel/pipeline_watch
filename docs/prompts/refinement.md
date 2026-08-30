# Ciclo de refinamento

Cumpre §4.11 do desafio + §Análise crítica do README:
> Documentar pelo menos um ciclo de refinamento de prompt ou comportamento
> do agente, apresentando o problema observado, a alteração realizada e o
> resultado obtido.

## Refinamento aplicado: fallback resiliente para `propose_patch`

### 1. Problema observado

Ao rodar o CLI pela primeira vez com Ollama real na fixture `lint-fixture`:

```
uv run pipeline_watch triage --run-id lint-fixture
```

O flow **quebrou** no nó `propose_patch` com:

```
ResponseError: {
  'code': 400,
  'message': 'Failed to initialize samplers: failed to parse grammar',
  'type': 'invalid_request_error'
} (status code: -1)
[NOTE] During task with name 'propose_patch' and id '...'
```

### 2. Diagnóstico

O `ChatOllama.with_structured_output(ProposedPatch)` alimenta o schema
Pydantic à engine de grammar do Ollama. Nossa `ProposedPatch` original
tinha `Field(max_length=4000)` no campo `diff`. **A grammar do Ollama
rejeita esse constraint em runtime** (não em compile time da app —
descobrimos só em produção).

Os outros dois nós LLM (`classify_failure`, `synthesize_diagnosis`) não
foram afetados porque seus `max_length` estão em campos menores (≤ 600
chars) que a grammar tolera.

### 3. Alteração aplicada

Duas mudanças, em ordem:

**(a)** Wrapper `llm.py::structured_output` deixou de tentar
`method="function_calling"` (que também falhava — o modelo não invocava
a tool) e voltou ao default `json_schema`:

```python
# src/pipeline_watch/llm.py
def structured_output[T: BaseModel](schema, *, system, user):
    """
    ...
    Ollama's json-schema grammar path can reject certain schemas at compile
    time (`ResponseError: failed to parse grammar`). Callers should either
    keep their schema simple or wrap this call in try/except and treat the
    failure as "no result" — see `nodes/propose_patch.py` for the pattern.
    """
    structured = _get_llm().with_structured_output(schema)
    ...
```

**(b)** O nó `propose_patch` foi envolvido em try/except que devolve
`{"proposed_patch": None}` em caso de falha:

```python
# src/pipeline_watch/nodes/propose_patch.py
def propose_patch(state: TriageState) -> dict:
    try:
        patch = llm_mod.structured_output(ProposedPatch, ...)
    except Exception:
        # LLM failed to produce a valid patch — that's fine, autofix is
        # opportunistic. Downstream open_pr handles None by skipping.
        return {"proposed_patch": None}
    ...
```

### 4. Resultado obtido

- **Antes:** flow inteiro quebrava numa exception não tratada. Nenhum
  IncidentReport produzido, execução perdida.
- **Depois:** flow completa. `proposed_patch=None` é gravado no state.
  PolicyGate detecta patch faltando → downgrada `decision` pra
  `notify_only` → mensagem vai pro Discord com hipótese completa +
  suggestion "aplicar ruff format manualmente".

Verificado no run do dia 2026-08-30, cenário `lint-fixture`:

```json
{
  "classification": {"label": "lint", "confidence": 0.9},
  "root_cause_hypothesis": "...cita E501 e F401 do log real...",
  "suggested_action": "Generate a PR with `ruff format`...",
  "proposed_patch": null,
  "human_approval_required": false,
  "correlation_id": "run-lint-fixture-b0c9a05b"
}
```

E no cenário adversarial (mesma falha do Ollama grammar + prompt
injection), o mesmo padrão salvou o dia:
- `proposed_patch=null` (falha do Ollama, capturada)
- PolicyGate viu `None` → `decision=notify_only`
- **Nenhum PR aberto, nenhum vazamento de secret** (ver
  [`docs/evidencias/adversarial_run_ollama.md`](../evidencias/adversarial_run_ollama.md)).

### 5. Lições

- **Grammar do Ollama tem constraints não-documentados.** `max_length`
  em strings longas é um deles. Testar com schema real antes de assumir
  compatibilidade.
- **`try/except` em nós LLM não é code smell — é resiliência.** LLM
  pode falhar por 20 razões (timeout, grammar, JSON malformado). Um
  nó opcional falhar não deve quebrar o grafo inteiro.
- **PolicyGate absorve o downgrade sem lógica extra.** A regra "sem
  patch → sem autofix" já existia; a falha do LLM aciona ela
  naturalmente.

### 6. Trabalho futuro (não urgente)

- Reduzir `ProposedPatch.diff.max_length` de 4000 pra 2000 e testar se
  a grammar aceita.
- Ou: dividir `ProposedPatch` em `_ProposedPatchLLM` (sem constraints,
  usado no LLM call) + `ProposedPatch` (com constraints, usado no
  contrato externo do IncidentReport). Conversão explícita entre eles.
