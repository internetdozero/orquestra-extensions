# Auditing UX

Use this when the user asks for a review, or as the last pass before you call a UI change done. Findings are repairs, not a score.

## Scope

Review the surfaces the change touched, plus the shared states those surfaces write: the list and the detail, the create form and the empty state, the happy path and the error. Do not audit the whole product unless asked.

If `web-design-guidelines` is available, run that for implementation rules (focus, labels, motion, i18n, virtualization) and do not duplicate its hits here. This audit is the person-level layer: task, hierarchy, states, copy, recovery, and agent behavior.

## Method

1. Name the primary job of the view in one sentence.
2. Walk it as a novice with only what is on screen. Note every moment of "what do I do?" or "what just happened?".
3. Walk it again for empty, error, long text, keyboard only, and narrow width.
4. If the feature acts on the user's behalf, check `agent-ux.md` for preview, undo, and uncertainty.
5. Assign severity from `heuristics.md`. Drop severity 0. Mention severity 1 only if the list is short.

## Output

Lead with whether the person can finish the job. Then findings, highest severity first. No preamble about the importance of UX.

```
Job: <one sentence>
Verdict: <blocked | finishes with friction | finishes cleanly>

<file:line> — S<n> — <what the person hits>. <change>.
```

Example:

```
Job: Invite a teammate and show them on the members list.
Verdict: finishes with friction

src/invite.tsx:40 — S3 — Submit stays disabled until the email is valid, with no message, so the empty field looks frozen. Validate on submit and focus the field error.
src/members.tsx:18 — S2 — A successful invite only toasts, and the list does not update. Add the person to the list and say "Invite sent to ada@studio.com."
src/invite.tsx:12 — S2 — Placeholder "Enter value" is the only label. Use "Email" and keep the example as helper text.
```

Rules for a finding:

- Location is a file and line when you have them, otherwise the view and the control name.
- Harm is what the person does wrong or cannot do.
- The change is a single concrete repair. If two repairs are plausible, pick the smaller one that removes the harm and say the assumption.
- Do not file "consider adding animations", "could use more color", or "add a tour" unless the missing motion or color causes a missed state change.

Group by surface only when there are many hits. A clean surface can be omitted. Do not write "pass" lines to pad the report.

## Before and after a fix

If you changed the UI, say what you verified: keyboard path, empty, error, narrow viewport, and, for agent actions, cancel and undo. Say what you could not run.

## Heuristic sweep, only if you need a checklist

Do not print this list filled with "pass". Use it privately, then emit only failures.

- Status of the last action is visible.
- Labels match the task, not the schema.
- Back, cancel, or undo exists where work can be lost.
- The same action has the same name as elsewhere in the product.
- The likely mistake is constrained or confirmed.
- Options are on screen; the person does not memorize the last step.
- A daily task is short; shortcuts are optional.
- One primary action; everything else is quieter.
- Errors name the fix and keep the input.
- Help, if any, is at the decision and is short.
- Loading, empty, error, and success exist and are distinct.
- Keyboard, focus, names, contrast, and zoom hold up.
- If AI acts: plan before side effects, log after, undo or an honest expiry, no fake certainty.
