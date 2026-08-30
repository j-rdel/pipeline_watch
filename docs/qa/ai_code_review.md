# AI code review — `src/pipeline_watch/policy.py`

Cumpre §4.7: "Utilizar IA para analisar pelo menos uma alteração real do
projeto, como um diff, trecho de código ou Pull Request real, identificando
possíveis problemas ou oportunidades de melhoria."

## Setup

- **Modelo:** Ollama `qwen3:8b` (local, mesma stack do agente)
- **Prompt:** system message pedindo review estruturado em três seções
  (Strengths / Issues / Suggestions), com regra explícita de severidade
  por issue e citação de linha
- **Alvo:** `src/pipeline_watch/policy.py` (~90 linhas, adicionado no PR #22)
- **Script:** `/tmp/pw_review.py` (ad-hoc; um wrapper de 15 linhas em
  `ChatOllama` sem structured output — o objetivo era ver uma opinião
  natural do LLM, não constrainir formato)

## Saída bruta do LLM

> ### Strengths
> - **Clear separation of concerns**: The `check_patch` method logically
>   separates path validation, injection marker checks, and suspicious
>   verb checks.
> - **Regex patterns are well-documented**: The `_SUSPICIOUS_VERBS` and
>   `_INJECTION_MARKERS` regex patterns are clearly defined with comments.
> - **Immutability**: The `PolicyDecision` dataclass is frozen, ensuring
>   immutability of decisions.
>
> ### Issues
> - **Low**: Line 52: The regex for suspicious verbs includes
>   `"print(?:\s+the)?\s+token"` but the code only checks for `"print the
>   token"` (missing optional whitespace). This could miss variations like
>   `"print token"` or `"print the token"` with extra spaces.
> - **Low**: Line 47: The `_INJECTION_MARKERS` regex includes
>   `"GITHUB_TOKEN"` but the code checks for exact matches. This might
>   miss variations like `"github_token"` or `"GITHUB_TOKEN_123"`.
> - **Medium**: Line 68: The `check_patch` method returns the first
>   matching rule (e.g., injection marker) but does not aggregate all
>   violations. This could hide multiple policy violations.
> - **Low**: Line 32: The `dry_run` flag is defined in `__init__` but
>   never used in any method. This is a redundant parameter.
> - **Low**: Line 65: The `surfaces_to_scan` list includes
>   `state.get("evidence")` which may be `None`, but the code assumes
>   it's a list. This could cause a `TypeError` if `evidence` is `None`.
>
> ### Suggestions
> 1. **Enhance regex flexibility**: Update `_SUSPICIOUS_VERBS` to account
>    for variations like `"print token"` or `"print the token"` by
>    simplifying the pattern.
> 2. **Use `dry_run` for logging**: If `dry_run` is intended for testing,
>    add logic to log policy violations instead of blocking when `dry_run=True`.
> 3. **Aggregate all violations**: Modify `check_patch` to collect all
>    matching rules and return a combined reason string for clarity.

## Verificação humana + ação tomada

| Achado | Verdict | Ação |
|---|---|---|
| L52 regex — variações de "print token" | **Válido, prioridade baixa** | Não corrigido. O prompt-side já instrui o LLM a não gerar tais frases; PolicyGate é defesa em profundidade — regex tight vale a pena mas não urgente. Registrado como tech-debt. |
| L47 — `GITHUB_TOKEN` case | **Válido, baixo risco** | O regex já é `re.IGNORECASE`. Falso positivo do reviewer — a issue não procede na leitura completa. |
| L68 — first-match-wins | **Design consciente** | Rejeitado. Cita a primeira violação já basta pro operador — a lista completa vira ruído. Documentado. |
| L32 — `dry_run` nunca usado | **Válido, alta clareza** | **Corrigido neste PR** — removido do construtor. |
| L65 — `state.get("evidence")` pode ser None | **Falso positivo** | O código na verdade usa `state.get("evidence") or []`. O reviewer não parseou o `or`. |

## Aprendizado sobre o próprio processo de review

- O modelo produz achados **corretos e úteis**, mas mistura false positives
  com legítimos. **Verificação humana continua obrigatória.**
- Reviewer sem contexto de callers (todo o resto do projeto) é limitado —
  ele não sabe que o `dry_run` estava sendo pensado para uma feature futura
  que acabou movendo pra outro módulo.
- Prompt de review com **seções fixas** (Strengths/Issues/Suggestions com
  severidade) produziu saída consistente e navegável.

## Reprodução

```sh
uv run python -c "
from pathlib import Path
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

SYSTEM = '''/no_think
You are a Python code reviewer. Return markdown with three sections:
Strengths, Issues (with severity), Suggestions. Be specific.'''

f = Path('src/pipeline_watch/policy.py')
llm = ChatOllama(model='qwen3:8b', temperature=0.2)
print(llm.invoke([
    SystemMessage(content=SYSTEM),
    HumanMessage(content=f'File: {f.name}\n\n\`\`\`python\n{f.read_text()}\n\`\`\`'),
]).content)
"
```
