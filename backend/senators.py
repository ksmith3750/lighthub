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
    return _state.copy()


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
        await _set_all_senators_red()
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
