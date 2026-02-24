# Design Refresh Plan (MVP UI)

## Objective
Improve visual trust, scan speed, and usability of the current site without blocking ongoing data ingestion and review workflow.

## Current UI Audit
### Strengths
- Clear functional separation across Search, Dashboard, Intake, and Review tabs.
- Good baseline data exposure for claims, sources, and workflow state.
- Consistent card styling and spacing primitives already exist.

### Primary Gaps
- The main search workspace has weak hierarchy, so filters, results, and detail compete for attention.
- The table-first result view is dense and not optimized for fast triage.
- Verdict states are visually under-expressed (badges do not convey level of concern clearly).
- Focus and keyboard interaction states are minimal, especially for row selection and actionable controls.
- Brand tone is neutral but visually generic; trust cues can be stronger.

## Visual Direction
### Theme: "Public Record Desk"
- Tone: institutional, evidence-first, restrained.
- Typography:
  - Headings: `Newsreader` (serif, editorial authority).
  - Body/UI: `Source Sans 3` (readability at density).
- Color system:
  - Base parchment neutrals remain, but with stronger contrast boundaries.
  - Introduce semantic verdict tokens:
    - `true`/`verified`: green family
    - `mixed`/`unverified`: amber family
    - `misleading`/`false`/`contradicted`: red family
- Visual motifs:
  - Sticky section headers
  - Inline citation markers
  - Strong row hover and selected states

## Layout Changes (No Backend Blockers)
1. Search tab becomes a 3-zone workspace on desktop:
   - Left: collapsible filter rail
   - Center: results list/table
   - Right: sticky claim detail panel
2. Mobile collapses to stacked order:
   - filters -> results -> detail
3. Dashboard cards get tighter visual grouping and semantic color accents.
4. Intake and Review forms use stronger section framing and clearer step hierarchy.

## Component Plan
1. Token layer
   - Expand `:root` vars for semantic color and spacing scale.
2. Verdict chip system
   - Replace single neutral badge style with verdict-specific classes.
3. Result row/card state
   - Add selected state and keyboard-focus style.
4. Citation block
   - Standard source block with publisher, tier, and external-link affordance.
5. Action button system
   - Normalize primary, secondary, danger, and neutral variants.

## Accessibility Plan
1. Add explicit `:focus-visible` styles for all interactive controls.
2. Ensure contrast meets WCAG AA for text and critical states.
3. Add ARIA tab semantics and keyboard support for tab switching.
4. Avoid color-only meaning by pairing verdict colors with labels/icons/text.

## Phased Implementation
### Phase 1 (Quick Wins, 1-2 days)
- Update design tokens and typography stack in `styles.css`.
- Improve tab bar, card headers, button variants, and focus states.
- Add verdict-specific badge classes and styling.

### Phase 2 (Core UX, 2-4 days)
- Refactor Search tab layout into filter/results/detail zones.
- Add persistent selected-row state and clearer detail panel hierarchy.
- Improve mobile layout behavior and spacing rhythm.

### Phase 3 (Trust + Discovery, 3-5 days)
- Add timeline visualization block for dated claims.
- Add contradiction link panel in detail view.
- Add revision history teaser in claim detail card.

## Backend Requests (for Later UX)
1. Contradiction details endpoint (`P1`)
   - Why: support contradiction panel and related-claim navigation.
2. Revision history endpoint (`P1`)
   - Why: show edit transparency directly in UI.
3. Search facets endpoint (`P2`)
   - Why: dynamic filter counts and better discovery.

## Next Implementation Slice
1. Restyle primitives and semantic tokens in [styles.css](/Users/jason/Documents/Trump_Tracking/backend/app/static/styles.css).
2. Add structural hooks/classes in [index.html](/Users/jason/Documents/Trump_Tracking/backend/app/static/index.html).
3. Add selected-result state + verdict class mapping in [app.js](/Users/jason/Documents/Trump_Tracking/backend/app/static/app.js).

## Assumptions
- Current tabs and workflow structure stay intact for this iteration.
- No frontend framework migration in this phase.
- Primary goal is usability and trust, not animation-heavy redesign.

## Risks
- Too much visual change in one pass could disrupt reviewer muscle memory.
- Semantic verdict colors may need tuning for accessibility and neutrality perception.

## Confidence
85%
