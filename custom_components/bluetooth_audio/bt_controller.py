"""Low-level Bluetooth and audio sink controller - optimised for HAOS."""
from __future__ import annotations

import asyncio
import logging
import re
import shutil
from enum import Enum

_LOGGER = logging.getLogger(__name__)

# HAOS PulseAudio socket
PULSE_ENV = {"PULSE_SERVER": "unix:/run/audio/pulse.sock"}


class BtStatus(str, Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    UNKNOWN = "unknown"


async def _run(*args: str, timeout: int = 15, env_extra: dict | None = None) -> tuple[int, str, str]:
    import os
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
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
    """Manages BT connection and audio via bluetoothctl + pactl on HAOS."""

    def __init__(self, mac: str, sink_name_hint: str = "") -> None:
        self.mac = mac.upper()
        self.sink_name_hint = sink_name_hint
        # Build the expected sink name from MAC
        self._auto_sink = f"bluez_sink.{mac.upper().replace(':', '_')}.a2dp_sink"
        self._resolved_sink: str | None = sink_name_hint if sink_name_hint else None

    # ------------------------------------------------------------------
    # Bluetooth
    # ------------------------------------------------------------------

    async def async_get_status(self) -> BtStatus:
        rc, stdout, _ = await _run("bluetoothctl", "info", self.mac)
        if rc != 0:
            return BtStatus.DISCONNECTED
        if "Connected: yes" in stdout:
            return BtStatus.CONNECTED
        return BtStatus.DISCONNECTED

    async def async_connect(self) -> bool:
        _LOGGER.debug("Connecting to %s", self.mac)
        rc, stdout, _ = await _run("bluetoothctl", "connect", self.mac, timeout=30)
        return rc == 0 and "Connection successful" in stdout

    async def async_disconnect(self) -> bool:
        rc, _, _ = await _run("bluetoothctl", "disconnect", self.mac, timeout=15)
        return rc == 0

    async def async_is_paired(self) -> bool:
        _, stdout, _ = await _run("bluetoothctl", "info", self.mac)
        return "Paired: yes" in stdout

    # ------------------------------------------------------------------
    # Sink discovery (HAOS PulseAudio)
    # ------------------------------------------------------------------

    async def async_find_sink(self) -> str | None:
        """Return sink name, preferring the auto-derived bluez sink name."""
        # Try the known auto sink name first
        rc, stdout, _ = await _run(
            "pactl", "list", "sinks", "short", env_extra=PULSE_ENV
        )
        if rc != 0:
            _LOGGER.warning("pactl list sinks failed")
            return None

        for line in stdout.splitlines():
            # line format: index  name  module  sample  state
            parts = line.split()
            if len(parts) < 2:
                continue
            name = parts[1]
            if (
                self._auto_sink in name
                or (self.sink_name_hint and self.sink_name_hint in name)
                or self.mac.replace(":", "_").upper() in name.upper()
            ):
                self._resolved_sink = name
                _LOGGER.debug("Resolved sink: %s", name)
                return name

        _LOGGER.debug("Sink not found for %s", self.mac)
        return None

    async def _ensure_sink(self) -> str | None:
        if self._resolved_sink:
            return self._resolved_sink
        return await self.async_find_sink()

    # ------------------------------------------------------------------
    # Volume / mute via pactl
    # ------------------------------------------------------------------

    async def async_set_volume(self, volume: float) -> bool:
        sink = await self._ensure_sink()
        if not sink:
            return False
        pct = max(0, min(100, int(volume * 100)))
        rc, _, _ = await _run(
            "pactl", "set-sink-volume", sink, f"{pct}%", env_extra=PULSE_ENV
        )
        return rc == 0

    async def async_set_mute(self, mute: bool) -> bool:
        sink = await self._ensure_sink()
        if not sink:
            return False
        rc, _, _ = await _run(
            "pactl", "set-sink-mute", sink, "1" if mute else "0", env_extra=PULSE_ENV
        )
        return rc == 0

    async def async_get_volume(self) -> float | None:
        sink = await self._ensure_sink()
        if not sink:
            return None
        rc, stdout, _ = await _run(
            "pactl", "list", "sinks", env_extra=PULSE_ENV
        )
        if rc != 0:
            return None
        in_block = False
        for line in stdout.splitlines():
            if sink in line:
                in_block = True
            if in_block and "Volume:" in line:
                m = re.search(r"(\d+)%", line)
                if m:
                    return int(m.group(1)) / 100.0
        return None

    async def async_get_mute(self) -> bool:
        sink = await self._ensure_sink()
        if not sink:
            return False
        rc, stdout, _ = await _run(
            "pactl", "list", "sinks", env_extra=PULSE_ENV
        )
        if rc != 0:
            return False
        in_block = False
        for line in stdout.splitlines():
            if sink in line:
                in_block = True
            if in_block and "Mute:" in line:
                return "yes" in line.lower()
        return False

    # ------------------------------------------------------------------
    # Playback control via playerctl
    # ------------------------------------------------------------------

    async def async_player_command(self, cmd: str) -> bool:
        if not shutil.which("playerctl"):
            return False
        rc, _, _ = await _run("playerctl", cmd, timeout=5)
        return rc == 0

    async def async_get_player_status(self) -> str | None:
        if not shutil.which("playerctl"):
            return None
        rc, stdout, _ = await _run("playerctl", "status", timeout=5)
        if rc == 0:
            return stdout.strip().lower()
        return None

    async def async_get_track_info(self) -> dict[str, str]:
        info: dict[str, str] = {}
        if not shutil.which("playerctl"):
            return info
        for key, field in (("title", "title"), ("artist", "artist"), ("album", "album")):
            rc, stdout, _ = await _run(
                "playerctl", "metadata", f"xesam:{field}", timeout=5
            )
            if rc == 0 and stdout.strip():
                info[key] = stdout.strip()
        return info
