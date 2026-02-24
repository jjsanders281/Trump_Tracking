# Frontend Agent Reference

## Stack Constraints
- Vanilla HTML/CSS/JS — no React, Vue, or build tools.
- All files served from `backend/app/static/` via FastAPI `StaticFiles` mount.
- No external CDN dependencies without explicit approval.

## File Layout
- `index.html` — single-page app shell, all views rendered client-side.
- `app.js` — API calls, DOM manipulation, event binding, search/filter logic.
- `styles.css` — responsive grid, verdict badges, detail panel, dashboard cards.

## API Integration Patterns
- All data fetched via `fetch()` to `/api/` endpoints.
- Search: `GET /api/claims/search?q=...&topic=...&verdict=...&verified_only=true&limit=25&offset=0`
- Detail: `GET /api/claims/{id}`
- Dashboard: `GET /api/dashboard/summary`
- Workflow queues: `GET /api/workflow/queues/{stage}`
- Workflow summary: `GET /api/workflow/summary`
- Intake: `POST /api/workflow/intake`
- Fact-check: `POST /api/workflow/fact-check/{id}`
- Editorial: `POST /api/workflow/editorial/{id}`

## Security Rules
- HTML-escape all API data before inserting into DOM (prevent XSS).
- Never use `innerHTML` with unescaped user/API content.
- Use `textContent` for plain text, build DOM elements programmatically for structured content.

## Responsive Breakpoints
- Desktop: ≥900px — two-column grid (results + detail panel).
- Tablet: 600–899px — single-column, detail panel below results.
- Mobile: <600px — stacked layout, full-width cards.

## Verdict Badge Colors (Neutral Palette)
Keep color scheme nonpartisan. Badges convey status, not judgment. Current system uses muted tones — maintain this.

## Source Display Priority
Source links and tier indicators must appear before verdict text in claim detail views. Primary sources visually distinguished (bold or icon). This is a hard editorial requirement.

## Accessibility Baseline
- All interactive elements reachable via keyboard (Tab, Enter, Escape).
- Focus states visible on all clickable elements.
- Color alone never encodes meaning — use text labels alongside color.
- ARIA labels on icon-only buttons.

## Performance Targets
- First meaningful paint: < 1s on broadband.
- Search results render: < 200ms after API response.
- No layout shifts after initial render.
