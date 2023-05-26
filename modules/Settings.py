# Optitrack settings
CLIENT_ADDRESS = "10.99.2.60"
OPTITRACK_ADDRESS = "10.99.2.4"
USE_MULTICAST = True

# Websocket settings
WEBSOCKET_SERVER_ADDRESS = "10.42.0.1"
WEBSOCKET_SERVER_PORT = "9600"

# Logging settings
LOGGING_ON_STDOUT = True

# General settings (don't change these parameters unless you know what you are doing)
PROGRAM_SLEEP_TIME = 1
PROGRAM_LOOP_SLEEP_TIME = 1

if CLIENT_ADDRESS is None or OPTITRACK_ADDRESS is None or USE_MULTICAST is None or WEBSOCKET_SERVER_ADDRESS is None or WEBSOCKET_SERVER_PORT is None:
    raise ValueError("Please set all the settings in Settings.py")