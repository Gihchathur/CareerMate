# CareerMate 3.4 — Navigation and starter portal improvements

## Navigation

- Desktop collapsed rail: 60px.
- Desktop expanded rail: 220–238px, activated by pointer hover or keyboard focus.
- No nested sidebar scrolling. The navigation list uses a compact viewport-relative row height and hides decorative group captions before shrinking or hiding destinations.
- At very short desktop heights, the profile footer is hidden so the complete set of navigation links stays visible. Candidate profile remains reachable from the top-right avatar.
- Touch devices retain the mobile bottom navigation and More sheet.

## Starter employer portals

CareerMate includes five enabled sample employer board configurations: Spotify (Lever), Vercel (Greenhouse), Lovable (Ashby), Legora (Ashby), and Temporal (Ashby). They are sample integrations; their health is initially Not checked. Run **Check portal health** from the Portals page to confirm current reachability from your machine.

The portal seed marker is now version 3. This is important for upgrades from CareerMate 3.3: older installations may already have marker version 2 despite having an empty `data/sources.json`. Version 3 performs an additive merge of the starter records, preserving user boards and user edits. After the version 3 marker is written, removing a sample portal is respected and it will not silently reappear.

## Validation

- Backend tests include migration coverage for a version 2 marker with an empty source registry.
- `data/sources.json` remains private/local and is not shipped in the source archive. `data/sources.example.json` remains the API-compatible template.
