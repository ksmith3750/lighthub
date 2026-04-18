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
