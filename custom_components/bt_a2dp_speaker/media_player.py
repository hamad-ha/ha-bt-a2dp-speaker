"""Support for Bluetooth A2DP Speaker as Media Player."""
from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .bt_controller import BluetoothController


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Bluetooth speaker."""
    controller = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([BluetoothSpeakerMediaPlayer(config_entry, controller)])


class BluetoothSpeakerMediaPlayer(MediaPlayerEntity):
    """Representation of a Bluetooth A2DP Speaker."""

    _attr_should_poll = True
    _attr_supported_features = (
        MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.PLAY_MEDIA
    )

    def __init__(self, config_entry: ConfigEntry, controller: BluetoothController):
        self._controller = controller
        self._attr_name = config_entry.data.get("name", "P PRO3")
        self._attr_unique_id = config_entry.entry_id

    @property
    def state(self):
        return self._controller.state

    @property
    def volume_level(self):
        return self._controller.volume_level

    @property
    def is_volume_muted(self):
        return self._controller.is_muted

    async def async_turn_on(self):
        await self._controller.async_connect()

    async def async_turn_off(self):
        await self._controller.async_disconnect()

    async def async_media_play(self):
        await self._controller.async_play()

    async def async_media_pause(self):
        await self._controller.async_pause()

    async def async_media_stop(self):
        await self._controller.async_stop()

    async def async_set_volume_level(self, volume: float):
        await self._controller.async_set_volume(volume)

    async def async_mute_volume(self, mute: bool):
        await self._controller.async_mute(mute)

    async def async_play_media(self, media_type: str, media_content_id: str, **kwargs):
        """Play media (used by TTS)."""
        await self._controller.async_play_media(media_content_id)
