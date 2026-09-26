# GridMarket design system

This document describes the GridMarket dashboard design as it ships. The
source of truth for values is the code: `dashboard/src/styles.css` (CSS custom
properties) and `dashboard/src/theme.ts` (the Astryx theme). If this document
and the code disagree, fix one of them in the same change.

Contents: [Principles](#principles) · [Palette](#palette) ·
[Typography](#typography) · [Shape](#shape) · [Layout](#layout) ·
[Components](#components) · [Overview page](#overview-page) ·
[Data rules](#data-rules) · [Accessibility](#accessibility) ·
[Screenshots](#screenshots)

## Principles

1. **Real data or an honest gap.** Every number comes from a served backend
   field. A field the backend does not serve renders the word "unavailable".
   Nothing is invented to fill a layout.
2. **Calm hierarchy.** One display headline per page, numbered sections, and
   quiet structural rules. Emphasis comes from size and weight before colour.
3. **Few colours, used as tones.** Two neutrals, three palette hues and one
   warm status hue. Everything else is a tint or shade of those six.
4. **Colour never carries meaning alone.** Every status also has a word, a sign
   or a symbol.
5. **One family, one curve.** Inter everywhere, and a radius scale derived from
   Inter's letter shapes.
6. **Keep the last known state.** A lost connection shows one banner and keeps
   the last data on screen, marked stale.
7. **Two themes, equal quality.** Dark is the default. Light and dark meet the
   same contrast rules.

## Palette

Six hues:

| Hue | Hex | Role |
|---|---|---|
| Black | `#000000` | Neutral: dark page, light text |
| Ghost white | `#F4F4F9` | Neutral: light surface, dark text |
| Blue slate | `#586F7C` | Palette hue: map borders, muted text shades, dark surfaces |
| Light blue | `#B8DBD9` | Palette hue: secondary surfaces, map tints, series fill |
| Turf green | `#04724D` | Palette hue: accent fill, gains, buy |
| Burnt sienna | `#9E3D1C` light / `#F2A07E` dark | Warm status: sell, loss, warning, stale, outage |

Every other value is a tonal step (a tint, shade or mix) of these hues. Do not
add a hue. Charts, the zone map and the scarcity ramp use tints of the palette
hues only.

### Tokens

Defined once in `:root` in `dashboard/src/styles.css` with `light-dark()`, and
mirrored for Astryx controls in `dashboard/src/theme.ts`.

| Token | Role | Light | Dark |
|---|---|---|---|
| `--page` | Page field | `#E8E9EF` | `#000000` |
| `--surface` | Panels and cards | `#F4F4F9` | `#0E1214` |
| `--secondary` | Map panel, code line, selected nav, spread row | `#DFEBEE` | `#191F23` |
| `--tint-high` | Top of the scarcity ramp, high-scarcity map zone | `#C4DAD7` | `#012219` |
| `--tint-medium` | Medium-scarcity map zone | `#DCEAEC` | `#252C2B` |
| `--warn-bg` | Outage banner, stale badges | `#EADEDE` | `#271A14` |
| `--line` | Structural rules (decorative) | `#C8CFD6` | `#2C383E` |
| `--map-border` | Texas outline | `#586F7C` | `#586F7C` |
| `--text` | Primary text | `#000000` | `#F4F4F9` |
| `--muted` | Secondary text | `#465963` | `#9BBBBD` |
| `--accent`, `--up` | Accent text and strokes, buy, gains | `#036141` | `#88BAAC` |
| `--accent-fill` | Button fill, hero top rule | `#04724D` | `#04724D` |
| `--on-accent` | Text on `--accent-fill` | `#F4F4F9` | `#F4F4F9` |
| `--info` | Informational text and strokes | `#465963` | `#B8DBD9` |
| `--series-fill` | Chart area shading | `#B8DBD9` | `#586F7C` |
| `--down`, `--warning` | Sell, loss, rejected, stale, outage | `#9E3D1C` | `#F2A07E` |

Why the text tokens are shades, not the raw hues: slate and turf pass 4.5:1 on
ghost white but not on the darker light-theme page and tints, so light text
uses `#465963` and `#036141`. On black, raw slate and turf fall below 4.5:1, so
dark text uses light mixes. Raw turf appears only as a fill carrying ghost-white
text. Light blue is never used as light-theme text.

The zone table tints each row by scarcity: `color-mix(in oklab, var(--surface),
var(--tint-high) calc(var(--heat) * 100%))`, where `--heat = (score − 30) / 60`
clamped to 0–1.

## Typography

- **Family.** Inter 4 variable (weights 100–900, optical size 14–32),
  self-hosted from `dashboard/public/fonts/inter-latin-var.woff2` under the SIL
  Open Font License (`dashboard/public/fonts/OFL.txt`). Stack:
  `'Inter', 'Inter Fallback', system-ui, sans-serif` (`--font`). Astryx body,
  heading and code families are set to the same stack.
- **Inter Display.** `font-optical-sizing: auto` selects the Display cut at
  large sizes (headlines, the scarcity number, key numbers). It is the same
  family, not a second typeface.
- **No layout shift.** The font is preloaded with `font-display: swap`. A
  metric-matched `'Inter Fallback'` face (local Arial, Liberation Sans or
  Arimo with size and ascent overrides) covers the moment before the swap.
- **Numbers.** `font-variant-numeric: tabular-nums` applies to numeric
  contexts only: `.num`, tables, `time`, key numbers, the map and the chart.
  Do not apply it to prose; Inter's tabular hyphen spaces out words.
- **Scale (px):** 11 · 12 · 13 · 14 · 16 · 19 · 23 · 26 · 30 · 34 · 38 · 64 ·
  72. **The smallest text is 11px**, including chart ticks, badges and
  uppercase labels.
- **Tracking.** In em, so one rule holds at every size: `--track-caps`
  (+0.06em, uppercase labels), `--track-tight` (−0.02em, key numbers),
  `--track-display` (−0.03em, display headings).

| Role | Size | Weight | Colour |
|---|---|---:|---|
| Hero scarcity number | 72px (64px on phones) | 600 | `--accent` |
| Display headings | 38px (34px on phones) | 600 | `--text` |
| Key numbers | 23–30px | 500 | `--text` |
| Panel titles, row heads | 12–13px | 500 | `--text` |
| Body and table cells | 11–14px | 400 | `--text` |
| Captions, secondary text | 11px | 400 | `--muted` |
| Uppercase labels | 11px | 500–600 | `--muted` or `--accent` |

## Shape

Three radii, derived from the curve of Inter's lowercase bowl at body size:

| Token | Value | Use |
|---|---:|---|
| `--r-1` | 2px | Inline badges up to 16px tall (`Stale`), order-book depth bars |
| `--r-2` | 4px | Controls and inline surfaces 20–44px tall: buttons, nav items, chips, code line, tooltips, inputs |
| `--r-4` | 8px | Surfaces: panels, hero, sandbox card, sidebar key card, disclosure, dialogs |
| 50% | – | Status dots, bot avatars only |

There are no pill shapes.

**Concentric nesting.** When one rounded shape sits inside another with a
small inset, the outer radius equals the inner radius plus the inset. The theme
switcher track is `calc(var(--r-2) + 2px)` around 4px items with a 2px inset.
The hero is 8px with `overflow: hidden`, so the flush map panel follows the
inner edge. When the inset is larger than the outer radius (a button 22px
inside a card), the corners no longer read as a pair; use the element scale.

## Layout

- **Rail shell** (`dashboard/src/components/Shell.tsx`). A fixed left sidebar
  holds the wordmark, the numbered navigation (01 Overview to 07 Spec), the
  market clock in Texas time, data freshness and the "Get API key" call to
  action. The workspace on the right has a masthead with the market label, a
  fixture/simulated tag and the Dark / Light / Auto theme switcher. At phone
  width the sidebar collapses behind a Menu button.
- **Sidebar freshness.** The sidebar shows the latest ERCOT publish time, the
  count of stale series and the polling interval. On a connection error it
  reads "Stale · connection lost" and the status dot turns warm.
- **One outage banner.** When any feed fails, the page shows a single
  `role="status"` line: "API unreachable, retrying", the error, and whether
  last-known data was kept. Panels keep their last data and add a
  "Stale · last known" badge. There is never more than one banner.
- **Pages** use a numbered page heading (eyebrow, display title ending in a
  turf period) and a responsive grid of numbered panels. Every non-Overview
  page ends with the disclosure line.
- **Widths.** Designed and checked at 1280px and 390px, in both themes, with no
  horizontal overflow at 390px.

## Components

| Component | File | Purpose |
|---|---|---|
| `Shell` | `dashboard/src/components/Shell.tsx` | Rail shell, navigation, clock, freshness, theme switcher, skip link |
| `Disclosures` | `dashboard/src/components/Shell.tsx` | One-line expandable legal disclosure |
| `Panel` | `dashboard/src/components/Panel.tsx` | Numbered section panel; `aria-label` makes it a named region; `busy` sets `aria-busy` |
| `Icon` | `dashboard/src/components/Icon.tsx` | Inline stroke icons (up-right, down-right, left-right, plus) for glyphs the font subset lacks |
| `PriceChart` | `dashboard/src/components/PriceChart.tsx` | Recharts line chart of served trade prices, loaded lazily |
| `ZoneMap` | `dashboard/src/components/ZoneMap.tsx` | Schematic ERCOT load-zone map with scarcity tints and pulses |
| `PageHeading`, `FeedBody`, `Stale` | `dashboard/src/pages/Market.tsx` | Shared page heading, polled-panel body (loading, unavailable or data), stale badge |
| Theme | `dashboard/src/theme.ts` | Astryx `defineTheme` tokens matching the CSS tokens |
| Tokens and styles | `dashboard/src/styles.css` | All CSS custom properties, type roles and radius rules |
| Data hooks | `dashboard/src/hooks.ts` | `useResource` polling with shared last-known data per path |

Astryx 0.6.0 supplies structure (`Theme`, `SegmentedControl`, `Button`,
`CodeBlock`). Its controls are re-themed with the tokens above; no vendor
visual identity remains.

## Overview page

`dashboard/src/pages/Overview.tsx`. Its regions, top to bottom:

1. **Prediction card** (hero, 01): the zone and delivery hour with the highest
   predicted scarcity, the scarcity percentage in large Display type, expected
   value against the current future price per Flex Credit, and the top three
   drivers as chips with direction icons.
2. **Key-number strip**: system load, highest scarcity, open interest, active
   traders and participants by provider. Unserved values read "unavailable".
3. **Compact disclosure**: one line stating that these are simulated contracts,
   expandable for the full statement.
4. **Price chart** (02): served trade prices over time in Central time. The
   day-ahead forecast is labelled unavailable because it is not served.
5. **Zone table** (04): zone, real-time $/MWh, scarcity, publish time and a
   `Stale` badge, with rows tinted by scarcity and the leading zone marked.
6. **Order book** (03): sells above, buys below, the spread between them, and
   depth bars. Every row prints Sell or Buy.
7. **Bots and providers** (05): top traders by simulated P&L with their
   provider, linking to each bot profile.
8. **Market anomalies** (06): anomalies from the market status feed.
9. **Sidebar clock and freshness, with the API-key call to action.**
10. **One outage banner** that keeps last-known data on screen.
11. **Zone map**: scarcity tints per zone, pulses at 70% and above, a Pause
    control, and a static fallback under reduced motion. The "Explore in 3D"
    link appears only when a 3D view URL is configured.

The exchange tape (07) and the sandbox card (08, "Trade it yourself") close
the page.

## Data rules

- Bind every field to a real backend shape: `backend/gridmarket_server` and
  [`CONTRACTS.md`](../../CONTRACTS.md). Types live in `dashboard/src/api.ts`.
- A field the backend does not serve renders "unavailable" (or "—" inside a
  table cell). Never fabricate, estimate or hard-code a value to fill space.
- Loading, empty, unavailable and stale are distinct states with distinct text.
- Fixture builds are labelled "ILLUSTRATIVE FIXTURES" in the masthead.
- Times are shown in Central time. Money uses a true minus sign and a fixed
  number of decimals.

## Accessibility

- **Contrast.** Every text token passes WCAG AA (4.5:1) on every surface token
  in both themes. The tightest pair is light-theme `--down` on `--tint-high` at
  4.58:1. Graphic strokes (map border) meet 3:1.
- **Reduced motion.** `prefers-reduced-motion: reduce` removes all animation
  and transitions. The map also has a Pause control and stops pulsing during
  an outage.
- **Visible focus.** Links, buttons, summaries and focusable elements show a
  2px `--accent` outline with an offset. A skip link leads to `main`.
- **Text, never colour alone.** The order book prints Sell and Buy; P&L is
  signed; direction uses icons plus text; stale data says "Stale"; the outage
  banner says "API unreachable, retrying".
- **Semantics.** Panels are named regions; tables use `th scope`; the map and
  chart have text alternatives; the current nav item has `aria-current`.

## Screenshots

As built, rendered from fixtures.

### Overview

| | 1280px | 390px |
|---|---|---|
| Dark | ![Overview, dark, 1280px](screenshots/overview-dark-1280.png) | ![Overview, dark, 390px](screenshots/overview-dark-390.png) |
| Light | ![Overview, light, 1280px](screenshots/overview-light-1280.png) | ![Overview, light, 390px](screenshots/overview-light-390.png) |

### Outage (last-known data kept)

| Dark, 1280px | Light, 390px |
|---|---|
| ![Outage, dark, 1280px](screenshots/outage-dark-1280.png) | ![Outage, light, 390px](screenshots/outage-light-390.png) |

### Market

| | 1280px | 390px |
|---|---|---|
| Dark | ![Market, dark, 1280px](screenshots/market-dark-1280.png) | ![Market, dark, 390px](screenshots/market-dark-390.png) |
| Light | ![Market, light, 1280px](screenshots/market-light-1280.png) | ![Market, light, 390px](screenshots/market-light-390.png) |

### Predictions

| | 1280px | 390px |
|---|---|---|
| Dark | ![Predictions, dark, 1280px](screenshots/predictions-dark-1280.png) | ![Predictions, dark, 390px](screenshots/predictions-dark-390.png) |
| Light | ![Predictions, light, 1280px](screenshots/predictions-light-1280.png) | ![Predictions, light, 390px](screenshots/predictions-light-390.png) |

### Bots

| | 1280px | 390px |
|---|---|---|
| Dark | ![Bots, dark, 1280px](screenshots/bots-dark-1280.png) | ![Bots, dark, 390px](screenshots/bots-dark-390.png) |
| Light | ![Bots, light, 1280px](screenshots/bots-light-1280.png) | ![Bots, light, 390px](screenshots/bots-light-390.png) |

### Bot profile

| | 1280px | 390px |
|---|---|---|
| Dark | ![Bot profile, dark, 1280px](screenshots/bot-profile-dark-1280.png) | ![Bot profile, dark, 390px](screenshots/bot-profile-dark-390.png) |
| Light | ![Bot profile, light, 1280px](screenshots/bot-profile-light-1280.png) | ![Bot profile, light, 390px](screenshots/bot-profile-light-390.png) |

### Sandbox

| | 1280px | 390px |
|---|---|---|
| Dark | ![Sandbox, dark, 1280px](screenshots/sandbox-dark-1280.png) | ![Sandbox, dark, 390px](screenshots/sandbox-dark-390.png) |
| Light | ![Sandbox, light, 1280px](screenshots/sandbox-light-1280.png) | ![Sandbox, light, 390px](screenshots/sandbox-light-390.png) |
