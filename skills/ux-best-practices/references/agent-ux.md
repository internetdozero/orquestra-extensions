# Agent and AI UX

Use this when the product generates, recommends, chats, calls tools, or acts without a click on every step. Classic heuristics still apply. This file adds the failure modes those heuristics do not name: autonomy, uncertainty, and side effects that happen off-screen.

Compressed from public guidance, not a reprint: Amershi et al., *Guidelines for Human-AI Interaction* (CHI 2019); Google PAIR's people-plus-AI themes (expectations, feedback, errors, control); Nielsen's heuristics applied to probabilistic output; Victor Yocco's six agentic lifecycle patterns (*Smashing Magazine*, February 2026). Implement the behavior. Do not quote the articles in the UI.

## Choose the surface

| Person needs | Surface |
| --- | --- |
| A known structured input (date, amount, file, choice) | Form or control. Not a chat. |
| To find or transform an object that is on screen | Action on that object, with a result they can edit. |
| An open-ended draft or exploration | Composer, with examples and a way to attach context. |
| To supervise ongoing work | A plan, a status, and a log. Chat may be the entry, not the only record. |

Do not hide a form behind a prompt. Do not hide a side effect behind a paragraph of generated prose.

## Expectations

Before the person depends on the system, the UI can answer:

- What it is for, in task language.
- What it will not do, especially if people will assume it does (legal, medical, sending, deleting).
- What it can see (this document, the account, the web) when that scope changes the result or the privacy story.

Place the boundary at the entry to the feature, not in a docs site. Repeat it contextually when a request crosses the boundary.

Invocation is obvious and voluntary. Dismissal is obvious: stop generating, close the panel, and return to the unchanged object. A feature that cannot be dismissed will be disabled at the account level.

## Six patterns for anything that acts

Use the lightest set that matches the risk. A spellcheck underline is not this lifecycle. Sending mail, paying, deleting, and changing permissions are.

### 1. Intent preview

Before a hard-to-undo, paid, or outward action, show the plan in user language: steps, objects, and who is affected. Offer three responses when they make sense: proceed, edit, and do it myself.

The plan is a decision point, not a notification. "Executing delete_user(id=42)" fails. "Remove Ada's access to Northwind" passes.

Skip the preview for actions the person just invoked directly and can see, like "shorten this paragraph" on selected text, when the result stays local and undo exists.

### 2. Autonomy level

When tasks vary in risk, let the person set how far the system goes, per task type if risks differ:

| Level | Behavior |
| --- | --- |
| Suggest | Surface the opportunity. Do not draft a plan unless asked. |
| Propose | Draft a plan. Wait. |
| Confirm | Prepare the action. One explicit commit. |
| Act, then notify | Only for a class the person pre-approved. Tell them what happened. |

Default to Propose or Confirm. Move to Act only for a narrow, named, reversible class. Remember the setting and do not silently widen it because the model is confident.

### 3. Rationale

After an action the person did not click step-by-step, say why in one or two lines tied to a rule they set or a fact they can check. "Rebooked you on the 14:30 nonstop because you allowed same-day nonstop rebooking." Internal chain-of-thought dumps are not a rationale.

### 4. Confidence

When a wrong answer is costly, show uncertainty in words or a small set of levels the person can learn (ready to send / needs review / not enough information). Do not show a fake precise probability. Do not use color alone.

High confidence still leaves the commit to the person when the action is outward. Low confidence asks a question or presents options. It does not ship the guess.

### 5. Audit and undo

Keep a human-readable log of what the system did, to what, and when. Each reversible entry has undo. If undo expires, say the window before they rely on it ("Undo for 15 minutes"). If it cannot be undone, the preview said that.

A reversion rate that climbs on one task type means stop automating that type, not a louder confirmation.

### 6. Escalation

On ambiguity, ask a specific question or offer a short list of real options. "Next Tuesday, 30 Sep or 7 Oct?" beats a confident booking on the wrong day.

Provide a path to a human or to fully manual handling for high-stakes and for repeated failure. The system should prefer a question over a quiet guess when several actions are plausible and the cost of being wrong is high.

## Generating

- The composer states what context will be sent ("Includes the open document").
- Examples are real for this product, short, and tappable if they fill the composer.
- Streaming shows that work is in progress and keeps already-produced text. Stop cancels the rest and leaves the partial result editable or clearly discarded, by an explicit choice if both are plausible.
- The person can edit the result in place. Copy is secondary.
- Regeneration is an action with a meaning (try again, shorter, formal). A single "regenerate" that silently changes tone is a slot machine.
- Put the result in the artifact they were working on when there is one (the email body, the issue). A transcript buried in a side panel is easy to lose.
- Citations and sources, when the product has them, are next to the claim and open the source. Do not fabricate a source list. If grounding failed, say the answer is ungrounded.
- Distinguish generated content from records. A summary is labeled a summary. A quote is a quote. An action that was taken is in the log, not only implied by prose.

## Corrections

- Let them edit an assumption ("use the 2024 prices") without retyping the whole prompt when the product has structure.
- Corrections should stick for the session when they said "always" or "never", and the UI should show that it stuck.
- Learn slowly. Do not change a global preference from one reaction. Confirm before a lasting change to voice, recipients, or autonomy.
- Granular feedback (this result is wrong because…) beats a lone thumbs up when you have a place to use it. Do not ask for a rating after every message.

## Errors and repair

When the system did the wrong thing:

1. Say what it did, specifically.
2. Say what it already reversed, or how the person reverses it.
3. Offer a next step, including a human when the product has one.

"I emailed the wrong client. I sent a follow-up retracting it. Here is the thread." beats "An error occurred."

When the system cannot do the task, say so early. Partial work that looks complete is worse than a clear stop.

## Harmful agent habits

These are defects. Do not ship them.

- Acting outwardly during a "draft" interaction.
- A plan that omits a side effect (an email to a third person, a charge, a permission change).
- Confidence theater: badges, "100%", or cheerful tone with no basis.
- Hidden tool calls that change data while the transcript says it is thinking.
- Forcing a chat to recover from a form error the form could have shown.
- Memory or personalization that cannot be seen or deleted.
- Nudges that raise autonomy after a single success.
- Blocking the underlying product until the person tries the AI feature.
- Synthetic people, reviews, or logs presented as real.

## Status, time, and cost

- If an action spends money, quota, or irreversible attention (a push notification, a customer email), show the cost before commit.
- Long jobs: steps in language ("Checking invoices", "Writing the summary"), not a fake percent. On failure, say which step failed and what was not done.
- Background completion notifies in a way the person can find later. A toast alone is not a record.
- If the model or tool fell back, and the fallback changes quality or privacy, say so.

## Accessibility of conversational UI

- New messages announce politely. Do not steal focus from the composer on every token.
- Stop, send, and retry are real buttons.
- The transcript is readable by a screen reader in order, including who spoke.
- Streaming respects reduced motion.
- Suggested replies are buttons with names, not a string the person must retype, unless the point is to edit the text.

## What not to add

A temperature slider, a system-prompt editor, and a model picker are expert tools. They do not belong in a default path for a person who came to finish a task. Expose them only when the user asked for control at that level.
