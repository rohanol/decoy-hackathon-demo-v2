# M1 Frontend and design (Pashmee)

You own the ENTIRE frontend: design, every screen, and all the code in `frontend/`, plus `docs/demo/` (deck and demo script). Rohan does not write frontend code. He gives you the API, types and fixtures and answers questions.

Order of work:
0. **H0 to H4, design first** (can be done in Figma, Canva or plain sketches): wireframes for the 7 screens below, colours, severity badges (low, medium, high, critical), fonts, spacing. Wording on screen comes only from `AGENTS.md` section 7.
0b. **By about H3 start coding.** Ask Rohan for the fixtures and the `/openapi.json` link (he sends both by about H2). Start the Vite app on fixtures right away, do not wait for the live backend.
0c. If the live feed is not ready at H4, the team still passes G2 by showing the event in the backend's `/docs` page or `GET /api/events` in the browser. Do not skip the design to chase G2.

You own `frontend/` and `docs/demo/`. Read `AGENTS.md` and `contracts/API.md` first. Build against `contracts/examples/events_p3.json` until the backend is up, behind a `VITE_USE_FIXTURES=1` flag that is off on the demo path.

Rohan only changes `contracts/` and `backend/`. If an API shape blocks you, tell him in the group chat, he fixes the backend, not your UI.

Stack: Vite + React + TypeScript (strict). Generate types from the backend's `/openapi.json` once it exists (`npx openapi-typescript`), until then hand-write them from the contracts. Keep libraries minimal: a graph lib (React Flow or Cytoscape), nothing heavier.

Tasks in order:
1. Scaffold the app on 127.0.0.1:5173. Live feed page: REST snapshot from `GET /api/events`, then `/ws/events`, newest on top, connection status pill (live / reconnecting / offline). **H4 target: a real SSH event from Kali shows up here.**
2. Incident list and incident page: severity badge, score with breakdown table (rule, points, counted or not and why), findings with label + limitation, every evidence ID clickable to the raw event.
3. Kill-chain bar per incident: recon, credential attack, exploit attempt, post-access, data access. Unobserved stages grey with "not observed".
4. SSH transcript replay from `/transcript`: terminal-style, step through lines with timestamps. Label it "commands submitted to emulated shell".
5. Attack graph: nodes are sensors and the attacker IP, edges are links. Dashed = candidate, dashed + token label = strong candidate, solid = confirmed. Clicking an open link opens confirm/reject with a required rationale.
6. Noise counter on overview from `/api/stats/overview`: "N raw events → M incidents, K low priority".
7. Block flow: button on incident → preview modal (target IP, scope "web decoy only", TTL) → reason field + confirm → status pill applied → verified only after the backend says verified → undo button with countdown.

Rules: never compute score or block success in the browser. Never `dangerouslySetInnerHTML`. Every number on screen comes from the API. Laptop screen layout is enough, no mobile.

From H18: own the deck (problem, threat model, architecture, live demo, what each label does and does not prove, limits). Use the D3COY template.
