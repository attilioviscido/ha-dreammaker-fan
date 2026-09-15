"""Constants for the Dream Maker Fan integration.

Protocollo "dmiot" riverso-ingegnerizzato dal progetto
https://github.com/klada/dmiot2mqtt (klada, GPLv3). Questa integrazione
riscrive la stessa logica come custom_component nativo di Home Assistant
(niente MQTT, niente processo esterno): il ventilatore si collega
direttamente a Home Assistant tramite lo stesso trucco (redirect DNS di
cloud1.dm-maker.com verso l'host di Home Assistant).
"""

DOMAIN = "dreammaker_fan"

DEFAULT_PORT = 31270

SIGNAL_NEW_DEVICE = f"{DOMAIN}_new_device"

MANUFACTURER = "Dream Maker"

MODE_MAP = {0: "direct", 1: "natural", 2: "smart"}
MODE_MAP_REVERSE = {v: k for k, v in MODE_MAP.items()}

ANGLE_OPTIONS = ["30", "60", "90", "120", "140"]

RESOURCE_STATUS = 127
RESOURCE_STATE = 9031
ACTION_REQUEST = 1
ACTION_ACK = 81
ACTION_COMMAND = 4
ACTION_STATE_PUSH = 84
