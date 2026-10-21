# Orchestration Templates & Dispatch Reference

Reference templates for the Orchestrator agent to generate concise dispatches for the Builder AI.

## 1. Compact Builder Dispatch Prompt (English)

Copy-pasteable Markdown block to dispatch to the Builder AI:

```markdown
### Mission: <Clear imperative task title>
- **Workspace:** `<path/to/project>`
- **Targets:**
  - `<file1>`: <role or edit goal>
  - `<file2>`: <contracts to preserve>

#### Requirements & Scope
- <Requirement 1: concrete behavior / change>
- <Requirement 2: edge cases / error handling>

#### Idea Vault Lifecycle
- **Idea ID:** `#<ID>`
- **Kickoff:** `update_idea_status(idea_id=<ID>, status="in_progress")`
- **Completion:** `update_idea_status(idea_id=<ID>, status="completed")`

#### Verification
Before finishing, run and report:
1. `<test command>` (e.g. `rtk npm test` or `rtk cargo test`)
2. `<typecheck/lint command>` (e.g. `rtk cargo check`)
```

---

## 2. User Explanation Protocol (Portuguese)

Brief strategy summary for the operator (**senhor**):

```markdown
Entendi o escopo, senhor!

### 📋 Resumo da Estratégia:
- **Alvo:** <O que será feito em poucas palavras>
- **Arquivos:** `<caminho/do/arquivo>`
- **Validação:** <Testes/checks a executar>
- **Idea Vault:** `#<ID>`

Prompt estruturado abaixo pronto para despacho à Builder AI.
```

---

## 3. Post-Build Audit Checklist

When Builder concludes:
1. **Diff:** Check `rtk git diff` / `rtk git status` for scope compliance.
2. **Checks:** Verify test output provided by Builder passes without regression.
3. **Idea Vault:** Verify status is `completed`.
4. **Report:** Concise summary to operator (**senhor**).
