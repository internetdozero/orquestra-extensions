# Flows and states

Design the path and the states before the pixels. A component with no state model will grow a spinner and an empty `div` later, in the wrong place.

## Flow

Write the path as steps a person takes, not as components.

```
Entry → Decision or input → Commit → Result
                ↘ leave without damage
                ↘ fail → recover → Commit
```

For each step record: what they see, what they do, what changes, how they go back, and what is lost if they leave.

Cut a step when it does not change a decision or prevent an error. Account creation before the person has seen the value, a "welcome" interstitial, and a review step that only repeats one field are the usual cuts. Keep a review step when the commit is paid, shared, destructive, or hard to inspect afterward.

### Entry

- Deep links land on the object, not on a homepage that asks them to search for it again.
- Interrupted work resumes at the draft, not at step 1 with blank fields.
- A person who lacks permission sees who can grant it or what to do, not a blank page and not a stack trace.

### Progressive commitment

Ask for the minimum that unlocks the next real step. More data comes when the person asks for the feature that needs it. Order questions from easy and motivating to hard and sensitive. Do not lead with a tax ID.

### Multi-step flows

Use more than one screen only when a single screen is too long to review, the steps have different mental models, or later steps depend on earlier answers.

- Show progress as named steps when the count is stable. A percentage bar that lies is worse than "Step 2 of 4 · Payment".
- Back does not wipe answers.
- Let them jump back to a finished step if order allows.
- The last step is a confirmation of choices plus the commit verb, not a surprise fee or a new required field.

### After success

Say what happened in the same verb as the button. Put the new object in reach (open it, copy the link, return to the list). Do not dump the person on a marketing page. Do not auto-redirect so fast they cannot read the result.

## State matrix

Every view that depends on data or a request has these states. Sketch the ones that differ. Implement the ones that can happen.

| State | What the person needs | Usual failure |
| --- | --- | --- |
| Initial / loading | To know the product heard them and what is blocked. If the wait is under ~1s, do not flash a skeleton. Over ~1s, show a calm pending state in the region that will fill. Over ~10s, show progress or a step list and a cancel. | A blank page, a full-screen spinner that hides the chrome, a skeleton that never resolves. |
| Ideal | The primary action and the information required to take it. | Everything at equal weight. |
| Empty, first use | What this area is for, in one sentence, and the action that creates the first object. | An illustration and "No items yet" with no button. |
| Empty, filtered | "No matches" plus the active filters and a clear reset. Different from first use. | A first-use illustration when the list is empty because of a filter. |
| Partial | Usable content plus a visible gap (one widget failed, sync behind). | Failing the whole page because one card failed. |
| Error, user can fix | Inline, specific, input preserved, focus on the issue. | Toast only, or a red border. |
| Error, system | What failed, that their input is safe, and Retry. Offer a way out if retry will not help. | "Try again later" with no retry and no saved draft. |
| No permission | What is locked and how to get access, without leaking private data. | A disabled button with no reason, or a 403 string. |
| Offline / stale | What is old, what still works, and when it last succeeded. | Silent failure, or a banner that covers the work. |
| Success | The outcome, next to the action or in the resulting view. | A toast that vanishes before it can be read, and no change on the object. |
| Destructive pending | The object named, the consequence, and Undo or an explicit arming step. | Immediate delete on a mis-click. |
| Busy / double submit | The control shows pending and ignores repeat activation. | Two charges, two records. |

If two states look the same, they are one state. Do not design a unique illustration for each.

## Loading

- Prefer holding the layout still (reserved space, inline pending) over replacing the page.
- Skeletons mimic the layout that will arrive. A generic pulsing block for a form is noise.
- Do not show a skeleton and a spinner and a "please wait" line together.
- Optimistic UI is allowed when the action usually works, the rollback is automatic and visible, and a conflict cannot silently overwrite someone else. Payments, permissions, and deletes are poor optimistic candidates.
- Never invent progress percents. "Uploading Northwind.csv…" is honest. "67%" is a lie unless you have bytes.

Response-time guidance (Nielsen): ~0.1s feels instantaneous; ~1s needs no special feedback beyond the result; ~10s needs a progress indication and a way to abandon. These are ceilings for the feeling, not timers to code against.

## Empty

Structure:

1. What this place is, if the title did not already say it.
2. Why it is empty, if it is not obvious (filter, permission, first run).
3. The single next action, as a real button or link.

Skip the mascot unless the product already has one and it does not push the action below the fold.

## Errors

Place the message at the cause.

- Field error: under that field, tied with `aria-describedby` or equivalent, color plus text plus icon if color would be the only signal.
- Several fields: a summary at the top of the form that links down, plus the inline messages. Move focus to the summary or the first invalid field on submit.
- Page or network: replace the region that failed, keep the surrounding navigation.
- Toast: confirmation and low-stakes async events only. Toasts disappear, so they cannot be the only record of a failure.

Preserve input. Offer a fix that is a control ("Use a file under 10 MB"), not a lecture.

## Zero, one, and many

- Zero is the empty state above.
- One item should not look like a broken grid (a single card floating in a 3-column layout with two ghosts).
- Many needs sort, scan structure, and a way to act without pixel-hunting. Virtualize long lists. Sticky headers and bulk actions appear when they save a repeated task, not by default on five rows.

## Time and concurrency

- Show time zones when the person, the data, and the viewer can disagree. Store absolute instants; display in the viewer's zone unless the thing is a venue time.
- If two people can edit, say who has it or merge visibly. Last-write-wins with no warning is data loss.
- Stale tabs: if the record changed under them, block the save and show the new state rather than overwriting.

## Permissions and destructive scope

Say the scope in the control: "Delete 3 files", "Anyone with the link can edit". Default to the least exposure that still lets the task finish. Changing to a wider audience is an explicit act with the new audience written out before confirm.

## Maps of common flows

Use these shapes unless the domain has a stronger convention.

**Create.** List or parent → new (blank or template) → edit with autosave or explicit save → return to the object. Cancel asks only if there is unsaved input.

**Edit.** The object in view → edit in place for one field, or a form for many → save → the object shows the new values. Do not route them to a generic "success" page.

**Delete.** Name the object → state the recovery (undo for N seconds, or "this cannot be undone" plus the dependent damage) → commit → the object is gone from the list and focus moves to a sensible neighbor.

**Search.** Query remains visible → results count → zero-result help (spelling, clear filters) → open a result without losing the query on back.

**Invite or pay.** Review who or what is charged, in their words, on the same screen as the commit. Receipt stays reachable after success.

**Settings.** Group by task the person has ("Notifications"), not by service ("Webhook producer"). Dangerous settings are separated and labeled with their effect.
