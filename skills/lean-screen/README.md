# lean-screen

Layout skill for coding agents. One area on the page, the rest in a persistent sidebar. Composition carries the personality, not a display font.

Skill de layout para agentes de código. A página faz um trabalho. As outras áreas ficam numa barra lateral persistente. Métrica, histórico e ferramenta secundária ganham um lugar com nome. A linha é o objeto e a ação, não uma coluna por propriedade. Fonte de destaque e paleta nova não entram para parecer refinado.

Não escolhe a direção visual. Isso fica no design system do projeto, ou numa skill de direção visual. Fluxo, formulário e acessibilidade ficam na `ux-best-practices`.

## Instalar

```bash
npx skills add internetdozero/lean-screen
```

Funciona em agentes que leem o formato Agent Skills (Grok, Codex, Claude Code, Cursor, Antigravity e outros suportados pelo CLI).

Entra sozinha em tela, dashboard, lista, cards, métricas e layout. `/lean-screen` força a leitura. Use junto com `ux-best-practices` quando a tarefa também for de fluxo.

## O que tem dentro

| Arquivo | Uso |
| --- | --- |
| `SKILL.md` | Casca do produto, o que fica na página, o que sai, e o que não imitar |
| `references/tells.md` | Lista do que cortar ou mover antes de dar a tela por pronta |

Licença MIT.
