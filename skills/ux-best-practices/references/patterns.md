# Patterns

Pick the least ceremony that still makes the action clear and reversible. If the repo already has a pattern for this job, use it.

## Choosing a container

| Job | Use | Avoid |
| --- | --- | --- |
| Go somewhere | Link. Supports open-in-new-tab and back. | `div` with click, or a modal that only navigates. |
| Do something on this page | Button. | A link styled as a button for a non-navigation action, or the reverse. |
| Read or edit a long thing | Its own route. | A modal with an inner scrollbar as the editor. |
| A short decision with one consequence | Dialog, focused, easy to dismiss. | A dialog with three unrelated decisions. |
| Extra detail that should keep the list in view | Drawer or split view. | Navigating away for a one-line edit they will repeat. |
| One field, rarely | Popover or inline edit. | A full-page form. |
| Status that is not required to continue | Toast or inline status, also announced to assistive tech. | Toast as the error of record. |
| Teaching a control | A visible label, or one sentence beside it. | A multi-step coach mark tour. |

Dialogs trap focus. That is a cost. Use them for confirmations, short creates, and blocking errors that must be resolved. Always provide Escape and a visible close, except when a genuinely blocking decision is required, and even then both choices are explicit.

Do not stack dialogs. If a dialog needs another dialog, it wanted a page.

## Hierarchy

- One primary button per region. Secondary is quieter (text button or lower contrast). Tertiary is a link.
- Destructive is never the primary visual on a routine form. On a confirm step whose only job is destruction, the destructive action is primary and named, and Cancel is safe and easy.
- Reading order matches action order. Do not put the only "Next" at the top and the only explanation at the bottom unless the platform convention is a top app bar and the action is global.
- Group by relationship: proximity and a heading, not a box around every idea. Cards are for repeated objects a person scans, not for every paragraph.
- Alignment is a column the eye can ride. A form's labels and inputs share one edge. Mixed left-and-center alignment in one tool looks unfinished and slows scanning.

## Forms

- Visible label, always. Placeholder is an example, not a label. Placeholders end with an ellipsis character when they are hints.
- One column unless the fields are a natural pair (city and postal code) and the width is desktop.
- Mark the minority: if most fields are required, mark optional. If most are optional, mark required. Do not mark both on every field.
- Order: identity and easy fields, then the commitment. Group with headings when there are more than about seven fields.
- Help text sits under the label or under the field, persistent, and is not a duplicate of the label.
- Use the right control: select or radio for a small closed set (radios when fewer than about seven and comparison matters; a select when the list is long). Do not use a select for two options; use a radio or a toggle whose on and off states are words.
- Toggles are for immediate settings, not for "I agree" and not as a submit.
- Checkboxes are for independent options. Radios are for one of a set. A single checkbox is an agreement or an on state with a label that includes the verb.
- `autocomplete`, `inputmode`, and `type` match the data (email, tel, name, street-address, one-time-code).
- Do not block paste. Offer show/hide on passwords. Spellcheck off for emails, codes, and usernames.
- Tell password rules before the person fails them.
- Validate on blur after touch, and on submit. Do not validate on the first character.
- On submit, keep values, focus the first error, and leave the button enabled until the request actually starts. Then pending, no double post.
- Multi-field dates and addresses use locale-aware input, not three unlabeled boxes, unless a library the product already uses does better.
- File inputs state accepted types and the size limit before the attempt.
- Repeating rows (line items) have add, remove, and a keyboard path. Do not make the person drag to reorder unless a move-up and move-down also exist.
- Warn before discarding unsaved changes. Autosave when the object is a draft the person expects to keep (documents). Explicit save when the commit has external effects.

### Choice overload

If there are more than a handful of options, offer a default and a way to see the rest. Recommended plan, recent projects, and "more options" beat a wall of equal cards. Defaults must be safe: the cheapest plan, the private visibility, the least privilege, unless the person already chose otherwise.

## Navigation and information architecture

- Structure follows tasks the person repeats, then objects, then the org chart. Never the org chart first.
- Top-level destinations are few and stable. The current one is marked.
- Labels are words the person uses. "Billing" beats "Monetization engine".
- Depth greater than two gets breadcrumbs or an equivalent "you are here" that includes parents as links.
- Global search appears when the person cannot reasonably scan the set. The query, the scope, and the zero-result state are part of the feature.
- Do not put the primary action only inside a hamburger. Collapse secondary navigation on narrow screens; keep the job's main action visible.
- Account, help, and destructive session actions (log out) live in a predictable corner, not mixed into the task navigation.
- In-page anchors need `scroll-margin` so sticky headers do not cover the target.

## Search, filter, sort

- Filters that are on are visible as chips or an equivalent, each removable, plus clear all.
- Sort state is visible. Default sort matches the task (recent for inboxes, relevance for search, severity for errors).
- Combining filters is AND unless you label the logic. Do not make the person guess.
- Preserve filter state in the URL.
- A result count prevents the "did it search?" moment.

## Tables and lists

- Rows are for objects. Columns are for attributes the person compares. Actions for a row sit on the row, not only in a mystery kebab, if they are the main job (open, edit).
- Numeric columns line up and use tabular figures.
- Truncate with the full value available on focus, expansion, or the detail view. Do not truncate the only identifier so two rows look the same.
- Empty cells are a dash or "none", not a blank that looks like a bug, when the blank is ambiguous.
- Row hover is not the only way to discover actions. Keyboard and a visible menu must reach them.
- Pagination versus infinite scroll: pagination when people compare, cite a position, or need a footer. Infinite scroll for homogeneous feeds. Never infinite-scroll a footer action out of reach without a sticky bar.

## Feedback and motion

- Hover, active, and focus states exist on every interactive control and increase clarity. Focus uses `:focus-visible`, not a ring on every mouse click, and never removes the outline without a replacement.
- Motion communicates cause: the panel that opened, the item that moved, the status that changed. One orchestrated moment beats entrance animations on every block.
- Honor reduced motion. Do not autoplay motion longer than a few seconds beside other content without a pause.
- Do not use `transition: all`. Animate transform and opacity unless a specific property needs to change.

## Mobile and pointer

- Design the narrow viewport as a real layout, not a squeezed desktop. Stack the primary content; keep the primary action in the thumb zone if the task is one-handed.
- Targets at least 44×44 px on touch. Gap between targets so a miss does not hit the neighbor.
- Do not rely on hover. Anything hover revealed needs a tap equivalent.
- Inputs of the right type so the right keyboard opens.
- Do not autofocus a field on mobile if it opens the keyboard over the task. Autofocus is for a desktop screen whose only job is that field.
- Respect safe areas and the on-screen keyboard. The action must remain visible or sticky when the keyboard is open on a short form.
- Pull-to-refresh and swipe actions are extras. Provide a visible refresh or a menu action too.
- `touch-action: manipulation` on controls so double-tap zoom delay does not make the UI feel broken. Do not disable page zoom.

## Onboarding

The best onboarding is a product set to a useful default with one obvious first action.

- No carousel that blocks the product.
- No tooltip sequence that must be completed.
- Sample data only if it is clearly sample and one action removes it.
- Teach at the moment of the first relevant action, in one sentence, dismissible, and not shown again after they have done the thing.
- Empty states do the teaching for areas they have not visited.

## Settings and density

- Settings are grouped by user goal. Search when the list is long.
- A change that takes effect immediately says so. A change that needs save has a save and a dirty state.
- Dangerous and rare settings are not interleaved with daily ones.
- Offer a denser layout only if the audience lives in the tool all day. Default to a comfortable target size and line height (body line height around 1.4–1.6, line length under about 80 characters for reading text).

## Internationalization

- Leave room for strings about 30–40% longer than English. Do not size buttons to the English word.
- Do not concatenate sentences. Use full strings so translators can reorder.
- Bidi: icons that imply direction mirror when the locale does; icons that are objects (a clock, a logo) do not.
- Do not bake locale into images of text.

## Trustworthy defaults for data display

- Units are labeled. Precision matches the decision (do not show 12 decimals for money).
- Zero is "0", not blank, when zero is information.
- Negative and destructive numbers are signed and not color-only.
- Relative time ("3 hours ago") includes the absolute time on focus or when the exact moment matters.
- Avatars and logos have a text fallback when the image fails.
