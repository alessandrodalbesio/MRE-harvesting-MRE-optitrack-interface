
# Optitrack settings
CLIENT_ADDRESS = "10.99.2.243" # Client Address ( it should be the address given by ZeroTier )
OPTITRACK_ADDRESS = "10.99.2.4" # Optitrack Address ( it should be the address given by ZeroTier )
USE_MULTICAST = True # Optitrack uses multicast to send data. If you are not using multicast, set this to False

# Define the ID of the rigidbody to track (DO NOT CHANGE. BE SURE THAT THESE DATA ARE THE SAME IN THE MOTIVE PROJECT)
HOLDER_RIGIDBODY_ID = 100
HOLDER_RIGIDBODY_REF_NAME = "Holder"
OBJECT_RIGIDBODY_ID = 101
OBJECT_RIGIDBODY_REF_NAME = "Raspberry"
HEADSET_RIGIDBODY_ID = 102
HEADSET_RIGIDBODY_REF_NAME = "Headset"

# Websocket settings
WEBSOCKET_SERVER_ADDRESS = "virtualenv.epfl.ch/ws" # Address of the websocket server
IS_WEBSOCKET_ADDRESS_DNS = True # If True, the websocket address will be resolved using DNS. If False, the websocket address will be resolved using the IP address
MAX_ATTEMPTS_TO_CONNECT = 5 # If the websocket client fails to connect to the server, it will try again MAX_ATTEMPTS_TO_CONNECT times

# Logging settings
LOGGING_ON_STDOUT = True # If True, the logs will be printed on the console

# Program settings
PROGRAM_SLEEP_TIME = 1
PROGRAM_LOOP_SLEEP_TIME = 1
