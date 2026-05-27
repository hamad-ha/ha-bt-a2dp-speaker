"""Config flow for Bluetooth A2DP Speaker."""
from __future__ import annotations

import re
import asyncio
import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    DOMAIN,
    CONF_MAC_ADDRESS,
    CONF_SINK_NAME,
    CONF_CONNECT_ON_PLAY,
    CONF_DISCONNECT_ON_IDLE,
    CONF_IDLE_TIMEOUT,
    DEFAULT_CONNECT_ON_PLAY,
    DEFAULT_DISCONNECT_ON_IDLE,
    DEFAULT_IDLE_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)

MAC_REGEX = re.compile(r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")


def _validate_mac(mac: str) -> bool:
    return bool(MAC_REGEX.match(mac.strip()))


async def _async_check_device_paired(mac: str) -> bool:
    """Check if the BT device is paired via bluetoothctl."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "bluetoothctl", "info", mac.upper(),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
        return b"Paired: yes" in stdout
    except Exception as exc:  # noqa: BLE001
        _LOGGER.debug("bluetoothctl check failed: %s", exc)
        return False


class BtA2dpSpeakerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Bluetooth A2DP Speaker."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            mac = user_input[CONF_MAC_ADDRESS].strip().upper()
            user_input[CONF_MAC_ADDRESS] = mac

            if not _validate_mac(mac):
                errors[CONF_MAC_ADDRESS] = "invalid_mac"
            else:
                # Prevent duplicate entries for the same device
                await self.async_set_unique_id(mac)
                self._abort_if_unique_id_configured()

                paired = await _async_check_device_paired(mac)
                if not paired:
                    errors["base"] = "device_not_found"

            if not errors:
                return self.async_create_entry(
                    title=user_input.get("name", mac),
                    data=user_input,
                )

        schema = vol.Schema(
            {
                vol.Required("name", default="BT Speaker"): str,
                vol.Required(CONF_MAC_ADDRESS): str,
                vol.Optional(CONF_SINK_NAME, default=""): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> BtA2dpSpeakerOptionsFlow:
        """Return the options flow handler."""
        return BtA2dpSpeakerOptionsFlow(config_entry)


class BtA2dpSpeakerOptionsFlow(config_entries.OptionsFlow):
    """Handle options for Bluetooth A2DP Speaker."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        opts = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_CONNECT_ON_PLAY,
                    default=opts.get(CONF_CONNECT_ON_PLAY, DEFAULT_CONNECT_ON_PLAY),
                ): bool,
                vol.Optional(
                    CONF_DISCONNECT_ON_IDLE,
                    default=opts.get(CONF_DISCONNECT_ON_IDLE, DEFAULT_DISCONNECT_ON_IDLE),
                ): bool,
                vol.Optional(
                    CONF_IDLE_TIMEOUT,
                    default=opts.get(CONF_IDLE_TIMEOUT, DEFAULT_IDLE_TIMEOUT),
                ): vol.All(int, vol.Range(min=30, max=3600)),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
