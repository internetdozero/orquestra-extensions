---
name: lean-screen
description: >
  Stop the generic admin-dashboard screen on any product. Use on every new or
  changed UI, page, list, settings view, reading view, or generated layout.
  Bans obvious subtitles, the eyebrow-title-subtitle stack, decorative metric
  heroes, equal KPI cards, card-in-card, decorative row chrome, and a narrow
  centered column with huge side gutters. The first screen is this product's
  job at full content width. Secondary facts get a named place, not a delete.
  Do not strip a manager down to a database grid, and do not hide a list
  action behind Open. A product with several areas gets a persistent
  sidebar. Personality comes from composition and the existing accent, not
  from a display font. Do not reuse the
  objects, verbs, or layout of a previous screen. Triggers: UI, tela,
  dashboard, cards, KPI, métricas, subtítulo, layout, "muita informação",
  "não sei onde olhar", /lean-screen. Task rules stay in ux-best-practices.
  Visual identity stays in the design system or frontend-design.
---

# Lean screen

The first screen is the job, drawn once, at the width of the work. A second sentence, a second number, or a second panel has to earn its place by changing what the person does next.

This skill owns the screen template coding agents emit by default: metric heroes, explanatory subtitles, equal cards, squeezed center columns, and lists dressed as dashboards. It does not own task logic, forms, or accessibility. Those stay in `ux-best-practices`. It does not pick a visual identity. If a design system exists, use it. Do not restyle the product to apply this skill.

Run the checklist in `references/tells.md` before calling a screen done. A match means cut the decoration or move the fact. Deleting a function the person still needs, and leaving no path to it, is a failed screen.

## Before drawing

Name the job of this screen from the product in front of you. Do not borrow the job, the nouns, or the verb from a previous project.

Match the screen to that job:

- One action on an existing surface → a button. Do not build a page.
- A list the person acts on → that list.
- A record they read or edit → that record.
- A value they came to check → that value.

The primary control uses the job's verb. "New", "Edit", and "Delete" are primary only when they are the job. "Open" is not a job verb. Utility actions stay quiet and off the first reading cluster.

## Where the rest lives

On demand means a place with a name the person can predict. A summary, a history, a set of totals, or a rare tool gets a panel, a second view, or one quiet line. Build that place. Do not delete the fact because it was not allowed to be a hero card.

Name the place for what is inside. "Data", "More", and "Info" are not names. If the previous screen had a function and this one has no way to reach it, the screen is not done.

A tab or a second view is a different job, not a second copy of the same cards. Do not put a control on the first screen whose only purpose is to hide the dashboard. If the panel needs a hide button, it was not the first screen.

## The product has a shell

When the product has more than one area, the areas live in a persistent side navigation. Group them. Mark the current one. Put a count on an item when the count is a backlog the person acts on. The page is one area. It does not carry the rest of the product, and it does not delete the rest because they do not fit.

A few modes of the same area are tabs under the title, named for the mode. A few stable views of the same list (with counts) sit with the list. They are not four dropdowns, and they are not a second sidebar.

Global search belongs to the shell. Search of this list belongs to the list. The primary action of the area sits where the work starts. Utilities stay in the shell, quiet.

A long catalog shows a window and an honest way to see the rest. It does not dump every row, and it does not hide the rest behind an unnamed control.

## Personality is the composition

Use the type, accent, and density the product already has. If it has none, use one neutral text face and one accent. The accent marks the active nav item and the primary action. Almost everything else is neutral.

What reads as finished is alignment, a clear row, muted secondary text, and the current place being obvious. A display face, a gradient, or a new palette does not fix a page whose structure is wrong. Do not restyle the product to look designed.

## What the first screen contains

Only what this job needs now. Order, status, and verbs follow the job. They are not a fixed layout.

- When the person must act on items, show the items and the action. Put unfinished work first only when the job is to finish work. A directory stays in the order they asked for.
- When the person must read or compare, show that reading. Several comparable measures may sit in one compact row when comparing them is the job. Each one carries a real comparison (previous period, target, or an honest empty). A sparkline or a chart is the body only if the series exists. A caption does not repeat the number. A badge on the card does not replace the comparison. One measure that is the whole job appears once, not as a peer of three decorations.
- When the job is a single action, the screen is that action.
- A status word appears only when it changes what the person does next. One word, and it has to be true. Success styling on partial work is a lie. Partial stays partial.

A count is allowed once, small, beside the thing it counts, when it changes the next action. A number bigger than the work is vanity when the number is not the work. Two large numbers that mean different things and look like a pair are a false rhyme. Keep the one fact that decides the next click.

## What leaves the first screen

Extra totals, charts, history, empty fields, rare filters, explanations, and a form that edits every field. They move to the named place above. They do not vanish, and they do not all dump into the object as a tax for every row action.

Keep an extra total, chart, or history on the first screen when that is the job. Do not demote the job into a disclosure to make the page look minimal.

## A manager is not a spreadsheet

When the job is managing a collection, the row is the object plus the action. The name is the heaviest text. The job verb is on the row. Fields the person compares stay. Fields that are empty for most rows, and fields they rarely compare, are not columns.

The spreadsheet failure is every property as a column, a dash where data is missing, a copy icon on every value, a category glued under the name, and a single button that only opens the record. Using the full width to add those columns is the same mistake as the narrow dashboard. Width belongs to the identity and the action.

A row reads as one object. The name is strongest. One status or amount sits quiet at the end. A second line is a preview the person scans, muted, not a stack of labels. The way into the record is the row itself or a final cue, and it does not replace the job verb.

Removing an item is a list action when the person is managing the list. Keep it on the row, named and quiet, in a menu on that row if it must stay off the primary. Do not force a detail screen just to delete. Confirm with the object's name, and say whether the record goes away or the thing it points at does. Delete stays off the row only when it is rare and more dangerous than managing the list. Then the detail holds it, and the job verb is still on the row.

## Composition

- **One weight.** Squint. One cluster is heavier, and that cluster is the job. Equal cards, equal badges, and equal header buttons mean there is no focus. Fix the weight before adding anything.
- **Full width of the work area.** A tool, a table, a queue, or a console uses the content region beside the shell. Do not wrap it in `max-w-4xl`, `max-w-6xl`, `max-w-7xl`, or a centered narrow column that leaves wide empty gutters while the data is cramped. Cap line length only for prose you expect someone to read (about 65–75 characters).
- **No page furniture that restates the page.** One title, the name of the place or the object. No eyebrow in small caps above it. No subtitle that defines the title ("Library — where your library lives"). No badge next to the title that repeats the product. A second line is allowed only for a fact the title does not already say, and only if that fact changes the action.
- **No instruction line.** "Click a chip to filter instantly" means the control does not look like a control. Fix the control and delete the sentence. Do not brag that an interaction is instant.
- **Grouping by position, not by boxes.** Proximity and a heading. A card is for a repeated object the person scans as a unit, or for a true boundary (a modal, a draggable tile). A stat, a filter strip, and a table do not each get a card. Never a card inside a card. A list of seven does not become seven large cards.
- **A column that is mostly empty is not a column.** Collapse it. A dash is not data. A missing required value must not look like an optional blank. Show the gap when it changes the action. Omit it when it does not.
- **Do not triple-encode.** A fraction, a percent, and a bar for two items are one fact three times. Prefer the items, named, checkable, when the person must complete them. A bar that cannot be told apart at a glance (50% versus 67% of three) does not belong.
- **Do not decorate the row.** Monogram tiles when the name is already there, a category repeated under every name, a permanent copy icon, a pill plus a bar plus a percent. Copy and other rare acts appear on focus. The row is as tall as its data.
- **Destructive acts are quiet, named, and reachable.** An unlabeled trash icon glued to the only button is a misclick. So is a delete that exists only after Open. Follow the manager rule above.
- **Filters earn their place.** Search and filters appear when the list is long enough that scanning fails. A sort disguised as a filter ("Name A–Z" beside "Status (All)") is a sort. A filter chip with zero matches is not a peer of the real ones.
- **No filler objects.** Do not invent a row, a bucket, or a sample record so the layout looks populated. Do not show a truncated or uncertain value as if it were confirmed.

## When the admin template shows up

The reflex is a header stack, a row of metric cards, chips, a filter bar, a striped table, and Edit plus Delete. Use it only when that is actually the job. Otherwise:

1. One title. The name of the place or the object.
2. The job itself, at the content width. A list, a record, a value, or a single action. Not a substitute queue.
3. Chrome that restates the job comes off the first screen.
4. Totals and history move to a named place unless they are the job. They are not deleted.

## Do not

- Do not add a dashboard to a task that is a button.
- Do not turn a reading, a record, or a single action into a queue of unfinished objects.
- Do not teach the screen with a subtitle.
- Do not use the type preset of eyebrow + title + supporting sentence on sections, cards, or the page.
- Do not lead with metrics that are not the job.
- Do not center a cramped tool in a sea of empty margin.
- Do not make every region a card.
- Do not use success color for incomplete work.
- Do not give several names to one idea unless the difference changes the action. Pick one word.
- Do not ship a screen where a person cannot point to the next click, or the thing they came to read, in a second.
- Do not answer a crowded screen by deleting its functions. Move what is secondary. Keep what the job needs on the surface.
- Do not turn a manager into a database grid whose only action is Open.
- Do not put every area of the product on one page, and do not delete those areas because the page is lean. Give them the sidebar.
- Do not invent a typeface or a palette to manufacture personality. Fix the shell, the row, and the accent.
