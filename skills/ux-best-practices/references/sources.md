# Sources and boundaries

The procedures in this skill are written for agents. They are not a copy of any vendor skill or book. When a rule and a cited work disagree in a specific product, follow the platform's current documentation and the product's design system.

## What this skill deliberately does not absorb

| Concern | Where it lives |
| --- | --- |
| Distinctive visual direction, type, palette, art direction | The product's design system, or the `frontend-design` skill (Anthropic) |
| Implementation audit: ARIA details, focus rings, `Intl`, virtualization, hydration, motion mechanics | Vercel Web Interface Guidelines, via the `web-design-guidelines` skill, fetched fresh |
| WCAG normative text | W3C WCAG 2.2. This skill treats AA as the floor and names the checks an agent must perform. |
| Research planning, interview guides, usability-test scripts | Out of scope unless the user asks for a study plan. Do not fake research findings. |

## Works the rules are compressed from

- Jakob Nielsen, "10 Usability Heuristics for User Interface Design", Nielsen Norman Group. Severity scale follows the NN/g 0–4 ratings used in heuristic evaluation.
- Jakob Nielsen, response-time limits (0.1s / 1s / 10s), Nielsen Norman Group.
- Don Norman, *The Design of Everyday Things*: affordance, signifier, mapping, constraint, feedback, and the gulfs of execution and evaluation.
- Steve Krug, *Don't Make Me Think*: scanning, obvious clickability, cutting needless words.
- W3C, Web Content Accessibility Guidelines 2.2, level AA. Includes focus not obscured, target size minimum (24×24 CSS px), dragging movements, redundant entry, and accessible authentication.
- Apple Human Interface Guidelines and Material Design: follow them when shipping on those platforms; do not import mobile patterns into desktop without a reason.
- Saleema Amershi et al., "Guidelines for Human-AI Interaction", CHI 2019: make capabilities and limits clear, support invocation, dismissal, correction, and explanation, scope the action when uncertain, remember recent context, adapt cautiously, show consequences, provide global controls.
- Google PAIR guidebook: set expectations, explain, accept feedback, fail gracefully, keep the person in control.
- Victor Yocco, "Designing For Agentic AI: Practical UX Patterns For Control, Consent, And Accountability", *Smashing Magazine*, February 2026: intent preview, autonomy level, rationale, confidence, audit and undo, escalation.
- Vercel Web Interface Guidelines (living document): implementation companion, not duplicated here.
- Anthropic `frontend-design` and community packs such as `ui-ux-pro-max`, hueyexe `frontend-agent-skills`, and Vercel `web-design-guidelines`: neighboring skills. Prefer those for their narrower job instead of expanding this one.

## Maintenance

If a heuristic or a pattern in this folder starts contradicting a newer platform rule, fix the single file that owns it. Do not restate the same rule in `SKILL.md` and a reference. `SKILL.md` keeps only the rules that must hold even when no reference was opened.
