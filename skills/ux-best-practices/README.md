# ux-best-practices

UX skill for coding agents. Cut the flow down to the smallest action that finishes the job.

Skill de UX para agentes de código. O padrão é a menor ação que termina a tarefa. Um segundo passo, um modal ou um campo só entra se, sem ele, a pessoa errar ou não conseguir concluir. Confirmação fica para o que é destrutivo, pago ou visível para outra pessoa.

Não escolhe paleta nem fonte. Direção visual fica no design system do projeto, ou numa skill de direção visual. Não substitui uma auditoria de código de acessibilidade (foco, ARIA, `Intl`).

## Instalar

```bash
npx skills add internetdozero/ux-best-practices
```

Funciona em agentes que leem o formato Agent Skills (Grok, Codex, Claude Code, Cursor, Antigravity e outros suportados pelo CLI).

A skill também entra sozinha quando o pedido fala de UX, usabilidade, formulário, estado vazio, microcopy, fluxo ou interface de agente. `/ux-best-practices` força a leitura.

## O que tem dentro

| Arquivo | Uso |
| --- | --- |
| `SKILL.md` | Regras que valem em toda mudança de interface |
| `references/heuristics.md` | Heurísticas e gravidade do problema |
| `references/flows-and-states.md` | Caminho, passos e estados |
| `references/patterns.md` | Controles, formulário, navegação, mobile |
| `references/writing.md` | Botão, erro, vazio, tom |
| `references/agent-ux.md` | Chat, ferramenta, autonomia e desfazer |
| `references/audit.md` | Como reportar uma revisão |
| `references/sources.md` | De onde as regras vieram, e o que esta skill não absorve |

Licença MIT.
