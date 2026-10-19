---
name: ux-best-practices
description: >
  Product UX for agents that build or change interfaces, flows, copy, or
  AI/agent features. Use when designing or implementing UI, reviewing usability,
  fixing forms, empty/loading/error states, navigation, onboarding, microcopy,
  accessibility as a user task, mobile UX, or chat/agent/tool-use experiences.
  Triggers: UX, usability, heuristics, fluxo, jornada, estados vazios, formulário,
  microcopy, onboarding, IA de produto, interface de agente, "melhorar a UX",
  "revisar a interface", /ux-best-practices. Visual identity belongs to the
  product's design system or to frontend-design. Code-level interface lint
  belongs to web-design-guidelines.
---

# UX best practices

Make the person finish the job with less doubt, less recovery, and no surprise. A screen that looks finished and still hides the next step has failed.

This skill owns task design: who acts, what "done" is, the path, the states, the words, and the recovery. It does not own a new visual identity. If the repo already has components, tokens, or a design system, extend them. If the user asked for a distinctive look and no system exists, follow `frontend-design` for palette, type, and composition, then come back here for behavior. For a code audit of focus, labels, motion, and i18n, follow `web-design-guidelines` or fetch the current Vercel Web Interface Guidelines. Do not restate those implementation rules here.

Write product copy in the product's locale. The user's chat language is not automatically the UI language.

## When to apply

Apply on any of these:

- New screen, flow, component, or change to layout, labels, navigation, or feedback.
- Forms, settings, checkout, onboarding, empty states, tables, search, permissions.
- A product that chats, streams, calls tools, or acts on the user's behalf.
- "Review the UX", "why is this confusing", "make this easier".

Skip the full loop for a one-line copy tweak, a token rename, or a bugfix that does not change what the user sees or does. Still fix a broken label or a missing error if you touch that control.

## Decide before drawing

Answer these in a few lines before editing, in the reply or in a short plan the user can see. If the answers are already in the brief or the surrounding UI, reuse them. Do not interview the user for facts the screen already shows.

1. **Person and job.** Who is this for, in this moment, and what are they trying to finish?
2. **Done.** What is the smallest outcome that counts as success, and how will they know it happened?
3. **Frequency and risk.** First time or daily? Reversible or destructive, money, privacy, or other people?
4. **Primary action.** One action this view exists to support. Name it with a verb and an object.
5. **Existing pattern.** Which component, route, or platform convention already solves a sibling task? Use that unless it is the thing that is failing.

If you cannot name the job, stop and look at the route, the callers, and nearby copy. Invent a persona only when the product is greenfield and say the assumption.

Open a reference only for the gap you are in:

| You are about to… | Read |
| --- | --- |
| Judge a flow or explain a usability bug | `references/heuristics.md` |
| Add a screen, a wizard, or a state | `references/flows-and-states.md` |
| Pick a control, form, nav, dialog, or mobile behavior | `references/patterns.md` |
| Write labels, errors, empty states, or buttons | `references/writing.md` |
| Build chat, tools, autonomy, or generative output | `references/agent-ux.md` |
| Review existing UI and report findings | `references/audit.md` |

## Build loop

1. **Trace the path.** Entry, steps, success, and the way back. Count steps. Cut any step that does not change a decision or prevent an error.
2. **Design the failure modes with the happy path.** Loading, empty, error, partial, no permission, offline or stale, and success. A view with only the filled state is unfinished. See `references/flows-and-states.md`.
3. **Put the primary action where the eye lands first** on that platform: start of the reading order for dense tools, end of a form for submission, thumb zone for a phone's main action. One visual weight. Secondary actions look secondary. Destructive actions look destructive and sit away from the primary.
4. **Prefer recognition.** Show options, recent items, and examples. Recall (blank textarea, memorized syntax) is for experts who asked for it.
5. **Name things in the user's words.** The label matches the result. The same action keeps the same verb from button to toast to history.
6. **Prevent the error you can predict.** Constraints, defaults, summaries before commit, and disabled controls only with the reason beside them. A control that is disabled with no explanation is a dead end.
7. **Confirm the risky thing, not the routine thing.** Destructive, irreversible, paid, or shared-with-others gets a specific confirmation or an undo window. Saving a draft does not get a modal.
8. **Show status in the place the person is looking.** Inline error next to the field. Progress for waits over about a second. A toast may confirm; it must not be the only place a failure exists.
9. **Leave a way out.** Cancel, back, close, stop, and undo return to a known state without losing typed input.
10. **Check the floor, then the craft.** Keyboard, labels, contrast, hit targets, zoom, reduced motion, and long text. Then hierarchy, spacing rhythm, and quiet chrome. Craft that blocks the task does not count.

## Rules that override taste

- The user's requested change wins over a redesign. Do not restyle adjacent screens, invent a theme, or add a dashboard.
- One primary action per view. If two actions are truly equal, the view is probably two tasks and should say so.
- Never use placeholder text as the only label.
- Never block paste. Never disable zoom.
- Do not clear user input after a validation error.
- Do not punish the first keystroke with an error. Validate a field on blur after it has been touched, and again on submit. Server errors stay on the field they belong to.
- Keep the submit control enabled until the request starts, then show a pending state and prevent a double submit.
- Icon-only controls are for familiar, repeated tools with a visible name on focus or hover and an accessible name always. A primary action has a visible text label.
- Gesture-only actions need a click and a keyboard path, unless the gesture is the whole product (a drawing canvas) and a stated alternative exists.
- Deep-link state people will share or refresh: filters, tabs, search, pagination, open record.
- The URL and the back button must match what the screen shows.
- Honor `prefers-reduced-motion`. Offer a non-drag way to reorder or resize.
- Hit targets at least 24×24 CSS pixels, 44×44 on touch-primary surfaces.
- Text contrast at least 4.5:1, 3:1 for large text and essential graphics (WCAG 2.2 AA). Do not convey state by color alone.
- Write for a 200% zoom and a 320px-wide viewport without horizontal page scroll, clipped controls, or overlapping text.
- Long names, empty strings, one item, and hundreds of items are all normal data. Test those, not only the happy fixture.
- Loading ends. If you cannot know when, show what is blocked and a way to retry.
- Empty states teach the next action. They do not only name the void.
- Errors say what happened and what to do next, in the product's voice. No "something went wrong" as the whole message, no fake apology for a user typo.
- Destructive confirmation names the object: "Delete project Northwind", not "Are you sure?"
- Ask for permission and extra data at the moment of need, with what they get in return. No upfront permission wall for a feature they have not touched.
- Do not trap the person in an interstitial, cookie-style nag, or coach mark that covers the control it is teaching.
- Animation explains a change of state. It does not introduce every card.
- Numbers, dates, and currencies use the locale (`Intl`), including the right separators.
- Do not ship a new pattern when an existing component in the repo does the job.

## AI and agent surfaces

If the feature generates, recommends, or acts:

- Say what it can do, and the boundary, before the person relies on it.
- Separate drafts from actions that leave the building. A send, delete, pay, or publish is opted in.
- Show a plain-language plan before an action that is hard to undo, costs money, or affects other people. Give proceed, edit, and "I'll do it" .
- Stream or step status for work that takes time. Provide stop. Do not fake a precise percentage you do not have.
- Let the person correct a source, a step, or an assumption without starting over.
- Expose uncertainty when the result is a guess that could be acted on. A confident tone on a weak result is a defect.
- After an autonomous action, say what changed and why in user language, and keep undo or a time window where reversal is possible.
- When the agent is unsure, ask or offer choices. Do not invent a quiet guess on a high-stakes step.
- Label machine output as machine output when a person could mistake it for a human or for a record of fact.
- Persist a human-readable activity log for actions the system took.

Details and the six lifecycle patterns: `references/agent-ux.md`.

## Accessibility is part of done

Target WCAG 2.2 AA as the floor, plus the platform's own bar if it is stricter. Practical order:

1. Real controls (`button`, `a`, `label`, headings in order) before ARIA.
2. Every control has a name, a role, and a state a screen reader can hear.
3. Full keyboard path, visible `:focus-visible`, and focus that is not hidden behind sticky bars or dialogs.
4. Focus moves to the new context when a dialog opens and returns when it closes. On a failed submit, move focus to the first error or the error summary.
5. Live regions for async results that appear away from the focused control.
6. Captions or transcripts for meaningful audio and video.

Do not add ARIA that contradicts the native element. Do not mark decorative icons as content.

## Verify

Before calling UI work done, exercise the path the way a person does: keyboard only, empty data, a failed request, a long string, a narrow viewport, and the success message. If a browser is available, use it. A screenshot of the happy state is not verification.

When you report a UX review, use `references/audit.md`. Findings name the person-level harm, the location, and the change. Skip style nits that do not affect understanding, speed, or access.

## Do not

- Do not add onboarding carousels, sample dashboards, tooltip tours, or extra settings "for completeness".
- Do not swap a working labeled form for a chat box because the feature is "AI".
- Do not use a modal as the default container for navigation, long reading, or multi-step work.
- Do not invent marketing copy, fake testimonials, or placeholder metrics to fill a layout.
- Do not cite a heuristic number as decoration. Cite it only when it explains a finding.
