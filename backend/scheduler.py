"""
LightHub Scheduler — runs alongside the FastAPI server.
Checks schedules every minute and triggers scenes/commands.

Run separately: python scheduler.py
Or integrate via: asyncio.create_task(run_scheduler())
"""

import asyncio
import json
import os
import logging
from datetime import datetime, time
import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("scheduler")

CONFIG_FILE = "lighthub_config.json"
API_BASE = "http://localhost:8000/api"

DAY_MAP = {
    "mon": 0, "tue": 1, "wed": 2, "thu": 3,
    "fri": 4, "sat": 5, "sun": 6,
}

def load_schedules() -> list:
    if not os.path.exists(CONFIG_FILE):
        return []
    with open(CONFIG_FILE) as f:
        return json.load(f).get("schedules", [])

def schedule_matches_now(schedule: dict) -> bool:
    now = datetime.now()
    current_time = now.strftime("%H:%M")
    days = schedule.get("days", [])

    # Time match
    sched_time = schedule.get("time", "")
    if sched_time == "sunset":
        # Approximate sunset — in production use an astronomy library
        sched_time = "20:00"
    elif sched_time == "sunrise":
        sched_time = "06:30"

    if current_time != sched_time:
        return False

    # Day match
    if "everyday" in days:
        return True
    current_day = list(DAY_MAP.keys())[now.weekday()]
    return current_day in days

async def trigger_schedule(schedule: dict):
    async with httpx.AsyncClient() as client:
        scene = schedule.get("scene_name")
        if scene:
            try:
                resp = await client.post(
                    f"{API_BASE}/scenes/{scene}/activate", timeout=10.0
                )
                logger.info(f"Schedule '{schedule['name']}' → scene '{scene}': {resp.status_code}")
            except Exception as e:
                logger.error(f"Schedule trigger failed: {e}")
        elif schedule.get("devices"):
            for device_id, cmd in schedule["devices"].items():
                try:
                    await client.post(
                        f"{API_BASE}/devices/{device_id}/command",
                        json=cmd, timeout=5.0
                    )
                except Exception as e:
                    logger.error(f"Device command failed for {device_id}: {e}")

async def run_scheduler():
    logger.info("LightHub scheduler started. Checking every 60s.")
    while True:
        try:
            schedules = load_schedules()
            for schedule in schedules:
                if schedule.get("enabled", True) and schedule_matches_now(schedule):
                    logger.info(f"Triggering schedule: {schedule['name']}")
                    await trigger_schedule(schedule)
        except Exception as e:
            logger.error(f"Scheduler loop error: {e}")

        # Sleep until the next full minute
        now = datetime.now()
        seconds_until_next_minute = 60 - now.second
        await asyncio.sleep(seconds_until_next_minute)

if __name__ == "__main__":
    asyncio.run(run_scheduler())
