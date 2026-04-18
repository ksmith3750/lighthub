# Ottawa Senators Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a persistent Ottawa Senators Mode that sets all lights red, polls the NHL API every 15s during live games, flashes lights on Senators goals, dims on opponent goals, and auto-deactivates when the game ends.

**Architecture:** A new `senators.py` module manages all game-monitoring state and sequences, receiving `device_state` and a command callback from `main.py` to avoid circular imports. Three new FastAPI endpoints expose activate/deactivate/status. React senators state is lifted to `App.jsx` (consistent with existing pattern) and passed to a new `SenatorsModeCard` component rendered at the top of the Scenes page.

**Tech Stack:** Python asyncio, httpx (already installed), pytest + pytest-asyncio + respx for tests, React with CSS Modules

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `backend/senators.py` | NHL API fetch, flash/dim sequences, monitoring loop, activate/deactivate/get_status |
| Create | `backend/requirements-dev.txt` | pytest, pytest-asyncio, respx |
| Create | `backend/tests/__init__.py` | pytest package marker |
| Create | `backend/tests/test_senators.py` | All backend tests |
| Modify | `backend/main.py` | `import senators`, 3 new endpoints |
| Modify | `frontend/src/api.js` | senators API calls |
| Create | `frontend/src/components/SenatorsModeCard.jsx` | Toggle card with logo, score display |
| Create | `frontend/src/components/SenatorsModeCard.module.css` | Senators-themed card styles |
| Modify | `frontend/src/pages/ScenesPage.jsx` | Accept senators props, render SenatorsModeCard |
| Modify | `frontend/src/App.jsx` | Senators state, polling interval, handlers, pass to ScenesPage |

---

## Task 1: Test infrastructure and NHL API fetch

**Files:**
- Create: `backend/requirements-dev.txt`
- Create: `backend/tests/__init__.py`
- Create: `backend/senators.py` (partial — state + fetch only)
- Create: `backend/tests/test_senators.py` (fetch tests only)

- [ ] **Step 1: Add dev dependencies**

Create `backend/requirements-dev.txt`:

```
pytest==8.2.0
pytest-asyncio==0.23.7
respx==0.21.1
```

Install:

```bash
cd backend && pip install -r requirements-dev.txt
```

- [ ] **Step 2: Create tests package**

```bash
mkdir -p backend/tests && touch backend/tests/__init__.py
```

- [ ] **Step 3: Write failing test for fetch_todays_game — OTT as home team**

Create `backend/tests/test_senators.py`:

```python
import pytest
import respx
import httpx
from httpx import Response

NHL_API = "https://api-web.nhle.com/v1/scoreboard/OTT/now"

OTT_HOME_RESPONSE = {
    "focusedDate": "2026-04-18",
    "gamesByDate": [{
        "date": "2026-04-18",
        "games": [{
            "id": 2025020123,
            "gameState": "LIVE",
            "homeTeam": {
                "abbrev": "OTT",
                "commonName": {"default": "Senators"},
                "score": 2,
                "logo": "https://assets.nhle.com/logos/nhl/svg/OTT_light.svg"
            },
            "awayTeam": {
                "abbrev": "TOR",
                "commonName": {"default": "Maple Leafs"},
                "score": 1,
                "logo": "https://assets.nhle.com/logos/nhl/svg/TOR_light.svg"
            }
        }]
    }]
}

MOCK_DEVICES = {
    "hue_001": {"id": "hue_001", "brand": "hue", "reachable": True},
    "kasa_001": {"id": "kasa_001", "brand": "kasa", "reachable": True},
    "govee_001": {"id": "govee_001", "brand": "govee", "reachable": True},
    "hue_002": {"id": "hue_002", "brand": "hue", "reachable": False},
}


@pytest.fixture(autouse=True)
def reset_senators():
    import senators
    senators._state.update({
        "active": False, "game_id": None,
        "senators_score": 0, "opponent_score": 0,
        "opponent_name": None, "team_logo": None,
    })
    senators._monitor_task = None
    senators._flash_task = None
    senators._device_state = {}
    senators._send_command = None
    yield


@pytest.mark.asyncio
@respx.mock
async def test_fetch_todays_game_ott_home():
    respx.get(NHL_API).mock(return_value=Response(200, json=OTT_HOME_RESPONSE))
    from senators import fetch_todays_game
    game = await fetch_todays_game()
    assert game is not None
    assert game["game_id"] == "2025020123"
    assert game["senators_score"] == 2
    assert game["opponent_score"] == 1
    assert game["opponent_name"] == "Maple Leafs"
    assert game["game_state"] == "LIVE"
    assert "OTT" in game["team_logo"]
```

- [ ] **Step 4: Run test to verify it fails**

```bash
cd backend && pytest tests/test_senators.py::test_fetch_todays_game_ott_home -v
```

Expected: `ModuleNotFoundError: No module named 'senators'`

- [ ] **Step 5: Create senators.py with state and fetch_todays_game**

Create `backend/senators.py`:

```python
import asyncio
import httpx
import logging
from typing import Optional, Callable, Dict, Any

logger = logging.getLogger(__name__)

NHL_API = "https://api-web.nhle.com/v1/scoreboard/OTT/now"
SENATORS_RED = {"r": 255, "g": 0, "b": 0}
POLL_INTERVAL = 15
FLASH_ON_SECS = 0.3
FLASH_OFF_SECS = 0.3
FLASH_COUNT = 10
DIM_BRIGHTNESS = 10
DIM_DURATION = 3.0

_state: Dict[str, Any] = {
    "active": False,
    "game_id": None,
    "senators_score": 0,
    "opponent_score": 0,
    "opponent_name": None,
    "team_logo": None,
}
_monitor_task: Optional[asyncio.Task] = None
_flash_task: Optional[asyncio.Task] = None
_device_state: dict = {}
_send_command: Optional[Callable] = None


def get_status() -> dict:
    return {k: v for k, v in _state.items()}


async def fetch_todays_game() -> Optional[dict]:
    async with httpx.AsyncClient() as client:
        resp = await client.get(NHL_API, timeout=5.0)
        resp.raise_for_status()
        data = resp.json()

    today = data.get("focusedDate", "")
    for day in data.get("gamesByDate", []):
        if day.get("date") != today:
            continue
        for game in day.get("games", []):
            home = game.get("homeTeam", {})
            away = game.get("awayTeam", {})
            if home.get("abbrev") == "OTT":
                return {
                    "game_id": str(game["id"]),
                    "game_state": game.get("gameState", ""),
                    "senators_score": home.get("score", 0),
                    "opponent_score": away.get("score", 0),
                    "opponent_name": away.get("commonName", {}).get("default", away.get("abbrev", "")),
                    "team_logo": home.get("logo"),
                }
            elif away.get("abbrev") == "OTT":
                return {
                    "game_id": str(game["id"]),
                    "game_state": game.get("gameState", ""),
                    "senators_score": away.get("score", 0),
                    "opponent_score": home.get("score", 0),
                    "opponent_name": home.get("commonName", {}).get("default", home.get("abbrev", "")),
                    "team_logo": away.get("logo"),
                }
    return None
```

- [ ] **Step 6: Run test to verify it passes**

```bash
cd backend && pytest tests/test_senators.py::test_fetch_todays_game_ott_home -v
```

Expected: `PASSED`

- [ ] **Step 7: Write and run tests for OTT away and no-game cases**

Add to `backend/tests/test_senators.py`:

```python
OTT_AWAY_RESPONSE = {
    "focusedDate": "2026-04-18",
    "gamesByDate": [{
        "date": "2026-04-18",
        "games": [{
            "id": 2025020456,
            "gameState": "LIVE",
            "homeTeam": {
                "abbrev": "MTL",
                "commonName": {"default": "Canadiens"},
                "score": 0,
                "logo": "https://assets.nhle.com/logos/nhl/svg/MTL_light.svg"
            },
            "awayTeam": {
                "abbrev": "OTT",
                "commonName": {"default": "Senators"},
                "score": 3,
                "logo": "https://assets.nhle.com/logos/nhl/svg/OTT_light.svg"
            }
        }]
    }]
}


@pytest.mark.asyncio
@respx.mock
async def test_fetch_todays_game_ott_away():
    respx.get(NHL_API).mock(return_value=Response(200, json=OTT_AWAY_RESPONSE))
    from senators import fetch_todays_game
    game = await fetch_todays_game()
    assert game is not None
    assert game["senators_score"] == 3
    assert game["opponent_score"] == 0
    assert game["opponent_name"] == "Canadiens"


@pytest.mark.asyncio
@respx.mock
async def test_fetch_todays_game_no_ott_game():
    no_game = {"focusedDate": "2026-04-18", "gamesByDate": []}
    respx.get(NHL_API).mock(return_value=Response(200, json=no_game))
    from senators import fetch_todays_game
    game = await fetch_todays_game()
    assert game is None
```

Run:

```bash
cd backend && pytest tests/test_senators.py -v
```

Expected: all 3 tests `PASSED`

- [ ] **Step 8: Commit**

```bash
git add backend/requirements-dev.txt backend/tests/__init__.py backend/tests/test_senators.py backend/senators.py
git commit -m "feat: add senators.py with NHL API fetch and test infrastructure"
```

---

## Task 2: Light sequences

**Files:**
- Modify: `backend/senators.py` (add `_set_all_senators_red`, `_goal_flash`, `_opponent_dim`)
- Modify: `backend/tests/test_senators.py` (add sequence tests)

- [ ] **Step 1: Write failing tests for the three light sequences**

Add to `backend/tests/test_senators.py`:

```python
import senators


@pytest.mark.asyncio
async def test_set_all_senators_red_sends_red_to_color_devices():
    calls = []

    async def mock_send(device_id, cmd):
        calls.append((device_id, cmd))

    senators._device_state = MOCK_DEVICES
    senators._send_command = mock_send

    await senators._set_all_senators_red()

    hue_call = next(c for c in calls if c[0] == "hue_001")
    assert hue_call[1]["color"] == {"r": 255, "g": 0, "b": 0}
    assert hue_call[1]["on"] is True
    assert hue_call[1]["brightness"] == 100


@pytest.mark.asyncio
async def test_set_all_senators_red_kasa_has_no_color():
    calls = []

    async def mock_send(device_id, cmd):
        calls.append((device_id, cmd))

    senators._device_state = MOCK_DEVICES
    senators._send_command = mock_send

    await senators._set_all_senators_red()

    kasa_call = next(c for c in calls if c[0] == "kasa_001")
    assert "color" not in kasa_call[1]
    assert kasa_call[1]["on"] is True


@pytest.mark.asyncio
async def test_set_all_senators_red_skips_unreachable():
    calls = []

    async def mock_send(device_id, cmd):
        calls.append((device_id, cmd))

    senators._device_state = MOCK_DEVICES
    senators._send_command = mock_send

    await senators._set_all_senators_red()

    device_ids = [c[0] for c in calls]
    assert "hue_002" not in device_ids


@pytest.mark.asyncio
async def test_goal_flash_sends_ten_on_off_cycles_then_restores():
    calls = []

    async def mock_send(device_id, cmd):
        calls.append((device_id, cmd))

    senators._device_state = {"hue_001": {"id": "hue_001", "brand": "hue", "reachable": True}}
    senators._send_command = mock_send

    import unittest.mock as mock
    with mock.patch("senators.asyncio.sleep", return_value=None):
        await senators._goal_flash()

    # 1 device × (10 on + 10 off) + 1 restore = 21 calls
    assert len(calls) == 21
    on_calls  = [c for c in calls[:20] if c[1].get("on") is True]
    off_calls = [c for c in calls[:20] if c[1].get("on") is False]
    assert len(on_calls)  == 10
    assert len(off_calls) == 10


@pytest.mark.asyncio
async def test_opponent_dim_sets_10pct_then_restores_red():
    calls = []

    async def mock_send(device_id, cmd):
        calls.append((device_id, cmd))

    senators._device_state = {"hue_001": {"id": "hue_001", "brand": "hue", "reachable": True}}
    senators._send_command = mock_send

    import unittest.mock as mock
    with mock.patch("senators.asyncio.sleep", return_value=None):
        await senators._opponent_dim()

    assert calls[0][1]["brightness"] == 10
    assert calls[1][1]["color"] == {"r": 255, "g": 0, "b": 0}
    assert calls[1][1]["brightness"] == 100
```

Run to verify failures:

```bash
cd backend && pytest tests/test_senators.py -k "red or flash or dim" -v
```

Expected: `AttributeError: module 'senators' has no attribute '_set_all_senators_red'`

- [ ] **Step 2: Implement the three sequence functions**

Add to `backend/senators.py` after `get_status`:

```python
async def _set_all_senators_red():
    targets = [d for d in _device_state.values() if d.get("reachable")]
    tasks = []
    for dev in targets:
        if dev.get("brand") == "kasa":
            cmd = {"on": True, "brightness": 100}
        else:
            cmd = {"on": True, "brightness": 100, "color": SENATORS_RED}
        tasks.append(_send_command(dev["id"], cmd))
    if tasks:
        await asyncio.gather(*tasks)


async def _goal_flash():
    targets = [d for d in _device_state.values() if d.get("reachable")]
    for _ in range(FLASH_COUNT):
        on_tasks = []
        for dev in targets:
            if dev.get("brand") == "kasa":
                cmd = {"on": True, "brightness": 100}
            else:
                cmd = {"on": True, "brightness": 100, "color": SENATORS_RED}
            on_tasks.append(_send_command(dev["id"], cmd))
        await asyncio.gather(*on_tasks)
        await asyncio.sleep(FLASH_ON_SECS)

        off_tasks = [_send_command(dev["id"], {"on": False}) for dev in targets]
        await asyncio.gather(*off_tasks)
        await asyncio.sleep(FLASH_OFF_SECS)

    await _set_all_senators_red()


async def _opponent_dim():
    targets = [d for d in _device_state.values() if d.get("reachable")]
    dim_tasks = [_send_command(dev["id"], {"brightness": DIM_BRIGHTNESS}) for dev in targets]
    await asyncio.gather(*dim_tasks)
    await asyncio.sleep(DIM_DURATION)
    await _set_all_senators_red()
```

- [ ] **Step 3: Run sequence tests to verify they pass**

```bash
cd backend && pytest tests/test_senators.py -k "red or flash or dim" -v
```

Expected: all 5 tests `PASSED`

- [ ] **Step 4: Commit**

```bash
git add backend/senators.py backend/tests/test_senators.py
git commit -m "feat: add senators light sequences (red theme, goal flash, opponent dim)"
```

---

## Task 3: Monitor loop and activate/deactivate

**Files:**
- Modify: `backend/senators.py` (add `_monitor_loop`, `activate`, `deactivate`)
- Modify: `backend/tests/test_senators.py` (add activate/deactivate/status tests)

- [ ] **Step 1: Write failing tests for activate, deactivate, and get_status**

Add to `backend/tests/test_senators.py`:

```python
@pytest.mark.asyncio
@respx.mock
async def test_activate_sets_active_true():
    import asyncio
    respx.get(NHL_API).mock(return_value=Response(200, json={"focusedDate": "2026-04-18", "gamesByDate": []}))

    async def mock_send(device_id, cmd):
        pass

    await senators.activate(MOCK_DEVICES, mock_send)
    assert senators._state["active"] is True

    if senators._monitor_task:
        senators._monitor_task.cancel()
        try:
            await senators._monitor_task
        except asyncio.CancelledError:
            pass


@pytest.mark.asyncio
async def test_deactivate_sets_active_false():
    senators._state["active"] = True
    await senators.deactivate()
    assert senators._state["active"] is False


@pytest.mark.asyncio
async def test_get_status_returns_state_copy():
    senators._state.update({"active": True, "senators_score": 3, "opponent_score": 1})
    status = senators.get_status()
    assert status["active"] is True
    assert status["senators_score"] == 3
    assert status["opponent_score"] == 1
    # Verify it's a copy, not the live dict
    status["senators_score"] = 99
    assert senators._state["senators_score"] == 3


@pytest.mark.asyncio
@respx.mock
async def test_monitor_loop_detects_senators_goal():
    import unittest.mock as mock

    call_count = 0

    def nhl_side_effect(request):
        nonlocal call_count
        call_count += 1
        score = 1 if call_count > 1 else 0
        return Response(200, json={
            "focusedDate": "2026-04-18",
            "gamesByDate": [{"date": "2026-04-18", "games": [{
                "id": 2025020123, "gameState": "LIVE",
                "homeTeam": {"abbrev": "OTT", "commonName": {"default": "Senators"}, "score": score, "logo": ""},
                "awayTeam": {"abbrev": "TOR", "commonName": {"default": "Maple Leafs"}, "score": 0, "logo": ""},
            }]}]
        })

    respx.get(NHL_API).mock(side_effect=nhl_side_effect)

    async def mock_send(device_id, cmd):
        pass

    senators._device_state = {}
    senators._send_command = mock_send
    senators._state["active"] = True

    poll_count = 0

    async def counting_sleep(n):
        nonlocal poll_count
        poll_count += 1
        if poll_count >= 2:
            senators._state["active"] = False

    def mock_create_task(coro):
        # Close the coroutine so flash sequences don't run and don't pollute sleep counts
        coro.close()
        f = asyncio.get_event_loop().create_future()
        f.set_result(None)
        return f

    with mock.patch("senators.asyncio.sleep", side_effect=counting_sleep), \
         mock.patch("senators.asyncio.create_task", side_effect=mock_create_task):
        await senators._monitor_loop()

    assert senators._state["senators_score"] == 1
```

Run to verify failures:

```bash
cd backend && pytest tests/test_senators.py::test_activate_sets_active_true tests/test_senators.py::test_deactivate_sets_active_false tests/test_senators.py::test_get_status_returns_state_copy -v
```

Expected: `AttributeError: module 'senators' has no attribute 'activate'`

- [ ] **Step 2: Implement _monitor_loop, activate, and deactivate**

Add to the bottom of `backend/senators.py`:

```python
async def _monitor_loop():
    global _flash_task

    try:
        game = await fetch_todays_game()
    except Exception as e:
        logger.error(f"NHL API error on activate: {e}")
        game = None

    if game:
        _state.update({
            "game_id": game["game_id"],
            "senators_score": game["senators_score"],
            "opponent_score": game["opponent_score"],
            "opponent_name": game["opponent_name"],
            "team_logo": game["team_logo"],
        })

    await _set_all_senators_red()

    if not game:
        return  # No game today — red theme only, no polling

    while _state["active"]:
        await asyncio.sleep(POLL_INTERVAL)
        if not _state["active"]:
            break

        try:
            game = await fetch_todays_game()
        except Exception as e:
            logger.error(f"NHL API poll error: {e}")
            continue

        if not game:
            break

        new_senators = game["senators_score"]
        new_opponent = game["opponent_score"]

        if new_senators > _state["senators_score"]:
            _state["senators_score"] = new_senators
            if _flash_task and not _flash_task.done():
                _flash_task.cancel()
            _flash_task = asyncio.create_task(_goal_flash())

        if new_opponent > _state["opponent_score"]:
            _state["opponent_score"] = new_opponent
            if _flash_task and not _flash_task.done():
                _flash_task.cancel()
            _flash_task = asyncio.create_task(_opponent_dim())

        if game["game_state"] == "FINAL":
            logger.info("Senators game final — deactivating Senators Mode")
            break

    _state["active"] = False


async def activate(device_state: dict, send_command_fn: Callable):
    global _device_state, _send_command, _monitor_task
    _device_state = device_state
    _send_command = send_command_fn
    _state.update({
        "active": True,
        "game_id": None,
        "senators_score": 0,
        "opponent_score": 0,
        "opponent_name": None,
        "team_logo": None,
    })
    if _monitor_task and not _monitor_task.done():
        _monitor_task.cancel()
    _monitor_task = asyncio.create_task(_monitor_loop())


async def deactivate():
    global _monitor_task, _flash_task
    _state["active"] = False
    if _flash_task and not _flash_task.done():
        _flash_task.cancel()
    if _monitor_task and not _monitor_task.done():
        _monitor_task.cancel()
```

- [ ] **Step 3: Run all tests**

```bash
cd backend && pytest tests/ -v
```

Expected: all tests `PASSED`

- [ ] **Step 4: Commit**

```bash
git add backend/senators.py backend/tests/test_senators.py
git commit -m "feat: add senators monitor loop, activate, and deactivate"
```

---

## Task 4: Backend API endpoints

**Files:**
- Modify: `backend/main.py`

- [ ] **Step 1: Add senators import to main.py**

At the top of `backend/main.py`, after the existing imports, add:

```python
import senators
```

- [ ] **Step 2: Add three endpoints to main.py**

At the very bottom of `backend/main.py`, add:

```python
# ── Ottawa Senators Mode ──────────────────────────────────────────────────────

@app.post("/api/senators/activate")
async def activate_senators_mode():
    async def _send(device_id: str, cmd_dict: dict):
        await send_command(device_id, DeviceCommand(**cmd_dict))
    await senators.activate(device_state, _send)
    return {"ok": True, "status": senators.get_status()}


@app.post("/api/senators/deactivate")
async def deactivate_senators_mode():
    await senators.deactivate()
    return {"ok": True}


@app.get("/api/senators/status")
async def senators_status():
    return senators.get_status()
```

- [ ] **Step 3: Start the backend and verify all three endpoints**

```bash
cd backend && uvicorn main:app --port 8000 &
sleep 2
curl -s -X POST http://localhost:8000/api/senators/activate | python3 -m json.tool
```

Expected output contains `"ok": true` and `"status": {"active": true, ...}`

```bash
curl -s http://localhost:8000/api/senators/status | python3 -m json.tool
```

Expected: `"active": true`

```bash
curl -s -X POST http://localhost:8000/api/senators/deactivate | python3 -m json.tool
```

Expected: `{"ok": true}`

Kill the test server:

```bash
pkill -f "uvicorn main:app --port 8000"
```

- [ ] **Step 4: Commit**

```bash
git add backend/main.py
git commit -m "feat: add senators API endpoints (activate, deactivate, status)"
```

---

## Task 5: Frontend API calls

**Files:**
- Modify: `frontend/src/api.js`

- [ ] **Step 1: Add senators methods**

In `frontend/src/api.js`, inside the `api` object after the `// Config` block, add:

```js
  // Ottawa Senators Mode
  activateSenators: () => req('POST', '/senators/activate'),
  deactivateSenators: () => req('POST', '/senators/deactivate'),
  getSenatorStatus: () => req('GET', '/senators/status'),
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/api.js
git commit -m "feat: add senators API calls to frontend api.js"
```

---

## Task 6: SenatorsModeCard component

**Files:**
- Create: `frontend/src/components/SenatorsModeCard.jsx`
- Create: `frontend/src/components/SenatorsModeCard.module.css`

- [ ] **Step 1: Create the card component**

Create `frontend/src/components/SenatorsModeCard.jsx`:

```jsx
import styles from './SenatorsModeCard.module.css'

export default function SenatorsModeCard({ status, onActivate, onDeactivate, loading }) {
  const active = status?.active ?? false
  const hasGame = active && status?.game_id != null
  const noGame = active && status?.game_id == null
  const logo = status?.team_logo

  return (
    <div className={`${styles.card} ${active ? styles.cardActive : ''}`}>
      <div className={styles.top}>
        {logo
          ? <img src={logo} alt="Ottawa Senators" className={styles.logo} />
          : <div className={styles.logoBadge}>OTT</div>
        }
        <div className={styles.info}>
          <div className={styles.name}>Ottawa Senators Mode</div>
          {hasGame && (
            <div className={styles.score}>
              OTT {status.senators_score} — {status.opponent_name?.split(' ').pop() ?? 'OPP'} {status.opponent_score}
            </div>
          )}
          {noGame && <div className={styles.noGame}>No game today</div>}
          {!active && <div className={styles.inactive}>Sets all lights to Senators red</div>}
        </div>
      </div>

      <button
        className={`${styles.toggleBtn} ${active ? styles.toggleBtnActive : ''}`}
        onClick={active ? onDeactivate : onActivate}
        disabled={loading}
      >
        {loading ? '...' : active ? 'Deactivate' : 'Activate'}
      </button>
    </div>
  )
}
```

- [ ] **Step 2: Create the card styles**

Create `frontend/src/components/SenatorsModeCard.module.css`:

```css
.card {
  background: var(--bg-surface);
  border: 0.5px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 18px 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  transition: all var(--transition);
}

.cardActive {
  border-color: #DA1A32;
  background: rgba(218, 26, 50, 0.07);
  box-shadow: 0 0 0 1px rgba(218, 26, 50, 0.15);
}

.top {
  display: flex;
  align-items: center;
  gap: 14px;
}

.logo {
  width: 52px;
  height: 52px;
  object-fit: contain;
  flex-shrink: 0;
}

.logoBadge {
  width: 52px;
  height: 52px;
  border-radius: 50%;
  background: #DA1A32;
  color: #fff;
  font-size: 14px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  letter-spacing: 0.05em;
}

.info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.name {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
}

.score {
  font-size: 13px;
  color: #DA1A32;
  font-weight: 600;
  letter-spacing: 0.02em;
}

.noGame {
  font-size: 12px;
  color: var(--text-tertiary);
}

.inactive {
  font-size: 12px;
  color: var(--text-tertiary);
}

.toggleBtn {
  width: 100%;
  padding: 8px;
  border-radius: var(--radius-md);
  border: 0.5px solid var(--border);
  font-size: 13px;
  color: var(--text-secondary);
  transition: all var(--transition);
}

.toggleBtn:hover:not(:disabled) {
  border-color: #DA1A32;
  color: #DA1A32;
  background: rgba(218, 26, 50, 0.08);
}

.toggleBtnActive {
  border-color: #DA1A32;
  color: #DA1A32;
  background: rgba(218, 26, 50, 0.08);
}

.toggleBtnActive:hover:not(:disabled) {
  background: rgba(218, 26, 50, 0.15);
}

.toggleBtn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/SenatorsModeCard.jsx frontend/src/components/SenatorsModeCard.module.css
git commit -m "feat: add SenatorsModeCard component with Senators logo, score, and toggle"
```

---

## Task 7: Wire senators state into App.jsx and ScenesPage

**Files:**
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/pages/ScenesPage.jsx`

- [ ] **Step 1: Add useRef to App.jsx imports**

In `frontend/src/App.jsx`, update the first import line to:

```jsx
import { useState, useEffect, useCallback, useRef } from 'react'
```

- [ ] **Step 2: Add senators state variables to App.jsx**

After `const [notification, setNotification] = useState(null)`, add:

```jsx
const [senatorsStatus, setSenatorsStatus] = useState({ active: false })
const [senatorsLoading, setSenatorsLoading] = useState(false)
const senatorsIntervalRef = useRef(null)
```

- [ ] **Step 3: Add senators handlers to App.jsx**

After the `handleActivateScene` callback, add:

```jsx
const handleSenatorActivate = useCallback(async () => {
  setSenatorsLoading(true)
  try {
    const data = await api.activateSenators()
    setSenatorsStatus(data.status)
    senatorsIntervalRef.current = setInterval(async () => {
      try {
        const s = await api.getSenatorStatus()
        setSenatorsStatus(s)
        if (!s.active) clearInterval(senatorsIntervalRef.current)
      } catch { /* ignore poll errors */ }
    }, 15000)
  } catch {
    notify('Could not activate Senators Mode', 'error')
  } finally {
    setSenatorsLoading(false)
  }
}, [notify])

const handleSenatorDeactivate = useCallback(async () => {
  setSenatorsLoading(true)
  try {
    await api.deactivateSenators()
    setSenatorsStatus({ active: false })
    clearInterval(senatorsIntervalRef.current)
  } catch {
    notify('Could not deactivate Senators Mode', 'error')
  } finally {
    setSenatorsLoading(false)
  }
}, [notify])
```

- [ ] **Step 4: Add cleanup effect to App.jsx**

After the existing `useEffect(() => { loadAll() }, [loadAll])`, add:

```jsx
useEffect(() => {
  return () => clearInterval(senatorsIntervalRef.current)
}, [])
```

- [ ] **Step 5: Pass senators props to ScenesPage in App.jsx**

Find the `{page === 'scenes' && (` block and replace the entire `<ScenesPage ... />` call with:

```jsx
<ScenesPage
  scenes={scenes}
  devices={devices}
  onActivate={handleActivateScene}
  onCreate={async (scene) => {
    await api.createScene(scene)
    notify(`Scene "${scene.name}" saved`)
    loadAll()
  }}
  onDelete={async (name) => {
    await api.deleteScene(name)
    notify(`Scene deleted`)
    loadAll()
  }}
  senatorsStatus={senatorsStatus}
  senatorsLoading={senatorsLoading}
  onSenatorActivate={handleSenatorActivate}
  onSenatorDeactivate={handleSenatorDeactivate}
/>
```

- [ ] **Step 6: Update ScenesPage to accept senators props and render the card**

In `frontend/src/pages/ScenesPage.jsx`, add the import at the top:

```jsx
import SenatorsModeCard from '../components/SenatorsModeCard.jsx'
```

Update the function signature:

```jsx
export default function ScenesPage({ scenes, devices, onActivate, onCreate, onDelete, senatorsStatus, senatorsLoading, onSenatorActivate, onSenatorDeactivate }) {
```

Add `<SenatorsModeCard>` immediately before `<div className={styles.grid}>`:

```jsx
<SenatorsModeCard
  status={senatorsStatus}
  onActivate={onSenatorActivate}
  onDeactivate={onSenatorDeactivate}
  loading={senatorsLoading}
/>
```

- [ ] **Step 7: Start the full app and verify end-to-end**

Start the backend:

```bash
cd backend && uvicorn main:app --reload --port 8000
```

Start the frontend in a second terminal:

```bash
cd frontend && npm run dev
```

Open http://localhost:3000 and navigate to **Scenes**. Verify:

1. Senators card appears at the top with the OTT red badge and "Sets all lights to Senators red" subtitle
2. Clicking **Activate** calls the backend, card border turns red, button switches to "Deactivate"
3. Mock device state in the devices page shows lights turned on (red for Hue/Govee, on for Kasa)
4. Card shows "No game today" (since it's off-season)
5. Clicking **Deactivate** resets card to inactive state

- [ ] **Step 8: Commit**

```bash
git add frontend/src/App.jsx frontend/src/pages/ScenesPage.jsx
git commit -m "feat: wire Ottawa Senators Mode into App and ScenesPage with live score polling"
```
