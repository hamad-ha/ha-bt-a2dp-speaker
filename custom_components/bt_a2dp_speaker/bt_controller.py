"""Low-level Bluetooth and audio sink controller."""
from __future__ import annotations

import asyncio
import logging
import re
import shutil
from dataclasses import dataclass
from enum import Enum

_LOGGER = logging.getLogger(__name__)


class BtStatus(str, Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    UNKNOWN = "unknown"


@dataclass
class SinkInfo:
    index: str
    name: str
    description: str
    volume_percent: int = 50
    muted: bool = False


async def _run(*args: str, timeout: int = 15) -> tuple[int, str, str]:
    """Run a subprocess and return (returncode, stdout, stderr)."""
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return proc.returncode or 0, stdout.decode(), stderr.decode()
    except asyncio.TimeoutError:
        _LOGGER.warning("Command timed out: %s", args)
        return 1, "", "timeout"
    except FileNotFoundError:
        _LOGGER.error("Command not found: %s", args[0])
        return 127, "", f"{args[0]} not found"
    except Exception as exc:
        _LOGGER.error("Command error %s: %s", args, exc)
        return 1, "", str(exc)


class BluetoothController:
    """Manages Bluetooth connection + audio sink."""

    _PACTL = "pactl"
    _BLUETOOTHCTL = "bluetoothctl"
    _PLAYERCTL = "playerctl"

    def __init__(self, mac: str, sink_name_hint: str = "") -> None:
        self.mac = mac.upper()
        self.sink_name_hint = sink_name_hint
        self._resolved_sink: str | None = None
        self._has_pactl = bool(shutil.which(self._PACTL))
        self._has_bluetoothctl = bool(shutil.which(self._BLUETOOTHCTL))
        self._state = "idle"
        self._volume_level = 0.5
        self._is_muted = False

    # ==================== Bluetooth ====================

    async def async_connect(self) -> bool:
        if not self._has_bluetoothctl:
            return False
        rc, _, _ = await _run(self._BLUETOOTHCTL, "connect", self.mac, timeout=25)
        return rc == 0

    async def async_disconnect(self) -> bool:
        if not self._has_bluetoothctl:
            return False
        await _run(self._BLUETOOTHCTL, "disconnect", self.mac)
        return True

    async def async_get_status(self) -> str:
        if not self._has_bluetoothctl:
            return "disconnected"
        _, stdout, _ = await _run(self._BLUETOOTHCTL, "info", self.mac)
        return "connected" if "Connected: yes" in stdout else "disconnected"

    # ==================== Sink & Volume ====================

    async def _ensure_sink(self) -> str | None:
        if self._resolved_sink:
            return self._resolved_sink
        # Try to find sink
        await asyncio.sleep(1)
        rc, stdout, _ = await _run(self._PACTL, "list", "sinks")
        if rc != 0:
            return None
        mac_key = self.mac.replace(":", "_").lower()
        for line in stdout.splitlines():
            if mac_key in line.lower() or "bluez" in line.lower():
                self._resolved_sink = line.strip().split()[-1] if line.strip() else None
                return self._resolved_sink
        return None

    async def async_set_volume(self, volume: float) -> bool:
        sink = await self._ensure_sink()
        if not sink:
            return False
        pct = int(volume * 100)
        rc, _, _ = await _run(self._PACTL, "set-sink-volume", sink, f"{pct}%")
        if rc == 0:
            self._volume_level = volume
        return rc == 0

    async def async_mute(self, mute: bool) -> bool:
        sink = await self._ensure_sink()
        if not sink:
            return False
        rc, _, _ = await _run(self._PACTL, "set-sink-mute", sink, "1" if mute else "0")
        if rc == 0:
            self._is_muted = mute
        return rc == 0

    # ==================== Media Control ====================

    async def async_play(self):
        await _run(self._PLAYERCTL, "play")

    async def async_pause(self):
        await _run(self._PLAYERCTL, "pause")

    async def async_stop(self):
        await _run(self._PLAYERCTL, "stop")

    async def async_play_media(self, media_content_id: str):
        """Play a URL (important for TTS)."""
        if media_content_id.startswith("http"):
            await _run(self._PLAYERCTL, "open", media_content_id)
        else:
            _LOGGER.warning("Only HTTP URLs supported for play_media currently")

    # ==================== Properties ====================

    @property
    def state(self) -> str:
        return self._state

    @property
    def volume_level(self) -> float:
        return self._volume_level

    @property
    def is_muted(self) -> bool:
        return self._is_muted