# Style guide

Direction: **"Ticket"** (DECISIONS #38). Every idea reads like a filed report:
a short number, a stamp for its status, a log of what happened. Structure from
iOS, character from printed forms and street signs.

**North star: it must feel like a native app on iPhone and Mac, not a website.**
When "looks nice on the web" and "behaves like iOS" disagree, iOS wins.

## Look

- **Square corners everywhere.** No rounded cards, buttons or inputs.
- **Two weights of line:** 2 px strong rules for structure (under a screen's
  header, above the tab bar, input and button borders), 1 px hairlines between
  rows. No shadows; a sheet is set apart by a strong rule, not elevation.
- **Mono for metadata, sans for content.** Titles and text in the sans; IDs,
  dates, authors, statuses and section labels in mono, uppercase, tracked.
- **One accent: street-sign green.** Used for the short ID, the Doing stamp,
  Claude's name in the log, the active tab and primary buttons. Nothing else.
- **Dark is the default** (whatever the phone says); a setting switches to
  light or to following the phone. Both themes are designed, not inverted.

### Tokens

| Token | Dark (default) | Light | Use |
|---|---|---|---|
| ground | `#141413` | `#F2F1EC` | screen background |
| surface | `#1E1E1C` | `#FFFFFF` | rows, inputs, detail pane |
| text | `#EDEBE4` | `#141414` | titles, body |
| text-2 | `#CFCCC3` | `#34342F` | item details |
| muted | `#A3A199` | `#5E5E58` | metadata, labels, inactive tabs |
| rule | `#D9D6CD` | `#141414` | 2 px structure lines |
| hairline | `#33322E` | `#D6D4CC` | 1 px row separators |
| placeholder-line | `#6B6962` | `#8A877E` | dashed "add" fields |
| accent | `#34C17B` | `#0B7A4B` | see above |
| accent-hover | `#6FD9A3` | `#08603B` | links on hover/press |
| on-accent | `#141413` | `#FFFFFF` | text on accent fills |
| danger | `#E5534B` | `#A61B1B` | delete fills and borders |
| danger-text | `#F07870` | `#A61B1B` | delete as text |

Primary "ink" buttons (Log, Move in a swipe) use `text` as fill and `ground`
as their text, so they invert with the theme.

### Type

- Sans: **Public Sans**. Mono: **JetBrains Mono**. Both self-hosted (works offline).
- Large title 36/800, tracking −0.02em. Item title in detail 26/800.
- Row title 17/500. Body 15–16/400, line height 1.4–1.5.
- Mono labels 11–12/600, uppercase, tracking 0.06–0.08em.
- Inputs ≥ 16 px (prevents iOS zoom).

### Patterns

- **Short ID** (`#3F9A`, DECISIONS #40): mono 13/600 in accent, before the title.
- **Status:** Doing = filled accent stamp. Open = no stamp. Done = title struck
  through in `muted`, under a "CLOSED · n" label, with its date.
- **Author:** `CLAUDE` in accent, `ME` in `text`, mono uppercase.
- **Log entry:** date column (mono, `muted`) + "AUTHOR · WHAT" line + the
  comment in the sans. Hairline between entries, newest first.
- **Priority:** two-digit rank (`01`) in mono at the left, drag handle (≡) at
  the right, 44 pt hit area.
- **Rules from the services show up in the UI:** "Mark done" opens a sheet
  asking why (a status change needs a comment, DECISIONS #5).

### Rules

- Text contrast ≥ 4.5:1 (checked for every pair above); colors that must be
  told apart also differ in lightness.
- No gradients, glow, emoji, rounded "cards", left-border callouts (except the
  current project in the sidebar), purple.
- Icons: thin stroke, square caps, one consistent set.

## Native feel (requirements, checked on a real iPhone)

**Installed app, not a browser tab**
- Standalone PWA: no browser UI; status bar blends with the ground
  (`theme-color` per theme, `viewport-fit=cover`, safe-area insets everywhere).
- Proper home-screen icon and launch screen in the ground color (no white flash).

**Touch & motion**
- Every tap target ≥ 44 pt; instant press state; no grey tap flash, no text
  selection on controls.
- iOS-style transitions: push/pop between screens; sheets slide up and can be
  dragged down to dismiss. Spring-like easing, ~300 ms. Respect "Reduce Motion".
- Swipe from the left edge to go back (installed PWAs don't get it for free).
- Swipe actions on rows: Move, Delete.
- Pull-to-refresh on lists; no rubber-band on the whole page.

**Inputs**
- Pickers and choices as sheets or menus, never web dropdowns.

**Speed = native**
- Optimistic updates; cached data first, then refreshed. Skeletons, never
  full-screen spinners.
- The app shell loads offline; data needs the connection (calm offline state).

**Layouts**
- Phone: tab bar (Inbox · Projects · Search), screens push.
- Desktop: sidebar (Inbox, projects grouped by state) · ranked list · item
  detail, side by side. Same tokens, denser.
