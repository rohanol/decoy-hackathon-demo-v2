# DeceptionGraph SOC — Frontend Design Spec

Owner: M1 (Pashmee). Covers design tokens, the app shell, global states, the wording
dictionary and all seven screens.

This is the design source of truth for `frontend/`. Data shapes come from
`contracts/API.md`, `contracts/event.schema.json` and `contracts/finding.schema.json`.
Wording comes from `AGENTS.md` section 7. Thresholds and weights come from
`config/scoring.yaml` — **never hardcode them in the UI**, read them off the API response.

---

## 0. The three laws

Every decision below follows from these. If a design choice conflicts with one, the law wins.

1. **The browser never decides anything.** Score, severity, link status, whether a block
   worked — all of it arrives from the API and is displayed as received. No arithmetic on
   scores, no inferring severity from a number, no optimistic "blocked!" state.
2. **Attacker text is hostile.** Usernames, commands, paths and query strings are controlled
   by the attacker and land on our screen. Always render as plain React children. **Never**
   `dangerouslySetInnerHTML`. Attacker-controlled strings always render in the mono font
   inside a bounded container so they cannot break layout.
3. **Claim only what the evidence proves.** Every finding shows its `limitation` next to its
   `label`, at the same visual weight. Section 3 is the allowed wording list.

---

## 1. Screen inventory

The M1 prompt lists seven deliverables, but mixes screens with components. Here is the
actual route map. Seven screens, with the kill-chain bar and noise counter as components
that live inside them.

| # | Screen | Route | Primary data |
|---|---|---|---|
| 1 | Overview | `/` | `GET /api/stats/overview`, `GET /api/health` |
| 2 | Live Feed | `/events` | `GET /api/events` + `/ws/events` |
| 3 | Incident List | `/incidents` | `GET /api/incidents` |
| 4 | Incident Detail | `/incidents/:id` | `GET /api/incidents/{id}` |
| 5 | Transcript Replay | `/incidents/:id/transcript/:sessionId` | `GET /api/incidents/{id}/transcript` |
| 6 | Attack Graph | `/graph` | `GET /api/links`, `GET /api/incidents` |
| 7 | Response Center | `/response` | `GET /api/response/actions` |

The **kill-chain bar** is a component on screens 3 (compact) and 4 (full).
The **noise counter** is a component on screen 1.
The **block flow** is a modal sequence launched from screens 4 and 7.

Build order (matches the H4/H8/H12 gates): **2 → 4 → 3 → 1 → 5 → 6 → 7.**
Screen 2 is the H4 gate, so it ships first. Screen 7 is last because the block flow depends
on M2's response router existing.

---

## 2. Design tokens

Dark theme only. The demo runs on a laptop in a lit room, often mirrored to a projector, so
contrast targets are deliberately conservative: body text ≥ 7:1, secondary ≥ 4.5:1.
No mobile layout. Design to a 1440×900 canvas, degrade gracefully to 1280×800.

### 2.1 Colour — surfaces and text

| Token | Hex | Use |
|---|---|---|
| `--bg-base` | `#0B0F14` | Page background |
| `--bg-surface` | `#111822` | Cards, panels, table bodies |
| `--bg-raised` | `#1A232F` | Modals, dropdowns, hover rows, table headers |
| `--bg-inset` | `#080C11` | Terminal, code blocks, scrollable wells |
| `--border` | `#243040` | Default 1px borders, table row dividers |
| `--border-strong` | `#33465C` | Focused inputs, active cards, modal edge |
| `--text-primary` | `#E6EDF3` | Headings, values, body |
| `--text-secondary` | `#9BA9B7` | Labels, column headers, metadata |
| `--text-muted` | `#6B7A8A` | Disabled, "not observed", placeholders |
| `--accent` | `#3DA9FC` | Links, buttons, focus ring, selected state |
| `--accent-weak` | `rgba(61,169,252,0.12)` | Selected row tint, accent button hover |

### 2.2 Colour — severity

Severity comes from the API (`severity` field). The thresholds in `config/scoring.yaml`
(low 0, medium 25, high 50, critical 80) are documented here **for reference only** — the UI
reads the string, it does not compute it from the score.

| Severity | Base | Fill (12%) | Meaning |
|---|---|---|---|
| `low` | `#4A90A4` | `rgba(74,144,164,0.12)` | Probing, little progress |
| `medium` | `#D99A2B` | `rgba(217,154,43,0.12)` | Real attempt underway |
| `high` | `#E0703B` | `rgba(224,112,59,0.12)` | Got in, or exploit attempted |
| `critical` | `#D9394B` | `rgba(217,57,75,0.12)` | Data served, or confirmed cross-decoy path |

**Badge style — outlined, not solid.** 1px border in the base colour, 12% fill, text in the
base colour lightened to pass contrast. Solid fills with dark text fail at projector gamma.

```
┌──────────┐
│ CRITICAL │   border #D9394B · fill rgba(217,57,75,.12) · text #FF8A96
└──────────┘   11px, 600, letter-spacing .06em, uppercase, radius 4px, padding 2px 8px
```

Severity is **never** encoded by colour alone — the badge always carries the word. Colour
blindness, and projectors that shift hue.

### 2.3 Colour — status and semantics

| Token | Hex | Use |
|---|---|---|
| `--ok` | `#3DD68C` | Connection live, sensor healthy, action verified, link confirmed |
| `--warn` | `#D99A2B` | Reconnecting, sensor stale, preview expiring |
| `--danger` | `#D9394B` | Offline, blocked request, reject action |
| `--pending` | `#A78BFA` | Awaiting analyst decision, `pending_confirmation` findings |
| `--neutral` | `#6B7A8A` | Not observed, expired, revoked, uncounted |

`--pending` is intentionally a different hue from every severity colour. "This needs a human"
must never read as "this is severe".

### 2.4 Typography

Two faces. One rule decides which: **anything the machine produced is mono.**

**System stacks only — no webfonts.** Laptop B has no internet on the lab link
(`AGENTS.md` §6), so a Google Fonts request would hang and then silently fall back
mid-demo. JetBrains Mono is listed first in the mono stack so it gets used where it happens
to be installed locally, but nothing depends on it.

| Face | Stack | Use |
|---|---|---|
| UI | `system-ui, -apple-system, "Segoe UI", Roboto, sans-serif` | Headings, labels, prose, buttons |
| Mono | `"JetBrains Mono", ui-monospace, "SF Mono", Menlo, Consolas, monospace` | IPs, all IDs, timestamps, commands, paths, query strings, hashes, rule codes, ATT&CK codes |

The mono rule matters for credibility: when every `evt_...` and every attacker command is
visibly machine data, judges can see at a glance what came from the system versus what we
wrote.

| Role | Size / line-height / weight | Notes |
|---|---|---|
| Page title | 24 / 32 / 600 | One per screen |
| Section heading | 16 / 24 / 600 | Card headers |
| Body | 14 / 20 / 400 | |
| Label | 12 / 16 / 500 | `--text-secondary`, uppercase, `.04em` tracking |
| Micro | 11 / 14 / 500 | Badges, pills, table metadata |
| Mono data | 13 / 20 / 400 | Inline IDs, IPs, timestamps |
| Mono terminal | 13 / 22 / 400 | Transcript replay only |
| Metric | 32 / 36 / 600 | Overview counters, incident score |

### 2.5 Spacing, radius, elevation

4px base. Use only: **4, 8, 12, 16, 24, 32, 48**.

- Card padding `16px`; modal padding `24px`; table cell padding `8px 12px`
- Gap between cards `16px`; between page sections `24px`
- Radius: controls and badges `4px`, cards `8px`, modals `12px`, pills `999px`
- One shadow only, for modals: `0 16px 48px rgba(0,0,0,0.6)`. Cards use borders, not shadows.

### 2.6 Focus and motion

- Focus ring on every interactive element: `2px solid var(--accent)`, `2px` offset. Never
  remove outlines — the block flow gets operated under demo pressure and keyboard focus
  must be obvious.
- Motion is functional only: `120ms ease-out` for hover and state changes, `200ms` for modal
  entry. New rows in the live feed get a one-shot 400ms accent-left-border flash, then settle.
  No sliding, no bouncing, no spinners that outlive their request.
- Respect `prefers-reduced-motion: reduce` — drop the flash to an instant background tint.

---

## 3. Wording dictionary

`AGENTS.md` section 7 is a hard constraint, not a style preference. These strings are the
only approved phrasings. Put them in one `src/copy.ts` module so nothing drifts.

| Context | Use exactly | Never |
|---|---|---|
| SSH commands | "command submitted to emulated shell" | "executed", "ran on the host" |
| File download | "synthetic file served" | "data exfiltrated", "data stolen" |
| Web attack match | "web attack attempt" | "exploited", "vulnerability exploited" |
| Open link | "candidate link" | "same attacker", "confirmed" |
| Token reuse, pre-confirm | "strong candidate link — honeytoken reuse" | "identified", "proven" |
| Confirmed link | "analyst-confirmed link" | "same person", "attributed" |
| Successful SSH auth | "accepted by emulated shell" | "compromised", "breached" |
| Block applied | "block applied — web decoy only" | "attacker isolated", "contained", "neutralised" |
| Block verified | "verified by blocked request `evt_...`" | "attack stopped" |
| Unreached stage | "not observed" | "safe", "clear", "none" |

Every finding card renders `label` **and** `limitation`. The limitation is `--text-secondary`
at body size — smaller than the label but not a footnote. It is a feature, not a disclaimer.

Severity words are lowercase in prose ("this incident is high severity") and uppercase only
inside badges.

---

## 4. App shell

```
┌────────────────────────────────────────────────────────────────────────────────┐
│ DeceptionGraph SOC   [LIVE]        run-2026-11-01-01      ● live   12:04:31 UTC│  56px topbar
├──────────────┬─────────────────────────────────────────────────────────────────┤
│ Overview     │                                                                 │
│ Live Feed  3 │                      screen content                             │
│ Incidents  2 │                      max-width 1400, centred                    │
│ Attack Graph │                      padding 24                                 │
│ Response   1 │                                                                 │
│              │                                                                 │
│ ──────────── │                                                                 │
│ ssh-decoy ●  │                                                                 │
│ web-decoy ●  │                                                                 │
└──────────────┴─────────────────────────────────────────────────────────────────┘
   216px sidebar
```

### 4.1 Topbar — persistent, every screen

Left to right:

1. **Product name** — 14/600, `--text-primary`.
2. **Capture mode chip** — `LIVE` or `REPLAY`. Driven by the `capture_mode` on incoming
   events. `LIVE` is `--ok` outlined; `REPLAY` is `--pending` outlined. **Required on every
   screen** (PRD §8). If any event in view has `capture_mode: "replay"`, the chip reads
   `REPLAY`. If fixtures are on (`VITE_USE_FIXTURES=1`), the chip reads `FIXTURES` in
   `--warn` — so it is impossible to demo fixture data by accident.
   With no events received at all there is no capture to describe, so the chip reads
   `NO DATA` in neutral — never `LIVE`, which would be a claim we cannot back.
3. **`lab_run_id`** — mono, `--text-secondary`. Proves which run is on screen.
4. **Connection pill** — see 4.3.
5. **UTC clock** — mono, ticking. All timestamps in this app are UTC; the clock makes that
   obvious without a tooltip on every row.

### 4.2 Sidebar

Nav items with live counts fed by the WebSocket: Live Feed shows new-since-last-visit,
Incidents shows open incident count, Response shows currently applied actions. Active item
gets `--accent-weak` fill and a 2px `--accent` left border.

Below a divider, **sensor health** from `GET /api/health`: one row per sensor with a dot and
the relative time of its last event.

| Dot | Condition |
|---|---|
| `--ok` | Last event < 60s ago |
| `--warn` | 60s–5min ago — label "stale" |
| `--neutral` | `null` — label "no events yet" |
| `--danger` | `/api/health` unreachable |

This strip is the cheapest insurance in the build. When the demo misbehaves, it tells you
instantly whether the problem is the decoy, the backend or your UI.

### 4.3 Connection pill — the one piece of state that must never lie

| State | Dot | Label | Condition |
|---|---|---|---|
| Live | `--ok`, soft 2s pulse | `live` | WebSocket open |
| Reconnecting | `--warn`, blinking | `reconnecting · attempt N` | Socket closed, retrying |
| Offline | `--danger`, static | `offline — showing data from 12:03:58Z` | Retries exhausted |

Reconnect uses exponential backoff with jitter: 500ms, 1s, 2s, 4s, 8s, then every 8s.

**On reconnect, reload the REST snapshot and discard the in-memory list** (`API.md`, and
PRD AC11). Do not try to patch the gap from buffered messages. Apply WebSocket messages
only where `seq` is greater than the highest `seq` seen; drop or ignore anything lower.
Clicking the pill when offline forces a retry immediately.

---

## 5. Global states

Every screen implements all six. Judges open empty screens; a half-built empty state reads
as a broken app.

| State | Treatment |
|---|---|
| **Loading (first)** | Skeleton rows matching final layout — grey `--bg-raised` blocks, subtle shimmer. Never a centred spinner; layout must not jump. |
| **Loading (refresh)** | Keep current data, 2px `--accent` indeterminate bar under the topbar. |
| **Empty** | Centred in the card: one line of what will appear, one line of how to make it appear. "No events yet. Events appear here as soon as a decoy is touched." Never just "No data". |
| **Error** | Inline card, `--danger` left border, the API's `error.code` in mono, `error.message` as prose, and a Retry button. Never a raw stack trace, never a toast that disappears. |
| **Stale** | Data older than 60s with no live socket: `--warn` banner at the top of the card, "Showing data from 12:03:58Z — not live". |
| **Degraded** | One widget's request failed but the screen is otherwise fine: that widget alone shows the error card. Never blank the whole screen for one failed call. |

---

## 6. Screen 1 — Overview

**Route** `/` · **Data** `GET /api/stats/overview`, `GET /api/health`, `GET /api/incidents`

The screen that is on display before the demo starts and after it ends. It has one job:
make the noise-reduction argument visible in a single glance.

```
Overview                                                         run-2026-11-01-01

┌─ Noise reduction ──────────────────────────────────────────────────────────────┐
│                                                                                │
│      1,284                 2                    0                              │
│   raw events          incidents         low priority                           │
│                                                                                │
│   ████████████████████████████████████████████████████░░░░░░░                  │
│   1,284 raw events  →  2 incidents  →  0 low priority                          │
│                                                                                │
│   Deduplicated sensor records grouped by source IP and lab run.                 │
└────────────────────────────────────────────────────────────────────────────────┘

┌─ Time to first alert ──────────┐  ┌─ Findings by rule ────────────────────────┐
│                                │  │ R01 ████████ 2    R04 ██ 1                │
│        4.2 s                   │  │ R02 ████ 1        R05 ██ 1                │
│   first event → first finding  │  │ R03 ████ 1        R07 ██ 1                │
└────────────────────────────────┘  └───────────────────────────────────────────┘

┌─ Active incidents ─────────────────────────────────────────────────────────────┐
│ 192.168.77.10   [CRITICAL] 100   recon credential exploit post-access data     │
│ 192.168.77.11   [LOW]        5   recon · · · ·                                 │
└────────────────────────────────────────────────────────────────────────────────┘
```

**Noise counter** — three metrics at 32px, the exact sentence
`N raw events → M incidents, K low priority` beneath, then the bar. The bar is proportional
and purely decorative reinforcement; the numbers are the truth. `low_priority_incidents`
means incidents scoring below `low_priority_below` (25). Tooltip on "low priority":
*"Scored below the noise threshold set in scoring.yaml."*

**Time to first alert** — `first_alert_seconds`, one decimal, "s" in `--text-secondary`.
If `null`, show `—` with "no findings yet". Do not show `0.0`.

**Findings by rule** — horizontal bars from `findings_by_rule`. Rule code in mono, count at
the end. Fixed order R01, R02, R03, R04, R05, R07, R08, R09. **There is no R06** — do not
render a slot for it. Rules with zero count render a dim empty track, so the set of possible
rules is always visible. Clicking a bar goes to `/incidents` filtered by that rule.

**Active incidents** — compact rows: IP (mono), severity badge, score, and the compact
kill-chain strip. Whole row navigates to the incident.

---

## 7. Screen 2 — Live Feed · the H4 gate

**Route** `/events` · **Data** `GET /api/events?limit=200` then `/ws/events`

This is the first screen to exist and the one that passes G2 at H4: a real SSH event from
Kali, visible, with its event ID. Design it so a single event looks *intentional*, not like
an empty table with one row in it.

```
Live Feed                                                      ● live    [ Pause ]

[ All sensors ▾ ] [ All event types ▾ ]  src_ip ⌕ _________        214 events

┌──────────┬──────────────┬──────────────────┬───────────────┬────────────────────┐
│ TIME UTC │ SENSOR       │ EVENT            │ SOURCE        │ DETAIL             │
├──────────┼──────────────┼──────────────────┼───────────────┼────────────────────┤
┃ 04:31:30 │ web-decoy-01 │ ◆ synthetic file │ 192.168.77.10 │ customer_data.csv  │
┃          │              │   access  served │               │ 3,728 B            │
│          │              │                  │               │ evt_7f3a · inc_01  │
├──────────┼──────────────┼──────────────────┼───────────────┼────────────────────┤
│ 04:31:20 │ web-decoy-01 │ ◆ http request   │ 192.168.77.10 │ GET /search        │
│          │              │   500 fake_error │               │ q=x' UNION SELECT… │
│          │              │                  │               │ evt_6b21 · inc_01  │
└──────────┴──────────────┴──────────────────┴───────────────┴────────────────────┘
```

### 7.1 Behaviour

- **Newest on top.** Prepend on WebSocket `type: "event"`.
- **New-row flash**: 400ms `--accent` left border, then fade to the row's normal state.
- **Pause button.** Essential. During the demo rows arrive faster than anyone can read, and
  while paused you can actually point at one. Paused shows a `--warn` pill
  `paused · N new` and a Resume button. Pausing only freezes rendering; the buffer keeps
  filling and flushes on resume.
- **Cap the DOM at 500 rows.** Trim the oldest. Footer: "showing newest 500 of 1,284".
- **Filters** by sensor, event type and src_ip substring. Client-side over the loaded
  window, and the active filter is stated above the table so nobody misreads a filtered
  view as the whole truth.
- **Row click** opens the raw event drawer (7.4).

### 7.2 Event type presentation

Each of the eight `event_type` values gets a glyph and a colour. Glyph plus text label
always — never colour alone.

| `event_type` | Glyph | Colour | Label shown |
|---|---|---|---|
| `connection_open` | `○` | `--text-secondary` | connection open |
| `auth_failure` | `✕` | `--warn` | auth failure |
| `auth_success` | `✓` | `--danger` | auth accepted |
| `command_input` | `▸` | `--accent` | command submitted |
| `connection_close` | `●` | `--text-muted` | connection close |
| `http_request` | `◆` | `--accent` | http request |
| `synthetic_file_access` | `◆` | `--danger` | synthetic file access |
| `blocked_request` | `⊘` | `--ok` | blocked request |

Two deliberate inversions, worth being able to explain:

- `auth_success` is **red**, not green. A successful login to a decoy is the bad news.
- `blocked_request` is **green**. It means our block is working.

### 7.3 The detail column

One or two lines, derived from `attributes`, all in mono, truncated with ellipsis and the
full value in the drawer:

- `auth_failure` / `auth_success` → `username=dg_demo`
- `command_input` → the command, max 60 chars
- `http_request` → `METHOD path` then `query_redacted`, max 60 chars
- `synthetic_file_access` → `asset_id` then `size_bytes` and `outcome`
- `blocked_request` → `status 403 · act_01`

Beneath, always: `event_id` and, if present, `incident_id` as a link. Those IDs are how the
H4 gate is demonstrated — they are not decoration.

**Never render `password_sha256` or `sha256` in a row.** Hashes go in the drawer only,
truncated to 12 chars with a copy button.

### 7.4 Raw event drawer

Right-side panel, 480px, slides in 200ms. Header: event type, sensor, UTC timestamp,
`event_id` with copy button. Body: a two-column key/value table of every schema field,
then `attributes` expanded. Footer links: "view incident", "view transcript" when
`session_id` is present.

Attacker-controlled values (`command`, `path`, `query_redacted`, `user_agent`, `username`)
render in a `--bg-inset` well with `white-space: pre-wrap; overflow-wrap: anywhere` and a
max height of 160px. Bounded, scrollable, never breaking layout no matter what gets sent.

---

## 8. Screen 3 — Incident List

**Route** `/incidents` · **Data** `GET /api/incidents`

```
Incidents                                                              2 incidents

┌────────────────────────────────────────────────────────────────────────────────┐
│ ┃ [CRITICAL]  100   192.168.77.10                           42 events         │
│ ┃                                                                              │
│ ┃ ▓▓▓▓▓▓ recon  ▓▓▓▓▓▓ cred  ▓▓▓▓▓▓ exploit  ▓▓▓▓▓▓ post  ▓▓▓▓▓▓ data         │
│ ┃                                                                              │
│ ┃ inc_01 · run-01 · first 04:30:00Z · last 04:32:30Z · 2m 30s                 │
├────────────────────────────────────────────────────────────────────────────────┤
│ ┃ [LOW]         5   192.168.77.11                            9 events          │
│ ┃ ░░░░░░ recon  ░░░░░░ cred  ░░░░░░ exploit  ░░░░░░ post  ░░░░░░ data         │
│ ┃ inc_02 · run-01 · first 04:28:10Z · last 04:28:55Z · 45s                    │
└────────────────────────────────────────────────────────────────────────────────┘
```

Cards, not a dense table — there will only ever be one to three incidents in this lab, and
cards let the kill-chain strip breathe. Scanning those silhouettes down the page is the
point: how far each source got, side by side.

Each card: 4px left border in the severity colour, severity badge, score at 20/600, src_ip
in mono at 16px, event count, the compact kill-chain strip, then a mono metadata line.
The whole card is the link into the incident.

Sort newest `last_seen` first. An incident updated by a WebSocket `type: "incident"` message
replaces the one on screen and gets a 1.2s `--accent` flash.

**No rule chips and no "awaiting decision" flag, by necessity.** `IncidentSummary` carries
no findings, and `Link` carries no `incident_id`, so neither has an honest source at this
endpoint. The alternatives were N+1 fetching every incident's detail or inventing the data;
both are worse than a slightly thinner card. Open question 2 asks Rohan for
`findings_by_rule` and `open_link_count` on `IncidentSummary` — if they arrive, add the
chips back as mono micro text in `--bg-raised`, with uncounted rules at 60% opacity and a
dashed border, plus an `--pending` flag for open links.

The compact strip uses the identical five-column grid as the full bar (§9.2) so silhouettes
stay comparable between cards and against the incident page.

---

## 9. Screen 4 — Incident Detail · the centrepiece

**Route** `/incidents/:id` · **Data** `GET /api/incidents/{id}`

The screen that will be on the projector for most of the demo. Two columns: evidence on the
left, machinery on the right.

```
← Incidents                                                      [ Export ] [ Block ]

192.168.77.10                                               [CRITICAL]    100 / 100
inc_01 · run-2026-11-01-01 · 42 events · 04:30:00Z → 04:32:30Z · 2m 30s

┌─ Kill chain ───────────────────────────────────────────────────────────────────┐
│  ▓▓▓▓▓▓▓▓▓    ▓▓▓▓▓▓▓▓▓    ▓▓▓▓▓▓▓▓▓    ▓▓▓▓▓▓▓▓▓    ▓▓▓▓▓▓▓▓▓                 │
│  recon        credential   exploit      post-access  data access               │
│  R08          R01          R07          R02 R03      R04                       │
└────────────────────────────────────────────────────────────────────────────────┘

┌─ Summary ──────────────────────────────┐ ┌─ Score breakdown ───────────────────┐
│ [rules]                                │ │ RULE  PTS  COUNTED                  │
│ Five SSH password attempts from         │ │ R01    25  ✓ first R01              │
│ 192.168.77.10 against dg_demo, then an  │ │ R02    15  ✓ first R02              │
│ accepted login. Three commands were     │ │ R03    10  ✓ first R03              │
│ submitted to the emulated shell. A      │ │ R04    30  ✓ first R04              │
│ synthetic file was served.              │ │ R05    15  ✓ link confirmed         │
│                                         │ │ R07    15  ✓ first R07              │
│ cited: evt_1a2b evt_3c4d evt_5e6f       │ │ R08     5  ✓ first R08              │
└────────────────────────────────────────┘ │ R09    15  ✓ link confirmed         │
                                           │ ─────────────────────────────────── │
┌─ Findings (7) ─────────────────────────┐ │ raw 130 · capped at 100 → 100       │
│ ┌────────────────────────────────────┐ │ └─────────────────────────────────────┘
│ │ R01  credential_attack   T1110.001 │ │
│ │ Repeated SSH password guessing     │ │ ┌─ Cross-decoy links ────────────────┐
│ │ (5 failures in 60 s)               │ │ │ ssh-decoy-01 ⇢ web-decoy-01        │
│ │ Does not show the account was      │ │ │ analyst-confirmed link              │
│ │ compromised.                       │ │ │ honeytoken tok_portal_01            │
│ │ evidence: evt_1a2b evt_3c4d +3     │ │ │ "same trail, confirmed" 04:31:55Z  │
│ │                             25 pts │ │ └─────────────────────────────────────┘
│ └────────────────────────────────────┘ │
│ ┌────────────────────────────────────┐ │ ┌─ Sessions ─────────────────────────┐
│ │ R09  none              ⚑ pending   │ │ │ sess01  ssh-decoy-01  3 cmds  ▸    │
│ │ Honeytoken presented on the other  │ │ │ hyd0    ssh-decoy-01  0 cmds       │
│ │ sensor                             │ │ └─────────────────────────────────────┘
│ │ Awaiting analyst confirmation.     │ │
│ │                              0 pts │ │ ┌─ Response ─────────────────────────┐
│ └────────────────────────────────────┘ │ │ no action applied                   │
└────────────────────────────────────────┘ │ [ Preview block ]                   │
                                           └─────────────────────────────────────┘
```

### 9.1 Header

`src_ip` as the page title in mono at 24px — the IP is the subject of this page, not the
incident ID. Beneath it, a metadata line: `incident_id`, `lab_run_id`, event count,
first → last seen, duration.

Right side: the score at 32/600 in the severity colour, with the severity badge above it.

**Built as the bare number, not `100 / 100`.** The denominator would have to be the cap from
`config/scoring.yaml`, which the API does not expose — hardcoding `100` means the UI starts
lying the day M3 changes it. The cap still gets shown where it actually does something, in
the breakdown footer (§9.3). Open question 7 asks Rohan to expose `score_cap`; if he does,
restore the denominator.

Buttons: **Export** (`GET /api/incidents/{id}/export`, downloads; tooltip "JSON export,
password hashes excluded") and **Block** (opens the block flow, §12).

### 9.2 Kill-chain bar

Five fixed segments in fixed order: `recon`, `credential_attack`, `exploit_attempt`,
`post_access`, `data_access`. Always all five, always this order — the shape of the bar is
the at-a-glance read, so it must not reflow.

Observed (stage present in `stages_observed`): filled with the incident's severity colour,
the stage name in `--text-primary`, and the rule codes that evidence it beneath.

Unobserved: `--bg-raised` fill, 1px dashed `--border`, name in `--text-muted`, and the
literal words **"not observed"** where the rule codes would be. Not "safe", not "clear".

Derive the rule codes per stage by grouping `findings` on their `stage`. Findings with
`stage: "none"` (R05, R09) belong to no segment — they appear in the links panel instead.

Clicking a segment filters the findings list to that stage.

### 9.3 Score breakdown

Straight from `score_breakdown`: `rule_id`, `points`, `counted` and `reason`. Counted rows
show `✓` in `--ok` and the reason in `--text-secondary`. Uncounted rows render at 60%
opacity with `—` and their reason ("R01 already counted", "awaiting link confirmation").

Footer line: when the summed points exceed 100, show `raw 130 · capped at 100 → 100`. If
they do not exceed it, just show the total. Showing the cap doing its job is a credibility
detail — it proves the score is bounded by design.

**Do not sum the points yourself to produce the score.** Display the API's `score`. The raw
sum is shown only as a transparency aid next to the cap note, labelled `raw`.

### 9.4 Finding cards

Header row: `rule_id` (mono, bold), `stage` chip, `technique_ids` as mono chips linking to
`https://attack.mitre.org/techniques/T1110/001/` (new tab, `rel="noopener noreferrer"`),
and for R07 the `web_attack_class` values as `--warn` chips (`sqli`, `xss`, `lfi`, `rfi`,
`cmd_injection`).

Body: `label` at 14/500 `--text-primary`, then `limitation` at 14/400 `--text-secondary`
prefixed with a small `ⓘ`. The limitation is **always visible** — never behind a tooltip or
an accordion.

Footer: `evidence_event_ids` as mono chips. Each one is a button that opens that raw event
in the drawer from §7.4. Show the first three, then `+N` to expand. **Every evidence ID is
clickable** — this is the "evidence-linked" claim in the project's one-line pitch, and a
judge will click one.

Right-aligned: `points`. When `pending_confirmation` is true, show `0 pts`, an `--pending`
`⚑ pending` chip in the header, a 1px dashed `--pending` left border, and
"Awaiting analyst confirmation." as the limitation line.

### 9.5 Links panel

One row per link: `from_sensor ⇢ to_sensor`, the status phrase from the wording dictionary,
the `basis` in mono, and for decided links the `rationale` in quotes with `decided_at`.

| `status` | `kind` | Border | Phrase |
|---|---|---|---|
| `open` | `candidate` | 1px dashed `--pending` | candidate link |
| `open` | `strong_candidate` | 2px dashed `--pending` | strong candidate link — honeytoken reuse |
| `confirmed` | any | 2px solid `--ok` | analyst-confirmed link |
| `rejected` | any | 1px solid `--neutral`, 60% opacity | link rejected by analyst |

Open links get **Confirm** and **Reject** buttons, which open the decision modal (§11.1).
This mirrors the graph edge styling exactly, so the two screens teach each other.

### 9.6 Summary panel

`summary.text` as prose. A source chip: `[rules]` in `--neutral`, or `[llm]` in `--pending`
if an LLM summary is ever added. Beneath, `cited_event_ids` as clickable mono chips.

If `summary.source` is not `"rules"`, prepend the banner "Generated text — all claims cite
the event IDs below." The rule-based summary is the default and needs no such caveat.

### 9.7 Sessions panel

One row per session: `session_id` (mono), `sensor_id`, `started_at`, command count. Rows
with `commands > 0` get a `▸ Replay` button to screen 5. Rows with zero commands are dimmed
and not clickable — brute-force attempts never opened a shell, so there is nothing to replay.

### 9.8 Response panel

Mirrors `active_block`. When `null`: "no action applied" plus the **Preview block** button.
When present: the action card from §13.2 inline, with its status pill and countdown.

---

## 10. Screen 5 — Transcript Replay

**Route** `/incidents/:id/transcript/:sessionId` ·
**Data** `GET /api/incidents/{id}/transcript?session_id=`

```
← inc_01                            Session sess01 · ssh-decoy-01 · 3 commands

┌────────────────────────────────────────────────────────────────────────────────┐
│ ⚠ Commands submitted to an emulated shell. Nothing executed on a real host.    │
├────────────────────────────────────────────────────────────────────────────────┤
│                                                                                │
│  04:30:20Z   ✕  login failed    dg_demo                            evt_1a2b    │
│  04:30:22Z   ✓  login accepted  dg_demo                            evt_3c4d    │
│  04:30:25Z   ▸  dg_demo@srv-01:~$ whoami                           evt_5e6f    │
│  04:30:27Z   ▸  dg_demo@srv-01:~$ ls -la                           evt_7a8b    │
│▌ 04:30:31Z   ▸  dg_demo@srv-01:~$ cat notes.txt                    evt_9c0d    │
│                                                                                │
│  04:30:40Z   ●  connection closed                                  evt_1e2f    │
│                                                                                │
├────────────────────────────────────────────────────────────────────────────────┤
│ [ ⏮ ] [ ◀ ] [ ▶ Play ] [ ▶▶ ] [ ⏭ ]      step 5 / 6      speed [ 1× ▾ ]        │
└────────────────────────────────────────────────────────────────────────────────┘
```

**The banner is mandatory and non-dismissible.** It is the single most important honesty
statement in the UI, and it sits above the content, not below it.

Terminal styling: `--bg-inset`, mono 13/22, generous row padding. It should feel like a
terminal without pretending to be a live one.

Line kinds from the API (`login_failed`, `login_ok`, `command`, `close`) reuse the glyphs
and colours from §7.2. `command` lines render a dim `--text-muted` prompt prefix before the mono `text` — it reads
as a shell session while keeping the attacker's text visually separate from our chrome.
Never interpret or syntax-highlight the command. Render the string as-is.

**The prompt is `<user>@ssh-decoy-01:~$`, built from the `login_ok` line's username and the
real sensor id** — not an invented hostname like `srv-01`. The host genuinely is the decoy,
so there is no reason to make one up, and a fabricated hostname on screen is the kind of
small fiction that costs credibility when a judge looks closely. With no accepted login in
the session, the prefix falls back to a bare `$`.

Every line shows its UTC timestamp (left, `--text-secondary`) and its `event_id` (right,
clickable to the drawer).

**Replay controls** — this is a *stepper*, not a video:

- Lines after the current step are hidden, not greyed. The reveal is the point.
- Current line gets a 2px `--accent` left bar.
- `▶ Play` auto-advances using the real gaps between `occurred_at` values, clamped to
  400ms–2s per step so the demo never stalls on a long pause. Speed selector 0.5× / 1× / 2×.
- Keyboard: `←` `→` step, `Space` play/pause, `Home` `End` jump. Judges hand the laptop back
  and forth; keyboard control reads as competence.
- Default state on open: **fully revealed, paused at the end.** Someone arriving from a
  finding's evidence link wants to see everything. The stepper is opt-in via `⏮`.

If `lines` is empty: "No commands recorded for this session." plus a note that brute-force
sessions never reached a shell.

---

## 11. Screen 6 — Attack Graph

**Route** `/graph` · **Data** `GET /api/links`, `GET /api/incidents`

```
Attack Graph                                    [ All incidents ▾ ]   1 open link

┌────────────────────────────────────────────────────────────────────────────────┐
│                                                                                │
│                        ┌──────────────────┐                                    │
│                   ╭────┤  ssh-decoy-01    │                                    │
│                   │    │  SSH decoy       │                                    │
│   ┌────────────┐  │    │  18 events       │                                    │
│   │192.168.77.10│──╯    └────────┬─────────┘                                   │
│   │  [CRITICAL]│               ║ │                                             │
│   │  100       │               ║ │ tok_portal_01                               │
│   │  42 events │               ║ │                                             │
│   └────────────┘  ╮    ┌───────┴─────────┐                                     │
│                   ╰────┤  web-decoy-01   │                                     │
│                        │  Web decoy      │                                     │
│                        │  24 events      │                                     │
│                        └─────────────────┘                                     │
│                                                                                │
│  ─── observed traffic    ╌╌╌ candidate    ═══ analyst-confirmed                │
└────────────────────────────────────────────────────────────────────────────────┘
```

Library: **React Flow**, pinned. Nothing heavier (`AGENTS.md` §9 — no new heavy deps).

Layout is **fixed, not force-directed**: attacker node left-centre, `ssh-decoy-01` upper
right, `web-decoy-01` lower right. Three nodes, deterministic positions. A physics
simulation that jiggles under a projector helps nobody, and it must look identical in every
rehearsal. Pan and zoom on, with a Reset view button.

### 11.1 Nodes

**Attacker node** — `src_ip` in mono 16px, severity badge, score, event count. 2px border in
the severity colour. One per incident in view.

**Sensor nodes** — `sensor_id` in mono, a human label ("SSH decoy" / "Web decoy"), event
count from this source, and a health dot matching the sidebar. `--bg-raised`, 1px
`--border`.

Clicking an attacker node goes to its incident. Clicking a sensor node goes to the live feed
filtered by that sensor.

### 11.2 Edges — the thing judges look at

| Meaning | Style | Label |
|---|---|---|
| Observed traffic (IP → sensor) | 1px solid `--text-muted` | event count |
| `candidate` link | 2px dashed `--pending` | "candidate" |
| `strong_candidate` link | 3px dashed `--pending` | "candidate · tok_portal_01" |
| `confirmed` link | 3px solid `--ok` | "confirmed" |
| `rejected` link | 1px solid `--neutral`, 40% opacity | "rejected" |

The dashed → solid transition on confirm is the visual climax of the demo. Animate it over
400ms (dash offset to zero, colour `--pending` → `--ok`, with a brief outer glow), and
respect `prefers-reduced-motion` by switching instantly.

Honeytoken edges carry the `honeytoken_id` in the label, because "they reused our planted
credential" is the strongest claim the system makes and it should be legible without a click.

A persistent legend sits bottom-left. Judges should not have to ask what dashed means.

### 11.3 Link decision modal

Clicking an **open** edge opens it:

```
┌─ Confirm cross-decoy link ─────────────────────────────┐
│                                                        │
│ ssh-decoy-01  ⇢  web-decoy-01                          │
│ basis: honeytoken tok_portal_01                         │
│ lnk_01                                                 │
│                                                        │
│ evidence                                               │
│   from  evt_9c0d   04:30:31Z  cat notes.txt            │
│   to    evt_2b3c   04:31:10Z  POST /login svc_portal   │
│                                                        │
│ Confirming makes R05 count (+15), and R09 (+15)        │
│ because this is a strong candidate.                    │
│                                                        │
│ Rationale (required, min 5 characters)                 │
│ ┌────────────────────────────────────────────────────┐ │
│ │                                                    │ │
│ └────────────────────────────────────────────────────┘ │
│ A confirmed link means the same source followed our    │
│ planted trail. It does not identify a person.          │
│                                                        │
│          [ Cancel ]  [ Reject ]  [ Confirm link ]      │
└────────────────────────────────────────────────────────┘
```

- `POST /api/links/{link_id}/decision` with `{decision, rationale}`.
- Both buttons disabled until the rationale reaches 5 characters, with a live counter.
  Enforce the minimum in the UI so the analyst never meets a server-side rejection mid-demo.
- Show both evidence events inline with their IDs and a one-line detail. The analyst is
  making a judgement call; the judgement needs its evidence on the same surface.
- The consequence sentence names **which rules** confirming makes count, without point
  values: a pending rule's `score_breakdown` row reports `points: 0`, so the UI has no
  honest source for "+15" and will not invent one. Open question 8 asks whether pending rows
  can carry their would-be points; until then the analyst sees the real delta when the score
  updates. Phrase it as a consequence, not a recommendation — the UI must not nudge toward
  confirming.
- The closing caveat is mandatory, straight from `demo_p3.md`.
- A decision is reversible: a decided link reopens this modal pre-filled with the previous
  rationale, and the primary button reads "Change decision".
- While in flight, buttons show a spinner and disable. On success, close and let the
  WebSocket `type: "link"` message drive the edge update — **do not** optimistically restyle
  the edge. Law 1.

---

## 12. Screen 7 — Response Center

**Route** `/response` · **Data** `GET /api/response/actions`

```
Response Center                                               1 active action

┌─ Active ───────────────────────────────────────────────────────────────────────┐
│ ┃ 192.168.77.10          [ VERIFIED ]                          01:43 remaining │
│ ┃ scope: web-decoy-01 only · ttl 120 s · act_01                                │
│ ┃ reason: "demo containment"                                                   │
│ ┃ applied 04:32:10Z · verified by evt_4d5e                                     │
│ ┃ ████████████████████████████░░░░░░░░░                                        │
│ ┃                                                      [ Undo block ]          │
└────────────────────────────────────────────────────────────────────────────────┘

┌─ History ──────────────────────────────────────────────────────────────────────┐
│ 192.168.77.10   [REVOKED]   act_00   "test"    04:20:00Z → revoked 04:21:30Z   │
└────────────────────────────────────────────────────────────────────────────────┘
```

Active actions (`applied`, `verified`) on top as full cards; terminal ones (`expired`,
`revoked`) in a compact history table.

### 12.1 Status pills — the honesty-critical bit

| `status` | Pill | Label | Means |
|---|---|---|---|
| `applied` | `--warn` outlined | `APPLIED` | Block written. **Not yet proven to work.** |
| `verified` | `--ok` solid-ish | `VERIFIED` | A `blocked_request` event arrived with this `block_action_id`. |
| `expired` | `--neutral` | `EXPIRED` | TTL ran out. |
| `revoked` | `--neutral` | `REVOKED` | Analyst undid it. |

**`VERIFIED` appears only when the API says `verified`.** Never infer it, never show it
optimistically, never show it because the request succeeded. The distinction between "we
wrote a blocklist entry" and "we observed the block rejecting a request" is exactly the kind
of rigour this project is being judged on. The verified card shows
`verified by evt_4d5e` as a clickable chip so the claim is checkable.

The countdown is computed from `until` against the client clock — the only exception to
"no computation in the browser", and it is cosmetic. When it hits zero, **re-fetch**; do not
flip the status to expired yourself.

Progress bar: `--ok` while over 30s remaining, `--warn` under 30s.

---

## 13. The block flow

Launched from the incident detail Block button or the Response Center. Three steps, and the
friction is deliberate — a one-click block is a liability, not a feature.

### 13.1 Step 1 — Preview

`POST /api/response/preview` with `{incident_id, ttl_seconds: 120}`.

```
┌─ Preview block ────────────────────────────────────────┐
│                                                        │
│ target        192.168.77.10                            │
│ scope         web-decoy-01 only                        │
│ duration      120 s                                    │
│ preview       pre_7a3f · expires in 0:52               │
│                                                        │
│ ⚠ This blocks the web decoy only. The SSH decoy stays  │
│   reachable. This does not isolate the host.           │
│                                                        │
│                      [ Cancel ]  [ Continue ]          │
└────────────────────────────────────────────────────────┘
```

Every value is read from the preview **response**, not from what we sent. If the backend
returns a different target or scope than expected, we show the backend's version.

The 60s preview expiry runs as a live countdown. On expiry the modal disables Continue and
offers "Preview expired — request a new one". Under 15s the countdown turns `--warn`.

A 400 (target not an allowed lab IP) renders the error inline with the API's
`error.message` and no Continue button. This path exists because `AGENTS.md` §6 forbids
blocking `192.168.77.20`, `127.0.0.1` or any range — and demonstrating that the guard rail
*works* is worth more than hiding it.

### 13.2 Step 2 — Approve

`POST /api/response/apply` with `{preview_id, reason, confirm: true}`.

```
┌─ Approve block ────────────────────────────────────────┐
│ 192.168.77.10 · web-decoy-01 only · 120 s              │
│ preview expires in 0:38                                │
│                                                        │
│ Reason (required, min 5 characters)                    │
│ ┌────────────────────────────────────────────────────┐ │
│ │ demo containment                                   │ │
│ └────────────────────────────────────────────────────┘ │
│ Recorded in the action history.                        │
│                                                        │
│ ☑ I understand this blocks the web decoy only          │
│                                                        │
│                 [ Back ]  [ Apply block ]              │
└────────────────────────────────────────────────────────┘
```

Apply stays disabled until the reason reaches 5 characters **and** the checkbox is ticked.
The checkbox is not bureaucracy — it is the scope claim, acknowledged by the operator, and
it is a good thing to point at when a judge asks about overreach.

Autofocus the reason field. During the demo this is typed under pressure.

### 13.3 Step 3 — Result

On success the modal becomes a result panel: `action_id`, `APPLIED` pill, `until`, and the
line **"Applied. Waiting for a blocked request to verify."**

It stays open and watches for the WebSocket `type: "action"` message. When status becomes
`verified`, the pill flips to `VERIFIED` with the `verified_by_event_id` chip and a 400ms
`--ok` glow. That moment is demo step 8 — it deserves to be visible without navigating.

Then: **Undo block** (`POST /api/response/{action_id}/revoke`) and **Done**.

Undo asks for no confirmation. Making the safe, reversing action friction-free while the
dangerous action takes three steps is the right asymmetry.

### 13.4 Failure handling

Any step failing shows the API's `error.code` in mono and `error.message` as prose, keeps the
modal open, and leaves a working Back button. Never close the modal on error — mid-demo, a
vanished modal looks like a crash. Never retry apply automatically: it is a state-changing
call, and a double block is a confusing thing to explain on stage.

---

## 14. Fixtures and the demo-path guard

`VITE_USE_FIXTURES=1` loads `contracts/examples/events_p3.json` through a mock layer that
emulates the REST routes and replays events over a fake socket on a timer. This is how
screens 1–7 get built before M3's backend exists.

Hard requirements:

- The topbar chip reads **`FIXTURES`** in `--warn` whenever the flag is on. Loud, unmissable,
  on every screen.
- The flag defaults to **off**. The demo path must never be one stale `.env.local` away from
  showing fake data (`AGENTS.md` §9: "Fixtures only in dev mode. Nothing fake on the demo
  path.").
- `capture_mode` on fixture events is `"replay"`, so the chip would read `REPLAY` even if the
  fixture flag check were somehow bypassed. Two independent signals.

The fixture file covers: 6 `auth_failure`, 1 `auth_success`, 3 `command_input`,
1 `connection_close`, 7 `connection_open`, 3 `http_request`, 1 `synthetic_file_access`,
1 `blocked_request`. That exercises every event type and the whole demo narrative. Findings,
incidents, links and actions are **not** in the fixture file — mock those from the shapes in
`API.md` until the backend is live.

---

## 15. Component inventory

Primitives, built once:

`Badge` (severity) · `Pill` (status) · `Chip` (rule, technique, event ID, attack class) ·
`Card` · `MetricTile` · `Table` · `Modal` · `Drawer` · `Button` (primary/secondary/danger/ghost) ·
`TextField` with character minimum · `Checkbox` · `Countdown` · `SkeletonRow` ·
`ErrorCard` · `EmptyState` · `ConnectionPill` · `SensorHealthRow` · `MonoValue` ·
`AttackerText` (the bounded, wrapped, escaped well for hostile strings)

Domain components:

`KillChainBar` (compact / full) · `ScoreBreakdownTable` · `FindingCard` · `EventRow` ·
`RawEventDrawer` · `LinkRow` · `LinkDecisionModal` · `NoiseCounter` · `TranscriptLine` ·
`TranscriptPlayer` · `GraphCanvas` · `ActionCard` · `BlockFlowModal` · `SessionRow`

---

## 16. Open questions for Rohan (M3)

Ask these in the group chat early — all are small, and each one blocks a panel.

1. `GET /api/events` has no `src_ip` filter in `API.md`. Client-side filtering over the
   loaded window is fine for the lab's volumes — confirming that is not a problem.
2. **Blocking two features on the incident list.** `IncidentSummary` carries no findings and
   no link info, and `Link` has no `incident_id`, so the list cannot show rule chips or an
   "N links awaiting decision" flag without fetching every incident's detail. Could
   `IncidentSummary` carry `findings_by_rule` (same shape as the one in `/api/stats/overview`)
   and `open_link_count`? Alternatively, adding `incident_id` to `Link` would solve the
   second half on its own.
3. Does `/ws/events` emit `type: "action"` for response status changes, including the
   `applied → verified` transition? §13.3 depends on it. If not, the result panel polls
   `GET /api/response/actions` every 2s while open.
4. The attack graph wants per-sensor event counts per incident. Deriving them from
   `GET /api/events?incident_id=` is fine; just confirming there is no cheaper field.
5. Is `score_breakdown` guaranteed to list every rule that fired, including uncounted ones
   with `counted: false`? §9.3 renders both, and uncounted rows are a credibility feature.
6. Does `GET /api/health` include `lab_run_id`? The topbar currently takes it from events,
   which is empty before the first event arrives.
7. Can the incident carry `score_cap` (the `cap` from `config/scoring.yaml`)? Without it the
   header shows a bare score rather than `100 / 100`, because hardcoding the denominator
   means the UI lies if the cap ever changes.
8. For a rule awaiting confirmation, does its `score_breakdown` row report `points: 0`, or
   the points it *would* contribute? If the latter, the link decision modal can tell the
   analyst the exact delta before they decide, which is strictly better.

None of these block the H4 gate. Build screen 2 on fixtures now.

---

## 17. Accessibility and demo-robustness checklist

- Severity and status never communicated by colour alone — always a word too
- All text ≥ 4.5:1 against its background; body text ≥ 7:1
- Full keyboard path through the link decision modal and the block flow
- Visible focus ring everywhere; focus trapped in modals; `Esc` closes (except mid-apply)
- `prefers-reduced-motion` honoured for the edge-confirm animation and the row flash
- No layout shift when a long attacker string arrives — `AttackerText` is always bounded
- Every screen legible at 1280×800 and at 150% browser zoom
- Tested once against a projector before H20: dark theme gamma is the usual surprise
