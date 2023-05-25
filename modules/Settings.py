# Optitrack settings
CLIENT_ADDRESS = None
OPTITRACK_ADDRESS = None
USE_MULTICAST = None

# Websocket settings
WEBSOCKET_SERVER_ADDRESS = None
WEBSOCKET_SERVER_PORT = None

# Logging settings
LOGGING_ON_STDOUT = True

# General settings (don't change these parameters unless you know what you are doing)
PROGRAM_SLEEP_TIME = 1
PROGRAM_LOOP_SLEEP_TIME = 1

if CLIENT_ADDRESS is None or OPTITRACK_ADDRESS is None or USE_MULTICAST is None or WEBSOCKET_SERVER_ADDRESS is None or WEBSOCKET_SERVER_PORT is None:
    raise ValueError("Please set all the settings in Settings.py")