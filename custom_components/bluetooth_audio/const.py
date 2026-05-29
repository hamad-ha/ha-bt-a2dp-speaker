"""Constants for the Bluetooth Audio integration."""

DOMAIN = "bluetooth_audio"

# Config keys
CONF_MAC_ADDRESS = "mac_address"
CONF_SINK_NAME = "sink_name"

# Options keys
CONF_CONNECT_ON_PLAY = "connect_on_play"
CONF_DISCONNECT_ON_IDLE = "disconnect_on_idle"
CONF_IDLE_TIMEOUT = "idle_timeout"

# Defaults
DEFAULT_CONNECT_ON_PLAY = True
DEFAULT_DISCONNECT_ON_IDLE = True
DEFAULT_IDLE_TIMEOUT = 300

# Pulse socket path on HAOS
PULSE_SOCKET = "unix:/run/audio/pulse.sock"

# Bluetooth connection states
BT_STATE_CONNECTED = "connected"
BT_STATE_DISCONNECTED = "disconnected"
BT_STATE_CONNECTING = "connecting"
