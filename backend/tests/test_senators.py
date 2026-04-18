import pytest
import respx
import httpx
from httpx import Response
from senators import NHL_API

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
