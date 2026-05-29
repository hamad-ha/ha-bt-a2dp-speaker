"""Config flow for Bluetooth Audio."""
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


async def _async_check_device_paired(mac: str) -> bool:
    try:
        proc = await asyncio.create_subprocess_exec(
            "bluetoothctl", "info", mac.upper(),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
        return b"Paired: yes" in stdout
    except Exception:
        return False


class BluetoothAudioConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Bluetooth Audio."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            mac = user_input[CONF_MAC_ADDRESS].strip().upper()
            user_input[CONF_MAC_ADDRESS] = mac

            if not MAC_REGEX.match(mac):
                errors[CONF_MAC_ADDRESS] = "invalid_mac"
            else:
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

        # Auto-suggest the sink name based on MAC if provided
        default_mac = ""
        schema = vol.Schema({
            vol.Required("name", default="Bluetooth Speaker"): str,
            vol.Required(CONF_MAC_ADDRESS, default=default_mac): str,
            vol.Optional(CONF_SINK_NAME, default=""): str,
        })

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> "BluetoothAudioOptionsFlow":
        return BluetoothAudioOptionsFlow(config_entry)


class BluetoothAudioOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        opts = self.config_entry.options
        schema = vol.Schema({
            vol.Optional(CONF_CONNECT_ON_PLAY, default=opts.get(CONF_CONNECT_ON_PLAY, DEFAULT_CONNECT_ON_PLAY)): bool,
            vol.Optional(CONF_DISCONNECT_ON_IDLE, default=opts.get(CONF_DISCONNECT_ON_IDLE, DEFAULT_DISCONNECT_ON_IDLE)): bool,
            vol.Optional(CONF_IDLE_TIMEOUT, default=opts.get(CONF_IDLE_TIMEOUT, DEFAULT_IDLE_TIMEOUT)): vol.All(int, vol.Range(min=30, max=3600)),
        })
        return self.async_show_form(step_id="init", data_schema=schema)
