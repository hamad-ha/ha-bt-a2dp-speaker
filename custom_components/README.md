# Bluetooth A2DP Speaker – Home Assistant Custom Integration

Expose a Bluetooth A2DP speaker (headphones, sound bar, etc.) as a full **media_player** entity in Home Assistant.

---

## Features

| Capability | Notes |
|---|---|
| Turn on / off | Connects or disconnects via `bluetoothctl` |
| Play / Pause / Stop / Next / Previous | Controlled via `playerctl` |
| Volume set + mute | Via `pactl` (PulseAudio / PipeWire) |
| Track metadata | Title, artist, album from MPRIS |
| Auto-connect on play | Optional (enabled by default) |
| Auto-disconnect on idle | Optional, configurable timeout |
| UI config flow | Set up from the HA GUI — no YAML needed |

---

## Requirements

Your Home Assistant host (typically Raspberry Pi / x86 Linux) needs:

```bash
# Bluetooth
sudo apt install bluez

# PulseAudio or PipeWire (usually pre-installed)
sudo apt install pulseaudio  # OR pipewire-pulse

# playerctl for media key control (optional but recommended)
sudo apt install playerctl
```

The speaker **must already be paired** with the host before adding this integration. Pair once with:

```bash
bluetoothctl
> power on
> agent on
> scan on
# ... find your device MAC ...
> pair AA:BB:CC:DD:EE:FF
> trust AA:BB:CC:DD:EE:FF
> quit
```

---

## Installation

### HACS (recommended)

1. In HACS → Integrations → ⋮ → **Custom repositories**
2. Add your repo URL, category **Integration**
3. Search "Bluetooth A2DP Speaker" and install

### Manual

1. Copy the `bt_a2dp_speaker/` folder into `<config>/custom_components/`
2. Restart Home Assistant

---

## Setup

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **Bluetooth A2DP Speaker**
3. Enter:
   - **Friendly name** – e.g. `Living Room Speaker`
   - **MAC address** – e.g. `AA:BB:CC:DD:EE:FF`
   - **Sink name hint** *(optional)* – part of the PulseAudio sink name if auto-detection fails

A new `media_player.*` entity will appear immediately.

---

## Options

After setup, click **Configure** on the integration card:

| Option | Default | Description |
|---|---|---|
| Auto-connect when playback starts | ✅ | Calls `turn_on` automatically if you call `play` while disconnected |
| Disconnect when idle | ✅ | Saves battery / power |
| Idle timeout (seconds) | 300 | How long to wait before auto-disconnect |

---

## How it works

```
Home Assistant service call
        │
        ▼
  media_player.py  (MediaPlayerEntity)
        │
        ▼
  bt_controller.py
   ├── bluetoothctl connect / disconnect / info
   ├── pactl set-sink-volume / set-sink-mute / list sinks
   └── playerctl play / pause / next / previous / status / metadata
```

- **State polling** runs every 15 seconds (`async_update`).
- **Idle timer** ticks every second in the background.
- The integration is entirely local — no cloud, no external API.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Entity stuck `off` / won't connect | Run `bluetoothctl info AA:BB:CC:DD:EE:FF` on the host — confirm `Paired: yes` |
| Volume control not working | Run `pactl list sinks short` — confirm a `bluez` sink appears when connected |
| Track info missing | Install `playerctl`; check `playerctl status` in a terminal while playing |
| Sink not found automatically | Set the **Sink name hint** option to part of the sink name from `pactl list sinks short` |
| HA can't run `bluetoothctl` | Add the `homeassistant` user to the `bluetooth` group: `sudo usermod -aG bluetooth homeassistant` |

---

## Automation examples

```yaml
# Turn on speaker at sunset
automation:
  trigger:
    platform: sun
    event: sunset
  action:
    service: media_player.turn_on
    target:
      entity_id: media_player.living_room_speaker

# Pause when everyone leaves home
automation:
  trigger:
    platform: state
    entity_id: group.household
    to: not_home
  action:
    service: media_player.media_pause
    target:
      entity_id: media_player.living_room_speaker
```

---

## License

MIT
