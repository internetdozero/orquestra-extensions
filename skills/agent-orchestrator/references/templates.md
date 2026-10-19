# Orchestration Templates & Dispatch Reference

Reference templates for the Orchestrator agent to generate structured dispatches for the Builder AI and verify results.

## 1. Builder Dispatch Prompt Template (English)

Copy-pasteable Markdown block to dispatch to the Builder AI:

```markdown
### Mission: <Clear, imperative task title>

#### 1. Context & Architecture
- **Objective:** <1-2 sentences on what needs to be accomplished and why>
- **Active Workspace:** `<path/to/project>`
- **Key Files & Entry Points:**
  - `<path/to/file1>`: <brief description of role or modification target>
  - `<path/to/file2>`: <relevant types or contracts to preserve>

#### 2. Detailed Scope & Requirements
- <Bullet point 1: exact functional requirement>
- <Bullet point 2: edge case or specific handling required>
- <Bullet point 3: data flow or state mutation expectations>

#### 3. Idea Vault Task Lifecycle (Mandatory when idea-vault MCP is present)
- **Idea ID:** `<ID>` (e.g., `#245`)
- **On Start:** Transition status to in-progress: `update_idea_status(idea_id=<ID>, status="in_progress")`.
- **On Completion:** Transition status to completed: `update_idea_status(idea_id=<ID>, status="completed")` after all verification checks pass.

#### 4. Engineering Guardrails (Strict)
- **Anti-Monolith Rule:** Keep all modified or newly created files strictly under 300–400 lines. Decompose into submodules/components if growing beyond this limit.
- **Surgical Patch:** Do not refactor unrelated modules, change public API signatures, or modify unrequested configuration keys.
- **Token Efficiency:** Prefix CLI commands with `rtk` (e.g., `rtk npm test`, `rtk cargo check`, `rtk git status`) to minimize context bloat.
- **No Direct `/tmp` Abuse:** If scratch files are needed, use `/var/tmp/testing/` or repository-designated test folders. Never write to memory-backed `/tmp/`.

#### 4. Verification & Acceptance Criteria
Before concluding, you MUST execute the following verification steps and report their exact outcomes:
1. `<typecheck command>` (e.g., `rtk npm run typecheck` or `rtk cargo check`)
2. `<test command>` (e.g., `rtk npm test` or `rtk cargo test`)
3. `<build/lint command>` (e.g., `rtk npm run build --no-bundle`)
Confirm that zero errors and zero regressions were introduced.
```

---

## 2. User Explanation Protocol (Portuguese)

Before or alongside providing the dispatch prompt, provide a concise explanation to the user in Portuguese:

```markdown
Entendi o escopo, senhor!

### 📋 Resumo da Estratégia:
- **Alvo:** <O que será feito em poucas palavras>
- **Arquivos impactados:** `<caminho/do/arquivo1>`, `<caminho/do/arquivo2>`
- **Validação planejada:** <Quais testes ou checks serão exigidos da Builder>

Abaixo está o prompt pronto em inglês para disparar para a IA Builder.
```

---

## 3. Post-Build Audit Checklist

When the Builder agent finishes, the Orchestrator verifies the implementation:

1. **Diff Inspection:** Inspect `git diff` or status. Verify only targeted files were modified.
2. **Contract Preservation:** Check that public API signatures, interfaces, and exported functions maintain backward compatibility.
3. **Line Cap Compliance:** Confirm no single file ballooned past 300–400 lines.
4. **Validation Evidence:** Verify that the Builder provided real test/build execution logs showing success.
5. **Final User Report:** Present an executive summary to the user highlighting what was done and what checks passed.
