# Writing

Interface words are navigation. Write the smallest text that lets a person act correctly. Match the product's locale and the voice the product already uses. If none exists: plain, specific, second person, sentence case, active voice.

## One job per string

| Element | Job | Test |
| --- | --- | --- |
| Title | Names this place or object | A person scanning tabs can tell it from the neighbor. |
| Label | Names the data or the action | Still clear with the helper text deleted. |
| Button | Verb plus object, the outcome | The toast can repeat the same verb in the past tense. |
| Helper | Format, constraint, or consequence the label cannot carry | Removing it would cause a predictable error. |
| Error | What happened and the fix | A person knows what to type or press next. |
| Empty | Why it is empty and the next action | The action is a control, not a suggestion in prose only. |
| Confirm | Names the object and the irreversibility | "Are you sure?" fails this test. |

## Buttons

- "Save changes", "Publish article", "Delete Northwind". Not "Submit", "OK", "Yes", "Continue" unless the object is obvious in the same breath.
- The dangerous button names the damage: "Delete 12 invoices", not "Confirm".
- Cancel is "Cancel" or "Keep editing", not "No".
- Pairs agree in grammar: "Save" / "Discard", not "Save" / "No thanks".
- Do not put a period on a button. Do not use "click here".
- If the action needs a modifier (public, billed, emailed), put that in the button or the sentence immediately above it, not in a distant footnote.

## Labels and headings

- Sentence case for headings, labels, and buttons in product UI. Title Case is for proper names and for platforms that already use it everywhere (some marketing pages). Do not mix in one product.
- No trailing colon unless the locale's forms convention needs it.
- Headings state the task ("Invite people"), not the enthusiasm ("Let's grow your team!").
- Do not number headings (01 / 02 / 03) unless the numbers are a real sequence the person must follow.
- Avoid ALL CAPS for sentences. Short nav labels in small caps are a visual style, not a readability win. Never use caps as the only emphasis for a warning.

## Helper text

- Examples use realistic values, marked as examples: "Example: ada@studio.com".
- State limits before failure: "Under 10 MB. PDF or PNG."
- Say who will see it if visibility is non-obvious: "Visible to anyone with the link."
- Cut "please", "simply", "just", and "easily". They add length and sometimes sound like blame.

## Errors

Pattern: *What is wrong. How to fix it.* Optional third beat only when the system is at fault: *What we did with their data.*

- "The file is 24 MB. The limit is 10 MB."
- "We couldn't save. Your draft is still on this page. Retry."
- "Card declined. Try another card or contact your bank."

Do not:

- Say "Oops" or tell the person to calm down.
- Blame "invalid input" with no field and no rule.
- Expose exception class names, SQL, or status codes as the only text. A code can be secondary for support.
- Apologize for a constraint the person can satisfy. Do apologize when the product lost work or acted wrong: "We published the draft by mistake. We reverted it."

## Empty and success

- Empty: "No invoices for March. Create an invoice." The second sentence is a button.
- Success: "Invoice 1042 sent to ada@studio.com." Include the specific result they will look for.
- Pending: "Sending…" with the ellipsis character, not three periods. The sentence ends when the result arrives. Do not leave "Sending…" as the final state.

## Voice

- Second person ("Your draft"). Avoid first person ("I'm your assistant") in ordinary product chrome. First person is reserved for a named agent speaking in a transcript, and even then the UI chrome around it stays second person.
- Present tense for state, past for completed actions.
- Consistent glossary. Pick "project" or "workspace" once. Pick "delete" or "remove" once and use the other only if the meaning differs (remove from a list versus delete from the system) and the UI says which.
- No marketing adjectives inside a tool ("powerful", "seamless", "magic") unless the user asked for a marketing page.
- No fake urgency ("Don't miss out") on a system dialog.
- Jokes only if the product already uses them and never on errors, billing, permissions, or data loss.

## Sensitive moments

- Permissions: name the access and the benefit. "Microphone, so you can record the meeting." Provide a way to proceed without it when the feature allows.
- Money: show the amount, the cadence, and the moment it will be charged before the commit verb.
- Privacy: say what is shared and with whom in the control, not only in a policy link.
- Irreversible: the word "permanently" is allowed when true. Do not say "permanently" for something undo can restore.
- Legal agreements: the label is the agreement ("I agree to the Terms"), the terms are a link, and the box is not pre-checked.

## AI wording

- Do not say the system "knows", "understands", or "is sure" unless you are showing a calibrated signal.
- "Draft" for text the person has not sent. "Sent" only after the side effect happened.
- Name the source of a factual claim when the product has one ("From the Q3 report"). If there is no source, do not invent a citation.
- Uncertainty is a sentence: "This is a guess based on the filename. Check the total before paying."
- Refusal and safety messages say the boundary and, when allowed, a next step. They do not scold.

## Punctuation and locale

- Use the ellipsis character (…) in UI truncation and pending strings.
- Use locale punctuation and quotation marks, or the product's house style, consistently.
- Non-breaking spaces between a number and its unit.
- Numerals for counts ("8 files"), including 1–9, in UI.
- Translate full phrases. Do not build sentences by gluing translated fragments.
- Brand names, user names, and code stay untranslated (`translate="no"` where the web platform needs it).

## Content that fills a layout

If the real copy is missing, write specific, short, plausible product copy and mark it as a draft assumption. Do not use lorem ipsum, "John Doe" in a shipping product, fake star ratings, or stock testimonials. Those read as finished and lie.

Cut copy until removing another word would force a wrong action. Then stop.
