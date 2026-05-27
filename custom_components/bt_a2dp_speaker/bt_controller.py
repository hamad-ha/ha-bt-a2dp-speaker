"""Low-level Bluetooth and audio sink controller."""
from __future__ import annotations

import asyncio
import logging
import re
import shutil
from dataclasses import dataclass, field
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


async def _run(
    *args: str, timeout: int = 15
) -> tuple[int, str, str]:
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
    except Exception as exc:  # noqa: BLE001
        _LOGGER.error("Command error %s: %s", args, exc)
        return 1, "", str(exc)


class BluetoothController:
    """Manages Bluetooth connection via bluetoothctl and audio via pactl."""

    # Prefer pactl (PulseAudio) over pw-cli for broad compatibility
    _PACTL = "pactl"
    _BLUETOOTHCTL = "bluetoothctl"

    def __init__(self, mac: str, sink_name_hint: str = "") -> None:
        self.mac = mac.upper()
        self.sink_name_hint = sink_name_hint
        self._resolved_sink: str | None = None
        self._has_pactl: bool = bool(shutil.which(self._PACTL))
        self._has_bluetoothctl: bool = bool(shutil.which(self._BLUETOOTHCTL))

    # ------------------------------------------------------------------
    # Bluetooth connect / disconnect
    # ------------------------------------------------------------------

    async def async_get_status(self) -> BtStatus:
        """Return current BT connection status."""
        if not self._has_bluetoothctl:
            return BtStatus.UNKNOWN
        rc, stdout, _ = await _run(self._BLUETOOTHCTL, "info", self.mac)
        if rc != 0:
            return BtStatus.DISCONNECTED
        if "Connected: yes" in stdout:
            return BtStatus.CONNECTED
        return BtStatus.DISCONNECTED

    async def async_connect(self) -> bool:
        """Connect the BT device. Returns True on success."""
        if not self._has_bluetoothctl:
            _LOGGER.error("bluetoothctl not available")
            return False
        _LOGGER.debug("Connecting to %s", self.mac)
        rc, stdout, stderr = await _run(
            self._BLUETOOTHCTL, "connect", self.mac, timeout=30
        )
        success = rc == 0 and "Connection successful" in stdout
        if not success:
            _LOGGER.warning(
                "BT connect failed rc=%s stdout=%s stderr=%s", rc, stdout, stderr
            )
        return success

    async def async_disconnect(self) -> bool:
        """Disconnect the BT device."""
        if not self._has_bluetoothctl:
            return False
        rc, _, _ = await _run(self._BLUETOOTHCTL, "disconnect", self.mac, timeout=15)
        return rc == 0

    async def async_is_paired(self) -> bool:
        """Check pairing status."""
        if not self._has_bluetoothctl:
            return False
        _, stdout, _ = await _run(self._BLUETOOTHCTL, "info", self.mac)
        return "Paired: yes" in stdout

    # ------------------------------------------------------------------
    # Sink discovery
    # ------------------------------------------------------------------

    async def async_find_sink(self) -> SinkInfo | None:
        """Locate the PulseAudio/PipeWire sink for this BT device."""
        if not self._has_pactl:
            _LOGGER.warning("pactl not available; volume control disabled")
            return None

        # Short wait for the A2DP sink to register after connect
        await asyncio.sleep(1.5)

        rc, stdout, _ = await _run(self._PACTL, "list", "sinks")
        if rc != 0:
            return None

        # Parse pactl list sinks output into blocks
        blocks = re.split(r"\nSink #", stdout)
        mac_key = self.mac.replace(":", "_").lower()

        for block in blocks:
            lines = block.splitlines()
            index = lines[0].strip().lstrip("Sink #").strip() if lines else ""

            # Collect Name: and Description: from the block
            name = ""
            description = ""
            volume_pct = 50
            muted = False

            for line in lines:
                stripped = line.strip()
                if stripped.startswith("Name:"):
                    name = stripped.split("Name:", 1)[1].strip()
                elif stripped.startswith("Description:"):
                    description = stripped.split("Description:", 1)[1].strip()
                elif stripped.startswith("Mute:"):
                    muted = "yes" in stripped.lower()
                elif stripped.startswith("Volume:"):
                    # e.g. "Volume: front-left: 65536 /  100% / ..."
                    m = re.search(r"(\d+)%", stripped)
                    if m:
                        volume_pct = int(m.group(1))

            # Match by hint or by MAC address embedded in sink name
            is_match = (
                (self.sink_name_hint and self.sink_name_hint in name)
                or mac_key in name.lower()
                or "bluez" in name.lower()
            )

            if is_match:
                _LOGGER.debug("Matched sink: %s (%s)", name, description)
                self._resolved_sink = name
                return SinkInfo(
                    index=index,
                    name=name,
                    description=description,
                    volume_percent=volume_pct,
                    muted=muted,
                )

        _LOGGER.debug("No matching sink found for %s", self.mac)
        return None

    # ------------------------------------------------------------------
    # Volume / mute
    # ------------------------------------------------------------------

    async def async_set_volume(self, volume: float) -> bool:
        """Set volume (0.0–1.0) via pactl."""
        sink = await self._ensure_sink()
        if not sink:
            return False
        pct = max(0, min(100, int(volume * 100)))
        rc, _, _ = await _run(self._PACTL, "set-sink-volume", sink, f"{pct}%")
        return rc == 0

    async def async_set_mute(self, mute: bool) -> bool:
        """Mute or unmute."""
        sink = await self._ensure_sink()
        if not sink:
            return False
        rc, _, _ = await _run(
            self._PACTL, "set-sink-mute", sink, "1" if mute else "0"
        )
        return rc == 0

    async def async_get_volume(self) -> float | None:
        """Return current volume as 0.0–1.0."""
        sink_info = await self.async_find_sink()
        if sink_info is None:
            return None
        return sink_info.volume_percent / 100.0

    # ------------------------------------------------------------------
    # Media control (via playerctl – controls whatever is playing into the sink)
    # ------------------------------------------------------------------

    async def async_player_command(self, cmd: str) -> bool:
        """Send a playerctl command (play, pause, next, previous, stop)."""
        if not shutil.which("playerctl"):
            _LOGGER.debug("playerctl not available; skipping %s", cmd)
            return False
        rc, _, _ = await _run("playerctl", cmd, timeout=5)
        return rc == 0

    async def async_get_player_status(self) -> str | None:
        """Return playerctl status string or None."""
        if not shutil.which("playerctl"):
            return None
        rc, stdout, _ = await _run("playerctl", "status", timeout=5)
        if rc == 0:
            return stdout.strip().lower()  # 'playing', 'paused', 'stopped'
        return None

    async def async_get_track_info(self) -> dict[str, str]:
        """Return current track metadata from playerctl."""
        info: dict[str, str] = {}
        if not shutil.which("playerctl"):
            return info
        for key, field in (
            ("title", "title"),
            ("artist", "artist"),
            ("album", "album"),
        ):
            rc, stdout, _ = await _run(
                "playerctl", "metadata", f"xesam:{field}", timeout=5
            )
            if rc == 0 and stdout.strip():
                info[key] = stdout.strip()
        return info

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _ensure_sink(self) -> str | None:
        if self._resolved_sink:
            return self._resolved_sink
        info = await self.async_find_sink()
        return info.name if info else None
