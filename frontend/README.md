# CareerMate frontend

React 19, TypeScript, and Vite frontend for the local-first CareerMate workspace.

## Structure

- `src/App.tsx` coordinates the existing feature workflows and API interactions.
- `src/components/layout/WorkspaceShell.tsx` owns the responsive app frame and primary navigation.
- `src/components/ui/Icon.tsx` contains the shared inline icon component.
- `src/styles/tokens.css` contains design tokens and base styles.
- `src/styles/layout.css` contains the document-first workspace layout and responsive navigation.
- `src/styles/components.css` contains shared controls, cards, list patterns, and dialog styling.
- `src/styles/pages/` contains one stylesheet per workflow, plus responsive and detail-pattern styles.

## Scrolling and dialogs

The document owns vertical page scrolling. The sidebar never becomes a nested vertical scroll container. On narrow screens, navigation becomes a wrapping tab grid. Job details, match insights, and reset confirmation render in portals attached to `document.body` so page transforms and overflow styles cannot reposition or clip them. Dialogs manage Escape handling, focus containment, focus restoration, and document scroll locking. Only the dialog content region is independently scrollable.

## Development

```bash
npm install
npm run dev
```

Create a production build with `npm run build`.
