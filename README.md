# Bluetooth Audio – Home Assistant Custom Integration

Expose any Bluetooth A2DP speaker or headset as a **media_player** entity in Home Assistant.

## Tested on
- Home Assistant OS 2026.x on Raspberry Pi 5
- Speaker: Any A2DP Bluetooth device

## Features
- Turn on / off (connect / disconnect)
- Play, Pause, Stop, Next, Previous
- Volume control + mute
- Track metadata (title, artist, album)
- Auto-connect on play
- Auto-disconnect on idle
- Full UI config flow – no YAML needed

## Installation

### Manual
1. Copy `bluetooth_audio/` into `<config>/custom_components/`
2. Restart Home Assistant
3. Settings → Devices & Services → Add Integration → **Bluetooth Audio**

### HACS
1. HACS → Integrations → Custom repositories
2. Add this repo URL, category: Integration
3. Install and restart

## Setup
1. Pair your speaker first via SSH:
```bash
bluetoothctl
power on
agent on
scan on
pair AA:BB:CC:DD:EE:FF
trust AA:BB:CC:DD:EE:FF
connect AA:BB:CC:DD:EE:FF
quit
```
2. Add the integration in HA UI
3. Enter the MAC address — sink name is auto-detected

## License
MIT
