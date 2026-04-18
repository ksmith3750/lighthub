import pytest
import respx
import httpx
import senators
from httpx import Response
from senators import NHL_API

MOCK_DEVICES = {
    "hue_001": {"id": "hue_001", "brand": "hue", "reachable": True},
    "kasa_001": {"id": "kasa_001", "brand": "kasa", "reachable": True},
    "govee_001": {"id": "govee_001", "brand": "govee", "reachable": True},
    "hue_002": {"id": "hue_002", "brand": "hue", "reachable": False},
}

# Reset senators module state before each test
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
    # Verify it is a copy, not the live dict
    status["senators_score"] = 99
    assert senators._state["senators_score"] == 3


@pytest.mark.asyncio
@respx.mock
async def test_monitor_loop_detects_senators_goal():
    import unittest.mock as mock
    import asyncio

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
