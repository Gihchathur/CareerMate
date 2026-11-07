# CareerMate 3.6.1 — Floating controls, application review states and CV template

## Browser application dropdowns

All frontend dropdowns now use a shared custom floating select. Its menu is rendered in a portal attached to `document.body`, so it is not clipped by cards, page panels, the Pipeline board, Evidence Vault or the expanding navigation rail. It repositions on window and visual-viewport scroll/resize, adapts to available space above/below the trigger, and follows the rail's short width transition. This replaces every native `<select>` in the frontend.

Keyboard support: Enter/Space opens or selects, Arrow Up/Down moves, Home/End moves to the first/last enabled option, Escape closes and restores focus. Search is available for longer option lists.

## Application field review states

- **Needs your input** — required/question/long-form fields with no answer yet; amber styling.
- **Profile value · review / Existing value · review / AI suggestion · review** — clearly distinguishes where a proposed value came from; blue styling until the user confirms it.
- **Accepted** — the user manually changed or explicitly selected a value; green styling.
- **Filled in employer form** — CareerMate confirmed that the selected value was applied to the live employer form; green styling.
- **Optional** — no answer is required and no suggestion is present; neutral styling.

A `false` checkbox answer is valid only after explicit user review. Legal consent, work authorization, salary, identity and other sensitive fields remain user-controlled. The final submission still requires separate approval. Each status also has short guidance beneath the field so a user can understand what to do next.

## New CV template

The CV Studio now offers **Sectioned professional · centered header and grouped skills**. The DOCX/PDF uses the same structure as the saved Backend CV: centered name and editable headline, two contact rows, a violet divider, Professional Summary, categorized Technical Skills, Professional Experience with right-aligned dates and location, Projects, Education, and Achievements. It remains single-column and table-free for ATS readability.

The template structure was aligned against the saved `Gihan_Chathuranga_Resume-Backend.pdf` reference: centered name and role, compact contact rows, Professional Summary, categorized Technical Skills, Professional Experience with dates/location, Projects, Education, and Achievements. It retains a single-column, table-free DOCX structure for ATS readability. The user's CV headline can be edited in Candidate Profile and is shown beneath the name. Colors, type and spacing are adapted to CareerMate's design system rather than being a pixel-identical copy.

## Verification

- Backend tests: 173 passed.
- DOCX generated and rendered; a two-page sample was visually reviewed on both pages.
- PDF exported and rendered; selectable text, section headings and both pages were visually reviewed.
- Frontend TypeScript/TSX syntax and stylesheets parsed. A full Vite production build requires installing the frontend npm dependencies locally.

## Visual CV template preview

The sample DOCX/PDF was rendered and both pages inspected. Preview images are included in the repository:

- [`sectioned-cv-style-page-1.png`](previews/sectioned-cv-style-page-1.png)
- [`sectioned-cv-style-page-2.png`](previews/sectioned-cv-style-page-2.png)

The preview uses sample candidate details; your own saved Candidate Profile is used when you generate a CV in CareerMate.
