# Heuristics

Use this to find why a flow fails and to check a design before shipping. Each heuristic has a test. A pass is behavior, not a slogan.

Sources, compressed for agents: Nielsen's 10 usability heuristics (NN/g); Norman's gulfs of execution and evaluation, affordances, signifiers, mapping, constraints, and feedback; Krug's "don't make me think" (scan, obvious choices, omit needless words). Wording here is operational, not a quotation of those texts.

Severity when you file a finding:

| Level | Meaning |
| --- | --- |
| 0 | Not a usability problem. Drop it. |
| 1 | Cosmetic. Fix only if you are already in the file. |
| 2 | Minor. Person recovers, but slows down or hesitates. |
| 3 | Major. Person takes a wrong path, loses work, or needs help. |
| 4 | Catastrophe. Blocks the job, destroys data, or excludes a group. |

## 1. Visibility of system status

The person can tell what the system is doing, what it did, and what mode they are in, within about a second of the change.

Fail: a save with no confirmation; a selected tab that looks like the others; a spinner with no name; a background job that finishes silently; a multi-step flow with no sense of position.

Pass: the control that was used shows the result next to it; mode (edit, view, offline, recording) is visible without hovering; long work shows status and a way to stop.

## 2. Match between system and the world

Labels, order, and metaphors come from the person's task language, not the schema, the team, or the model.

Fail: "Submit", "OK", "entity", internal IDs as the only name, a calendar week that starts on a day this locale does not use, icons whose metaphor only the author knows.

Pass: the button says the outcome ("Publish article"); the field order matches the paper form or the real sequence; icons are paired with words until the symbol is standard (play, close, search).

## 3. User control and freedom

Every path has an exit. Mistakes are reversible, or the irreversibility is told before the action.

Fail: no cancel on a dialog; back destroys a long form; a send that cannot be undone and was not previewed; a full-screen takeover with no close; a wizard that cannot return to step 1 with data intact.

Pass: cancel, back, and close are present and consistent; undo for destructive edits in the session; typed text survives validation errors and accidental navigation when the product can keep it.

## 4. Consistency and standards

The same word, the same place, and the same gesture mean the same thing across the product and the platform.

Fail: "Delete" on one screen and "Remove" on the next for the same verb; primary button on the left in one dialog and the right in another; a custom scroll or a custom checkbox that breaks platform behavior; Cmd/Ctrl-click on a "link" that is a `div`.

Pass: one verb glossary; platform conventions for links, menus, and shortcuts; a new pattern introduced once and documented by use, not by a tour.

Within the product, internal consistency beats a clever local variation. Platform convention beats internal invention when people bring habits from the OS.

## 5. Error prevention

The design makes the wrong action hard before it needs a good error message.

Fail: two adjacent buttons of equal weight, one of which deletes; a date field that accepts 31 February and fails on the server; a blank required select; sharing defaults to public; leaving a page silently drops a draft.

Pass: constraints (masks, min, max, disabled illegal dates), a summary before commit, safer defaults, confirmation only for the dangerous case, autosave or an explicit dirty-state warning.

## 6. Recognition rather than recall

Options, formats, and context stay on screen. The person should not have to remember a code, a position, or the contents of a previous step.

Fail: a command palette as the only way to reach a daily task; "see the email we sent" with no resend and no hint; multi-step checkout that hides what is being bought; an empty prompt with no examples for a novice tool.

Pass: visible labels, recently used items, example values near the field, a review step that repeats the choices, search that shows the query alongside results.

## 7. Flexibility and efficiency

Novices get a visible path. Frequent users get shortcuts that do not become the only path.

Fail: seven clicks for a daily task; shortcuts that are undiscoverable and also required; expert-only settings dumped into the first-run form; accelerators that break keyboard access.

Pass: a short default path; bulk actions once multi-select exists; shortcuts hinted on the control; sensible defaults so the common case is one confirmation, not ten fields.

Do not add a shortcut, a toolbar, and a wizard for the same action in the first version. Ship the visible path. Add the accelerator when the repeated cost is real.

## 8. Aesthetic and minimalist design

Every element earns its place by helping this task. Visual noise is a comprehension bug.

Fail: a marketing hero inside a settings task; two explanations of the same field; icon plus color plus badge plus tooltip plus caption all saying "new"; equal emphasis on every card so nothing is first.

Pass: one heading that states the task; helper text only where the label is not enough; decoration removed when it competes with the action. Hierarchy is obvious at arm's length: squint and the primary action should still be the heaviest thing.

Minimal does not mean sparse to the point of mystery. A dense tool for experts can be right if the density is information, not chrome.

## 9. Recognize, diagnose, and recover from errors

The message names the problem in plain language, says where it is, and gives a fix. The work product is still there.

Fail: "Something went wrong", "Invalid input", a red border with no text, an error only in a toast that disappears, a stack trace as the UI, a form that wipes itself.

Pass: "That email is missing an @. Example: ada@studio.com" next to the field; a page-level error summary that links to fields when there are several; a failed save that keeps the draft and offers Retry.

Tone: calm, specific, no blame, no joke in a blocking error. Do not apologize for the person's typo. Do apologize, plainly, when the system lost their work or did the wrong thing.

## 10. Help and documentation

The interface should not need a manual. When a task is genuinely complex, help sits at the decision, is searchable, and lists steps.

Fail: a 6-slide coach mark before first use; a tooltip that repeats the label; help that opens a PDF; a placeholder that disappears when the person starts typing and takes the only instructions with it.

Pass: one sentence at the field that needs it; a persistent "how billing works" link next to the billing control; empty states that include the first action.

## Norman checks

Use these when a control is "there" but people still miss it or misuse it.

| Check | Question | Fail signal |
| --- | --- | --- |
| Affordance | Does the thing look operable? | A clickable card with no hover, no pointer, and no button. |
| Signifier | Is the operation pointed at, not just possible? | A secret swipe with no on-screen hint and no menu equivalent. |
| Mapping | Does the control layout match the result layout? | A row of toggles whose order does not match the list they change. |
| Constraint | Are illegal actions hard to take? | Free text for a value that has five legal options. |
| Feedback | Did the gulf of evaluation close? | The person must look somewhere else, or wait, to learn whether it worked. |
| Conceptual model | Can they predict the next state? | "Sync" that sometimes merges, sometimes overwrites, with no description. |

## Krug checks

- Can a person who is scanning, not reading, name the page and the next action in a few seconds?
- Are clickable things obviously clickable, and non-clickable things not?
- Did you remove words that do not help the person choose or act? Half the copy is a common result, then cut again only if meaning stays.
- Is the choice self-evident? If not, is it at least self-explanatory without a manual?

If you need a paragraph above a control to explain it, change the control or the label before adding the paragraph.

## How to apply

Walk the primary task once with the heuristics in order. Stop at the first severity 3 or 4 and fix that before polishing severity 1. Do not produce a score. Produce the fix.
