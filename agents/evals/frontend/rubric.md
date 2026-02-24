# Frontend Agent Evaluation Rubric

Score each criterion 0-2. Target average: ≥ 1.7.

## Criteria

### 1. Visual Correctness
- 0: Layout broken, content overlapping or missing.
- 1: Layout works on one viewport but breaks on others.
- 2: Layout correct across mobile, tablet, and desktop.

### 2. Source Visibility
- 0: Source links hidden or absent from claim detail views.
- 1: Source links present but not prominently positioned.
- 2: Source links and tier indicators appear before verdict text, primary sources visually distinguished.

### 3. Security (XSS Prevention)
- 0: Unescaped API data inserted via innerHTML.
- 1: Most content escaped but some paths use innerHTML with API data.
- 2: All dynamic content HTML-escaped or built via DOM APIs.

### 4. Accessibility
- 0: Interactive elements unreachable by keyboard or missing focus states.
- 1: Keyboard navigation works but focus states unclear or ARIA labels missing.
- 2: Full keyboard navigation, visible focus states, ARIA labels on icon-only buttons.

### 5. API Integration
- 0: Broken API calls or incorrect parameter handling.
- 1: API calls work but error states not handled (loading, empty, failure).
- 2: All API calls work with loading indicators, empty states, and error handling.
