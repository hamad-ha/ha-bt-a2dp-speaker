"""Bluetooth Audio – MediaPlayerEntity for Home Assistant."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval

from .bt_controller import BluetoothController, BtStatus
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
SCAN_INTERVAL = timedelta(seconds=15)

SUPPORTED_FEATURES = (
    MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.PAUSE
    | MediaPlayerEntityFeature.STOP
    | MediaPlayerEntityFeature.NEXT_TRACK
    | MediaPlayerEntityFeature.PREVIOUS_TRACK
    | MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.TURN_ON
    | MediaPlayerEntityFeature.TURN_OFF
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    mac = entry.data[CONF_MAC_ADDRESS]
    name = entry.data.get("name", mac)
    sink_hint = entry.data.get(CONF_SINK_NAME, "")
    controller = BluetoothController(mac=mac, sink_name_hint=sink_hint)
    async_add_entities(
        [BluetoothAudioEntity(hass, entry, controller, name, mac)],
        update_before_add=True,
    )


class BluetoothAudioEntity(MediaPlayerEntity):
    """Bluetooth Audio media player entity."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = SUPPORTED_FEATURES

    def __init__(self, hass, entry, controller, name, mac):
        self.hass = hass
        self._entry = entry
        self._ctrl = controller
        self._mac = mac
        self._friendly_name = name

        self._attr_unique_id = f"bluetooth_audio_{mac.replace(':', '_').lower()}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, mac)},
            name=name,
            manufacturer="Bluetooth",
            model="A2DP Audio Device",
            connections={("bluetooth", mac)},
        )

        self._bt_connected = False
        self._player_state = MediaPlayerState.OFF
        self._volume = 0.5
        self._muted = False
        self._media_title = None
        self._media_artist = None
        self._media_album = None
        self._idle_seconds = 0
        self._unsub_idle = None

    @property
    def state(self): return self._player_state
    @property
    def volume_level(self): return self._volume
    @property
    def is_volume_muted(self): return self._muted
    @property
    def media_title(self): return self._media_title
    @property
    def media_artist(self): return self._media_artist
    @property
    def media_album_name(self): return self._media_album

    @property
    def _opt_connect_on_play(self):
        return self._entry.options.get(CONF_CONNECT_ON_PLAY, DEFAULT_CONNECT_ON_PLAY)
    @property
    def _opt_disconnect_on_idle(self):
        return self._entry.options.get(CONF_DISCONNECT_ON_IDLE, DEFAULT_DISCONNECT_ON_IDLE)
    @property
    def _opt_idle_timeout(self):
        return self._entry.options.get(CONF_IDLE_TIMEOUT, DEFAULT_IDLE_TIMEOUT)

    async def async_added_to_hass(self):
        self._unsub_idle = async_track_time_interval(
            self.hass, self._async_idle_tick, timedelta(seconds=1)
        )

    async def async_will_remove_from_hass(self):
        if self._unsub_idle:
            self._unsub_idle()

    async def async_update(self):
        status = await self._ctrl.async_get_status()
        self._bt_connected = status == BtStatus.CONNECTED

        if not self._bt_connected:
            self._player_state = MediaPlayerState.OFF
            return

        player_status = await self._ctrl.async_get_player_status()
        if player_status == "playing":
            self._player_state = MediaPlayerState.PLAYING
            self._idle_seconds = 0
            info = await self._ctrl.async_get_track_info()
            self._media_title = info.get("title")
            self._media_artist = info.get("artist")
            self._media_album = info.get("album")
        elif player_status == "paused":
            self._player_state = MediaPlayerState.PAUSED
        else:
            self._player_state = MediaPlayerState.IDLE
            self._media_title = None
            self._media_artist = None
            self._media_album = None

        vol = await self._ctrl.async_get_volume()
        if vol is not None:
            self._volume = vol
        self._muted = await self._ctrl.async_get_mute()

    async def _async_idle_tick(self, _now):
        if not self._opt_disconnect_on_idle:
            return
        if self._player_state == MediaPlayerState.IDLE and self._bt_connected:
            self._idle_seconds += 1
            if self._idle_seconds >= self._opt_idle_timeout:
                await self._ctrl.async_disconnect()
                self._bt_connected = False
                self._player_state = MediaPlayerState.OFF
                self._idle_seconds = 0
                self.async_write_ha_state()
        else:
            self._idle_seconds = 0

    async def async_turn_on(self):
        success = await self._ctrl.async_connect()
        if success:
            self._bt_connected = True
            self._player_state = MediaPlayerState.IDLE
            await self._ctrl.async_find_sink()
        self.async_write_ha_state()

    async def async_turn_off(self):
        await self._ctrl.async_player_command("stop")
        await self._ctrl.async_disconnect()
        self._bt_connected = False
        self._player_state = MediaPlayerState.OFF
        self.async_write_ha_state()

    async def async_media_play(self):
        if not self._bt_connected and self._opt_connect_on_play:
            await self.async_turn_on()
        await self._ctrl.async_player_command("play")
        self._player_state = MediaPlayerState.PLAYING
        self.async_write_ha_state()

    async def async_media_pause(self):
        await self._ctrl.async_player_command("pause")
        self._player_state = MediaPlayerState.PAUSED
        self.async_write_ha_state()

    async def async_media_stop(self):
        await self._ctrl.async_player_command("stop")
        self._player_state = MediaPlayerState.IDLE
        self.async_write_ha_state()

    async def async_media_next_track(self):
        await self._ctrl.async_player_command("next")

    async def async_media_previous_track(self):
        await self._ctrl.async_player_command("previous")

    async def async_set_volume_level(self, volume: float):
        if not self._bt_connected:
            return
        success = await self._ctrl.async_set_volume(volume)
        if success:
            self._volume = volume
        self.async_write_ha_state()

    async def async_mute_volume(self, mute: bool):
        if not self._bt_connected:
            return
        success = await self._ctrl.async_set_mute(mute)
        if success:
            self._muted = mute
        self.async_write_ha_state()
