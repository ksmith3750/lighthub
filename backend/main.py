"""
LightHub Backend — FastAPI server unifying Kasa, Hue, and Govee lights.
Run: uvicorn main:app --reload --port 8000
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import asyncio
import json
import os
import logging
import socket
import uuid
from datetime import datetime
import senators

# ── Conditional imports (graceful fallback if libraries not installed) ──────
try:
    from kasa import Discover, SmartPlug, SmartBulb
    KASA_AVAILABLE = True
except ImportError:
    KASA_AVAILABLE = False
    logging.warning("python-kasa not installed. Kasa devices will use mock data.")

try:
    from phue import Bridge
    HUE_AVAILABLE = True
except ImportError:
    HUE_AVAILABLE = False
    logging.warning("phue not installed. Hue devices will use mock data.")

try:
    import httpx
    GOVEE_AVAILABLE = True
except ImportError:
    GOVEE_AVAILABLE = False
    logging.warning("httpx not installed. Govee devices will use mock data.")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="LightHub API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Config & State ──────────────────────────────────────────────────────────
CONFIG_FILE = "lighthub_config.json"
STATE_FILE = "lighthub_devices.json"

def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {
        "hue_bridge_ip": "",
        "govee_api_key": "",
        "device_names": {},
        "rooms": {},
        "scenes": {},
        "schedules": []
    }

def save_config(config: dict):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)

def load_device_state() -> Dict[str, dict]:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                devices = json.load(f)
            return {d["id"]: d for d in devices}
        except Exception as e:
            logger.warning(f"Could not load device state: {e}")
    return {d["id"]: d.copy() for d in MOCK_DEVICES}

def save_device_state():
    with open(STATE_FILE, "w") as f:
        json.dump(list(device_state.values()), f, indent=2)

config = load_config()

# ── Pydantic Models ─────────────────────────────────────────────────────────
class DeviceCommand(BaseModel):
    on: Optional[bool] = None
    brightness: Optional[int] = None   # 0–100
    color_temp: Optional[int] = None   # Kelvin (2700–6500)
    color: Optional[Dict[str, int]] = None  # {"r":255,"g":128,"b":0}

class Scene(BaseModel):
    name: str
    icon: str = "💡"
    devices: Dict[str, DeviceCommand]  # device_id → command

class Schedule(BaseModel):
    id: Optional[str] = None
    name: str
    scene_name: Optional[str] = None
    devices: Optional[Dict[str, DeviceCommand]] = None
    time: str           # "HH:MM" or "sunset" / "sunrise"
    days: List[str]     # ["mon","tue",...] or ["everyday"]
    enabled: bool = True

class RoomAssignment(BaseModel):
    device_ids: List[str]

class ConfigUpdate(BaseModel):
    hue_bridge_ip: Optional[str] = None
    govee_api_key: Optional[str] = None

# ── Mock device data (used when real hardware not reachable) ─────────────────
MOCK_DEVICES = [
    {"id": "kasa_001", "name": "Table lamp", "brand": "kasa", "type": "plug",
     "room": "living", "on": True, "brightness": 100, "reachable": True},
    {"id": "kasa_002", "name": "Reading light", "brand": "kasa", "type": "plug",
     "room": "living", "on": False, "brightness": 100, "reachable": True},
    {"id": "kasa_003", "name": "Desk lamp", "brand": "kasa", "type": "plug",
     "room": "office", "on": False, "brightness": 100, "reachable": True},
    {"id": "hue_001", "name": "Floor lamp", "brand": "hue", "type": "bulb",
     "room": "living", "on": True, "brightness": 75, "color_temp": 2700,
     "color": {"r": 255, "g": 200, "b": 120}, "reachable": True},
    {"id": "hue_002", "name": "Bedside left", "brand": "hue", "type": "bulb",
     "room": "bedroom", "on": True, "brightness": 30, "color_temp": 2700,
     "color": {"r": 255, "g": 180, "b": 100}, "reachable": True},
    {"id": "hue_003", "name": "Bedside right", "brand": "hue", "type": "bulb",
     "room": "bedroom", "on": False, "brightness": 50, "color_temp": 4000,
     "color": {"r": 200, "g": 220, "b": 255}, "reachable": True},
    {"id": "hue_004", "name": "Kitchen main", "brand": "hue", "type": "bulb",
     "room": "kitchen", "on": True, "brightness": 90, "color_temp": 5000,
     "color": {"r": 220, "g": 235, "b": 255}, "reachable": True},
    {"id": "govee_001", "name": "TV backlight", "brand": "govee", "type": "strip",
     "room": "living", "on": True, "brightness": 100,
     "color": {"r": 200, "g": 50, "b": 200}, "reachable": True},
    {"id": "govee_002", "name": "Under-bed strip", "brand": "govee", "type": "strip",
     "room": "bedroom", "on": True, "brightness": 50,
     "color": {"r": 30, "g": 80, "b": 220}, "reachable": True},
    {"id": "govee_003", "name": "Shelf glow", "brand": "govee", "type": "strip",
     "room": "office", "on": False, "brightness": 60,
     "color": {"r": 100, "g": 255, "b": 150}, "reachable": True},
]

# In-memory device state — loaded from saved state, falls back to mocks
device_state: Dict[str, dict] = load_device_state()

# ── Kasa helpers ─────────────────────────────────────────────────────────────
async def discover_kasa() -> List[dict]:
    if not KASA_AVAILABLE:
        return [d for d in device_state.values() if d["brand"] == "kasa"]
    try:
        devices = await Discover.discover()
        result = []
        for ip, dev in devices.items():
            await dev.update()
            result.append({
                "id": f"kasa_{ip.replace('.','_')}",
                "name": dev.alias,
                "brand": "kasa",
                "type": "plug",
                "ip": ip,
                "on": dev.is_on,
                "brightness": 100,
                "reachable": True,
            })
        return result
    except Exception as e:
        logger.error(f"Kasa discovery failed: {e}")
        return [d for d in device_state.values() if d["brand"] == "kasa"]

async def control_kasa(device_id: str, cmd: DeviceCommand):
    if not KASA_AVAILABLE:
        _apply_mock_command(device_id, cmd)
        return
    dev_info = device_state.get(device_id, {})
    ip = dev_info.get("ip")
    if not ip:
        _apply_mock_command(device_id, cmd)
        return
    try:
        dev = SmartPlug(ip)
        await dev.update()
        if cmd.on is True:
            await dev.turn_on()
        elif cmd.on is False:
            await dev.turn_off()
    except Exception as e:
        logger.error(f"Kasa control failed: {e}")

# ── Hue helpers ──────────────────────────────────────────────────────────────
def get_hue_bridge():
    bridge_ip = config.get("hue_bridge_ip", "")
    if not bridge_ip or not HUE_AVAILABLE:
        return None
    try:
        return Bridge(bridge_ip)
    except Exception as e:
        logger.error(f"Hue bridge connection failed: {e}")
        return None

def discover_hue() -> List[dict]:
    bridge = get_hue_bridge()
    if not bridge:
        return [d for d in device_state.values() if d["brand"] == "hue"]
    try:
        lights = bridge.get_light()  # returns raw dict keyed by string light ID
        result = []
        for light_id, light in lights.items():
            state = light.get("state", {})
            result.append({
                "id": f"hue_{light_id}",
                "name": light.get("name", f"Hue light {light_id}"),
                "brand": "hue",
                "type": "bulb",
                "hue_id": int(light_id),
                "on": state.get("on", False),
                "brightness": int(state.get("bri", 254) / 254 * 100),
                "color_temp": state.get("ct"),
                "reachable": state.get("reachable", True),
            })
        return result
    except Exception as e:
        logger.error(f"Hue discovery failed: {e}")
        return [d for d in device_state.values() if d["brand"] == "hue"]

def control_hue(device_id: str, cmd: DeviceCommand):
    bridge = get_hue_bridge()
    dev_info = device_state.get(device_id, {})
    hue_id = dev_info.get("hue_id")
    if not bridge or not hue_id:
        _apply_mock_command(device_id, cmd)
        return
    try:
        settings = {}
        if cmd.on is not None:
            settings["on"] = cmd.on
        if cmd.brightness is not None:
            settings["bri"] = int(cmd.brightness / 100 * 254)
        if cmd.color_temp is not None:
            # Convert Kelvin to Hue mireds
            settings["ct"] = int(1_000_000 / cmd.color_temp)
        if cmd.color:
            # Convert RGB to xy (simplified)
            r, g, b = cmd.color["r"] / 255, cmd.color["g"] / 255, cmd.color["b"] / 255
            X = r * 0.664511 + g * 0.154324 + b * 0.162028
            Y = r * 0.283881 + g * 0.668433 + b * 0.047685
            Z = r * 0.000088 + g * 0.072310 + b * 0.986039
            total = X + Y + Z
            settings["xy"] = [X / total, Y / total] if total > 0 else [0.3, 0.3]
        bridge.set_light(hue_id, settings)
    except Exception as e:
        logger.error(f"Hue control failed: {e}")

# ── Govee helpers ────────────────────────────────────────────────────────────
GOVEE_BASE = "https://openapi.api.govee.com/router/api/v1"
GOVEE_LAN_PORT = 4003          # port devices listen on
GOVEE_LAN_LISTEN_PORT = 4002   # port devices respond to
GOVEE_LAN_BROADCAST = "255.255.255.255"
GOVEE_LAN_SCAN_TIMEOUT = 3.0   # seconds to wait for LAN responses

# Govee model prefixes mapped to device type
GOVEE_MODEL_TYPES = {
    # Floor / torchiere lamps
    "H607C": "floor",
    "H7021": "floor", "H7022": "floor", "H7023": "floor",
    "H7028": "floor", "H7029": "floor",
    "H7055": "floor", "H7060": "floor", "H7061": "floor",
    "H7062": "floor", "H7065": "floor", "H7066": "floor",
    # Bulbs
    "H6001": "bulb",  "H6003": "bulb",  "H6008": "bulb",
    "H6009": "bulb",  "H6010": "bulb",  "H6011": "bulb",
    "H6049": "bulb",  "H6051": "bulb",  "H6052": "bulb",
    "H6053": "bulb",  "H6054": "bulb",  "H6059": "bulb",
}

def _govee_device_type(model: str) -> str:
    """Return device type for a Govee model string, defaulting to 'strip'."""
    return GOVEE_MODEL_TYPES.get(model, "strip")

async def discover_govee() -> List[dict]:
    api_key = config.get("govee_api_key", "")
    if not api_key or not GOVEE_AVAILABLE:
        return [d for d in device_state.values() if d["brand"] == "govee"]
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{GOVEE_BASE}/user/devices",
                headers={"Govee-API-Key": api_key},
                timeout=5.0,
            )
            data = resp.json()
            logger.info(f"Govee API response: {data}")
            result = []
            for dev in data.get("data", []):
                model = dev.get("sku", "")
                result.append({
                    "id": f"govee_{dev['device'].replace(':','_')}",
                    "name": dev.get("deviceName", f"Govee {model}"),
                    "brand": "govee",
                    "type": _govee_device_type(model),
                    "govee_device": dev["device"],
                    "govee_model": model,
                    "on": False,
                    "brightness": 100,
                    "color": {"r": 255, "g": 255, "b": 255},
                    "reachable": True,
                })
            return result
    except Exception as e:
        logger.error(f"Govee discovery failed: {e}")
        return [d for d in device_state.values() if d["brand"] == "govee"]


def _govee_control_payload(govee_device: str, govee_model: str, capability_type: str, instance: str, value) -> dict:
    return {
        "requestId": str(uuid.uuid4()),
        "payload": {
            "sku": govee_model,
            "device": govee_device,
            "capability": {"type": capability_type, "instance": instance, "value": value},
        },
    }


async def control_govee(device_id: str, cmd: DeviceCommand):
    api_key = config.get("govee_api_key", "")
    dev_info = device_state.get(device_id, {})
    govee_device = dev_info.get("govee_device")
    govee_model = dev_info.get("govee_model")

    if not api_key or not govee_device or not GOVEE_AVAILABLE:
        _apply_mock_command(device_id, cmd)
        return

    try:
        async with httpx.AsyncClient() as client:
            headers = {"Govee-API-Key": api_key, "Content-Type": "application/json"}
            url = f"{GOVEE_BASE}/device/control"

            if cmd.on is not None:
                await client.post(url, headers=headers, json=_govee_control_payload(
                    govee_device, govee_model,
                    "devices.capabilities.on_off", "powerSwitch", 1 if cmd.on else 0,
                ), timeout=5.0)

            if cmd.brightness is not None:
                await client.post(url, headers=headers, json=_govee_control_payload(
                    govee_device, govee_model,
                    "devices.capabilities.range", "brightness", cmd.brightness,
                ), timeout=5.0)

            if cmd.color:
                r, g, b = cmd.color["r"], cmd.color["g"], cmd.color["b"]
                rgb_int = (r << 16) | (g << 8) | b
                await client.post(url, headers=headers, json=_govee_control_payload(
                    govee_device, govee_model,
                    "devices.capabilities.color_setting", "colorRgb", rgb_int,
                ), timeout=5.0)
    except Exception as e:
        logger.error(f"Govee control failed: {e}")

async def discover_govee_lan() -> List[dict]:
    """Discover Govee devices on the LAN via UDP broadcast."""
    scan_msg = json.dumps(
        {"msg": {"cmd": "scan", "data": {"account_topic": "reserve"}}}
    ).encode()
    found: List[dict] = []
    seen: set = set()

    class _ScanProtocol(asyncio.DatagramProtocol):
        def connection_made(self, transport):
            # Enable broadcast on the underlying socket then fire the scan.
            # Sending from this socket means source port == GOVEE_LAN_LISTEN_PORT,
            # so the device replies back to the same port we're listening on.
            sock = transport.get_extra_info("socket")
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            transport.sendto(scan_msg, (GOVEE_LAN_BROADCAST, GOVEE_LAN_PORT))

        def datagram_received(self, data, addr):
            try:
                msg = json.loads(data.decode())
                dev_data = msg.get("msg", {}).get("data", {})
                mac = dev_data.get("device", "")
                if not mac or mac in seen:
                    return
                seen.add(mac)
                model = dev_data.get("sku", "")
                found.append({
                    "id": f"govee_{mac.replace(':','_')}",
                    "name": dev_data.get("deviceName", f"Govee {model}"),
                    "brand": "govee",
                    "type": _govee_device_type(model),
                    "govee_device": mac,
                    "govee_model": model,
                    "govee_lan_ip": addr[0],
                    "on": False,
                    "brightness": 100,
                    "color": {"r": 255, "g": 255, "b": 255},
                    "reachable": True,
                })
            except Exception:
                pass

    loop = asyncio.get_event_loop()
    transport = None
    try:
        transport, _ = await loop.create_datagram_endpoint(
            _ScanProtocol,
            local_addr=("0.0.0.0", GOVEE_LAN_LISTEN_PORT),
        )
        await asyncio.sleep(GOVEE_LAN_SCAN_TIMEOUT)
    except Exception as e:
        logger.error(f"Govee LAN discovery failed: {e}")
    finally:
        if transport:
            transport.close()

    logger.info(f"Govee LAN discovery found {len(found)} device(s): {[d['name'] for d in found]}")
    return found


def _send_govee_lan_cmd(ip: str, payload: dict):
    """Fire-and-forget UDP command to a Govee LAN device."""
    msg = json.dumps(payload).encode()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.sendto(msg, (ip, GOVEE_LAN_PORT))
    finally:
        sock.close()


def control_govee_lan(device_id: str, cmd: DeviceCommand):
    dev_info = device_state.get(device_id, {})
    ip = dev_info.get("govee_lan_ip")
    if not ip:
        return
    if cmd.on is not None:
        _send_govee_lan_cmd(ip, {"msg": {"cmd": "turn", "data": {"value": 1 if cmd.on else 0}}})
    if cmd.brightness is not None:
        _send_govee_lan_cmd(ip, {"msg": {"cmd": "brightness", "data": {"value": cmd.brightness}}})
    if cmd.color:
        _send_govee_lan_cmd(ip, {"msg": {"cmd": "colorwc", "data": {
            "color": {"r": cmd.color["r"], "g": cmd.color["g"], "b": cmd.color["b"]},
            "colorTemInKelvin": 0,
        }}})


# ── Shared helpers ────────────────────────────────────────────────────────────
def _apply_mock_command(device_id: str, cmd: DeviceCommand):
    """Apply command to in-memory state (mock/fallback)."""
    if device_id not in device_state:
        return
    dev = device_state[device_id]
    if cmd.on is not None:
        dev["on"] = cmd.on
    if cmd.brightness is not None:
        dev["brightness"] = cmd.brightness
    if cmd.color_temp is not None:
        dev["color_temp"] = cmd.color_temp
    if cmd.color is not None:
        dev["color"] = cmd.color

async def send_command(device_id: str, cmd: DeviceCommand):
    _apply_mock_command(device_id, cmd)  # Always update local state immediately
    brand = device_state.get(device_id, {}).get("brand", "")
    if brand == "kasa":
        await control_kasa(device_id, cmd)
    elif brand == "hue":
        control_hue(device_id, cmd)
    elif brand == "govee":
        if device_state.get(device_id, {}).get("govee_lan_ip"):
            control_govee_lan(device_id, cmd)
        else:
            await control_govee(device_id, cmd)

# ── API Routes ────────────────────────────────────────────────────────────────

def _with_custom_names(devices: list) -> list:
    """Overlay user-defined friendly names onto the device list."""
    names = config.get("device_names", {})
    if not names:
        return devices
    result = []
    for dev in devices:
        custom = names.get(dev["id"])
        if custom:
            dev = {**dev, "name": custom}
        result.append(dev)
    return result

@app.get("/api/devices")
async def get_devices():
    """Return all known devices with current state."""
    return {"devices": _with_custom_names(list(device_state.values()))}

@app.post("/api/devices/discover")
async def discover_devices():
    """Discover all devices on the network."""
    kasa, govee, govee_lan = await asyncio.gather(
        discover_kasa(),
        discover_govee(),
        discover_govee_lan(),
    )
    hue = discover_hue()

    # Merge LAN results: if a cloud device also has a LAN IP, attach it
    lan_by_mac = {d["govee_device"]: d["govee_lan_ip"] for d in govee_lan}
    for d in govee:
        if d["govee_device"] in lan_by_mac:
            d["govee_lan_ip"] = lan_by_mac[d["govee_device"]]

    # LAN-only devices (not in cloud API) get added as-is
    cloud_macs = {d["govee_device"] for d in govee}
    lan_only = [d for d in govee_lan if d["govee_device"] not in cloud_macs]

    all_devices = kasa + hue + govee + lan_only
    for dev in all_devices:
        existing = device_state.get(dev["id"], {})
        dev.setdefault("room", existing.get("room", ""))
        device_state[dev["id"]] = dev
    save_device_state()
    return {"devices": _with_custom_names(list(device_state.values())), "discovered": len(all_devices)}

@app.get("/api/debug/hue")
async def debug_hue():
    """Return raw light list from the Hue bridge for debugging."""
    bridge = get_hue_bridge()
    if not bridge:
        raise HTTPException(400, "Hue bridge not configured or not reachable")
    raw = bridge.get_light()  # returns the full JSON dict from the bridge
    return raw

@app.get("/api/debug/govee")
async def debug_govee():
    """Return raw Govee API device list for debugging."""
    api_key = config.get("govee_api_key", "")
    if not api_key:
        raise HTTPException(400, "No Govee API key configured")
    if not GOVEE_AVAILABLE:
        raise HTTPException(500, "httpx not installed")
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GOVEE_BASE}/user/devices",
            headers={"Govee-API-Key": api_key},
            timeout=5.0,
        )
    return resp.json()

@app.post("/api/devices/{device_id}/command")
async def command_device(device_id: str, cmd: DeviceCommand):
    """Send a command to a single device."""
    if device_id not in device_state:
        raise HTTPException(404, f"Device {device_id} not found")
    await send_command(device_id, cmd)
    return {"ok": True, "device": device_state[device_id]}

@app.post("/api/rooms/{room}/command")
async def command_room(room: str, cmd: DeviceCommand):
    """Send a command to all devices in a room."""
    targets = [d for d in device_state.values() if d.get("room") == room]
    if not targets:
        raise HTTPException(404, f"No devices in room '{room}'")
    await asyncio.gather(*[send_command(d["id"], cmd) for d in targets])
    return {"ok": True, "affected": len(targets)}

@app.put("/api/devices/{device_id}/room")
async def assign_room(device_id: str, body: dict):
    """Assign a device to a room."""
    if device_id not in device_state:
        raise HTTPException(404)
    device_state[device_id]["room"] = body.get("room", "")
    save_device_state()
    return {"ok": True}

@app.put("/api/devices/{device_id}/name")
async def rename_device(device_id: str, body: dict):
    """Set a friendly name for a device."""
    if device_id not in device_state:
        raise HTTPException(404)
    name = body.get("name", "").strip()
    if not config.get("device_names"):
        config["device_names"] = {}
    if name:
        config["device_names"][device_id] = name
    else:
        config["device_names"].pop(device_id, None)
    save_config(config)
    return {"ok": True}

# ── Scenes ───────────────────────────────────────────────────────────────────

DEFAULT_SCENES = {
    "Morning": {
        "icon": "🌅",
        "devices": {
            "hue_001": {"on": True, "brightness": 60, "color_temp": 3000},
            "hue_002": {"on": True, "brightness": 80, "color_temp": 4000},
            "hue_004": {"on": True, "brightness": 90, "color_temp": 5000},
            "kasa_001": {"on": True},
            "govee_001": {"on": False},
        }
    },
    "Movie night": {
        "icon": "🎬",
        "devices": {
            "hue_001": {"on": True, "brightness": 20, "color_temp": 2700},
            "govee_001": {"on": True, "brightness": 80, "color": {"r": 20, "g": 20, "b": 200}},
            "kasa_001": {"on": False},
            "kasa_002": {"on": False},
        }
    },
    "Wind down": {
        "icon": "💤",
        "devices": {
            "hue_001": {"on": True, "brightness": 10, "color_temp": 2200},
            "hue_002": {"on": True, "brightness": 15, "color_temp": 2200},
            "hue_003": {"on": False},
            "govee_001": {"on": False},
            "govee_002": {"on": True, "brightness": 20, "color": {"r": 100, "g": 0, "b": 60}},
        }
    },
    "Focus": {
        "icon": "📚",
        "devices": {
            "hue_004": {"on": True, "brightness": 100, "color_temp": 6000},
            "govee_003": {"on": True, "brightness": 80, "color": {"r": 180, "g": 220, "b": 255}},
            "kasa_003": {"on": True},
        }
    },
    "Party": {
        "icon": "🎉",
        "devices": {
            "govee_001": {"on": True, "brightness": 100, "color": {"r": 255, "g": 0, "b": 128}},
            "govee_002": {"on": True, "brightness": 100, "color": {"r": 0, "g": 255, "b": 128}},
            "govee_003": {"on": True, "brightness": 100, "color": {"r": 128, "g": 0, "b": 255}},
            "hue_001": {"on": True, "brightness": 100, "color": {"r": 255, "g": 50, "b": 50}},
        }
    },
    "All off": {
        "icon": "🌙",
        "devices": {d["id"]: {"on": False} for d in MOCK_DEVICES}
    },
}

@app.get("/api/scenes")
async def get_scenes():
    scenes = {**DEFAULT_SCENES, **config.get("scenes", {})}
    return {"scenes": scenes}

@app.post("/api/scenes/{scene_name}/activate")
async def activate_scene(scene_name: str):
    scenes = {**DEFAULT_SCENES, **config.get("scenes", {})}
    scene = scenes.get(scene_name)
    if not scene:
        raise HTTPException(404, f"Scene '{scene_name}' not found")
    cmds = []
    for device_id, raw_cmd in scene["devices"].items():
        cmd = DeviceCommand(**raw_cmd)
        cmds.append(send_command(device_id, cmd))
    await asyncio.gather(*cmds)
    return {"ok": True, "scene": scene_name, "affected": len(scene["devices"])}

@app.post("/api/scenes")
async def create_scene(scene: Scene):
    config.setdefault("scenes", {})[scene.name] = {
        "icon": scene.icon,
        "devices": {k: v.dict(exclude_none=True) for k, v in scene.devices.items()}
    }
    save_config(config)
    return {"ok": True, "scene": scene.name}

@app.delete("/api/scenes/{scene_name}")
async def delete_scene(scene_name: str):
    if scene_name in config.get("scenes", {}):
        del config["scenes"][scene_name]
        save_config(config)
    return {"ok": True}

# ── Schedules ─────────────────────────────────────────────────────────────────

@app.get("/api/schedules")
async def get_schedules():
    return {"schedules": config.get("schedules", [])}

@app.post("/api/schedules")
async def create_schedule(schedule: Schedule):
    import uuid
    schedule.id = str(uuid.uuid4())[:8]
    config.setdefault("schedules", []).append(schedule.dict())
    save_config(config)
    return {"ok": True, "schedule": schedule}

@app.put("/api/schedules/{schedule_id}")
async def update_schedule(schedule_id: str, schedule: Schedule):
    schedules = config.get("schedules", [])
    for i, s in enumerate(schedules):
        if s["id"] == schedule_id:
            schedule.id = schedule_id
            schedules[i] = schedule.dict()
            save_config(config)
            return {"ok": True}
    raise HTTPException(404)

@app.delete("/api/schedules/{schedule_id}")
async def delete_schedule(schedule_id: str):
    config["schedules"] = [s for s in config.get("schedules", []) if s["id"] != schedule_id]
    save_config(config)
    return {"ok": True}

# ── Config ────────────────────────────────────────────────────────────────────

@app.get("/api/config")
async def get_config():
    safe = {k: v for k, v in config.items() if k != "govee_api_key"}
    safe["govee_configured"] = bool(config.get("govee_api_key"))
    safe["hue_configured"] = bool(config.get("hue_bridge_ip"))
    return safe

@app.put("/api/config")
async def update_config(body: ConfigUpdate):
    if body.hue_bridge_ip is not None:
        config["hue_bridge_ip"] = body.hue_bridge_ip
    if body.govee_api_key is not None:
        config["govee_api_key"] = body.govee_api_key
    save_config(config)
    return {"ok": True}

@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "kasa_lib": KASA_AVAILABLE,
        "hue_lib": HUE_AVAILABLE,
        "govee_lib": GOVEE_AVAILABLE,
        "devices_loaded": len(device_state),
        "timestamp": datetime.now().isoformat()
    }

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
