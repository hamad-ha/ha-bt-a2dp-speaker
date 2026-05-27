"""Constants for the Bluetooth A2DP Speaker integration."""

DOMAIN = "bt_a2dp_speaker"
PLATFORMS = ["media_player"]

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
DEFAULT_IDLE_TIMEOUT = 300  # 5 minutes

# Bluetooth connection states
BT_STATE_CONNECTED = "connected"
BT_STATE_DISCONNECTED = "disconnected"
BT_STATE_CONNECTING = "connecting"

# bluetoothctl / bluez exit codes
BLUEZ_CONNECT_SUCCESS = 0
