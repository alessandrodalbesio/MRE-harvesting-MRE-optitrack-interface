# Optitrack settings
CLIENT_ADDRESS = "10.99.2.60"
OPTITRACK_ADDRESS = "10.99.2.4"
USE_MULTICAST = True

# Define the ID of the rigidbody to track (DO NOT CHANGE. BE SURE THAT THESE DATA ARE THE SAME IN THE MOTIVE PROJECT)
HOLDER_RIGIDBODY_ID = 100
HOLDER_RIGIDBODY_REF_NAME = "Holder"
OBJECT_RIGIDBODY_ID = 101
OBJECT_RIGIDBODY_REF_NAME = "Raspberry"
HEADSET_RIGIDBODY_ID = 102
HEADSET_RIGIDBODY_REF_NAME = "Headset"

# Websocket settings
WEBSOCKET_SERVER_ADDRESS = "virtualenv.epfl.ch/ws"
MAX_ATTEMPTS_TO_CONNECT = 5 # Number of attempts to connect to the websocket server before giving up

# Logging settings
LOGGING_ON_STDOUT = True

# General settings (don't change these parameters unless you know what you are doing)
PROGRAM_SLEEP_TIME = 1
PROGRAM_LOOP_SLEEP_TIME = 1

if CLIENT_ADDRESS is None or OPTITRACK_ADDRESS is None or USE_MULTICAST is None or WEBSOCKET_SERVER_ADDRESS is None:
    raise ValueError("Please set all the settings in Settings.py")