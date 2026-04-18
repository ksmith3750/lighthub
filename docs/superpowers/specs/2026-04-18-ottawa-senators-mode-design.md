# Ottawa Senators Mode — Design Spec

**Date:** 2026-04-18  
**Status:** Approved

---

## Overview

A persistent "Senators Mode" that turns all reachable lights red while an Ottawa Senators game is in progress, flashes on a Senators goal, dims briefly on an opponent goal, and auto-deactivates when the game ends.

---

## Backend

### State

An in-memory dict tracks all runtime state:

```python
senators_state = {
    "active": False,
    "game_id": None,          # NHL game ID string, or None
    "senators_score": 0,
    "opponent_score": 0,
    "opponent_name": None,    # e.g. "Toronto Maple Leafs"
    "team_logo": None,        # URL from NHL API response
    "monitor_task": None,     # asyncio.Task reference
}
```

This state is not persisted to disk. If the server restarts, Senators Mode is off.

### NHL Data Source

Free public NHL Stats API — no authentication required.

- **Today's schedule / live score:** `https://api-web.nhle.com/v1/scoreboard/OTT/now`
- The response includes `teamLogo` URLs for both teams, current score, game state (`LIVE`, `FINAL`, `PRE`, etc.)

### Polling Loop

On activation, a background `asyncio.Task` is spawned:

1. Call the NHL API to find today's OTT game.
2. If no game found: set `game_id = None`, skip polling (mode stays active for red theme only).
3. If game found: store `game_id`, begin polling every **15 seconds**.
4. Each poll: compare current score to `senators_state` scores.
   - **Senators score increased** → cancel any in-progress flash task, spawn goal flash task.
   - **Opponent score increased** → spawn opponent dim task.
   - **Game state == `FINAL`** → auto-deactivate mode.
5. Update `senators_state` scores after each comparison.

### Light Sequences

All sequences operate only on devices where `reachable == True`.

**Senators Mode activation (red theme):**
- All reachable devices: `{on: True, brightness: 100, color: {r:255, g:0, b:0}}`
- Kasa plugs (no color): `{on: True, brightness: 100}`
- Runs via existing `send_command()` for each device concurrently with `asyncio.gather()`

**Goal flash (Senators score):**
- Background asyncio task, 10 iterations:
  - Lights on: `{on: True, brightness: 100, color: {r:255, g:0, b:0}}` → wait 300ms
  - Lights off: `{on: False}` → wait 300ms
- After loop: restore all lights to Senators red theme
- If a second goal arrives mid-flash: cancel current task, restart flash

**Opponent goal dim:**
- All reachable lights: `{brightness: 10}` → wait 3 seconds
- Restore all lights to Senators red theme
- Runs as a background asyncio task

**Deactivation:**
- Cancel monitor task and any in-progress flash/dim task
- Lights left as-is (no automatic restore to pre-Senators state)

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/senators/activate` | Start Senators Mode, spawn polling task, set lights red |
| `POST` | `/api/senators/deactivate` | Stop Senators Mode, cancel tasks |
| `GET` | `/api/senators/status` | Return current `senators_state` (excluding task reference) |

`/api/senators/status` response shape:

```json
{
  "active": true,
  "game_id": "2025020123",
  "senators_score": 2,
  "opponent_score": 1,
  "opponent_name": "Toronto Maple Leafs",
  "team_logo": "https://..."
}
```

---

## Frontend

### Scenes Page Card

A "Ottawa Senators" card is added to the Scenes page alongside existing scene buttons.

- Displays the Senators logo (URL sourced from NHL API response, stored in `senators_state.team_logo`; falls back to a text "OTT" badge if no game/logo available)
- Toggle button: **"Activate"** / **"Deactivate"** (not a one-click scene fire like other scenes)
- When active:
  - Card border highlighted in Senators red (`#DA1A32`)
  - Live score shown: `OTT 2 — TOR 1`
  - If no game today: score area shows "No game today"
- Frontend polls `GET /api/senators/status` every **15 seconds** while mode is active to refresh score display

### Styling

- Primary: `#DA1A32` (Senators red)
- Accent: `#B5985A` (Senators gold)
- Background: `#000000` / dark card consistent with app theme

---

## Error Handling

- NHL API timeout or non-200: log the error, retry on the next 15s poll (do not deactivate mode)
- No game found on activation: activate red theme, show "No game today" in UI, skip polling
- Device command failure during flash: log and continue — partial flash is acceptable
- Server restart: Senators Mode resets to off; user must re-activate

---

## Out of Scope

- Playoff series tracking
- Push notifications
- Persisting Senators Mode across server restarts
- Pre-game countdown
