---
name: gridmarket-frontend-design
description: Build or change GridMarket dashboard UI within the shipped design system. Use for new pages, panels, components, styling or layout changes under dashboard/. Do not use for backend-only work, API contract changes, or a redesign of the system itself.
---

# GridMarket frontend design

## Workflow

1. Read `docs/design/DESIGN.md` and `CONTRACTS.md`. Confirm every field you
   show exists in `backend/gridmarket_server` and `dashboard/src/api.ts`.
2. Reuse `Shell`, `Panel`, `Icon`, `PriceChart`, `ZoneMap`, `PageHeading`,
   `FeedBody` and `Stale`. Style with tokens from `dashboard/src/styles.css`
   and `dashboard/src/theme.ts`.
3. Use Astryx 0.6.0 for structure only; keep GridMarket tokens, type and radii.
4. Write the test first. Scope queries with `within(region)`; await fetched
   data with `findBy*`. Never use screen-wide `getByText` on money, times or
   counts.
5. Run `npm --prefix dashboard run test` and `make test-dash`.
6. Check the page at 1280px and 390px, in dark and light: no overflow, no
   clipped text, visible focus, reduced motion static.

## Don't

- Add a dependency.
- Hardcode a colour, font size, radius or font family.
- Change routes in `App.tsx` without a `CONTRACTS.md` update.
- Fabricate or estimate data; an unserved field reads "unavailable".

## Review checklist

- Every value binds to a real backend field; gaps read "unavailable".
- Loading, empty, unavailable and stale states each have their own text.
- Only palette tokens; text pairs pass 4.5:1 in both themes.
- Meaning never depends on colour alone.
- Text is 11px or larger; numbers use tabular figures.
- Radii use `--r-1`, `--r-2` or `--r-4`, nested concentrically.
- Tests use `within()` and `findBy*`; both commands pass.
- Screenshots at 1280 and 390 in both themes match `DESIGN.md`.
