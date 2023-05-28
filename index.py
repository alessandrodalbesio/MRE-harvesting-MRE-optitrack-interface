from modules.Settings import *
import sys
import time
from modules.NatNetClient import *
from modules.LoggingUtils import logger
import traceback

if __name__ == '__main__':
    loggerManager = logger(log_on_stout = LOGGING_ON_STDOUT)

    ##### Initialize the streaming client #####
    try:
        # Log that the service is starting
        loggerManager.info("Starting service")

        # Create the NatNet client and define the various parameters
        streaming_client = NatNetClientRaspberry()
        streaming_client.set_client_address(CLIENT_ADDRESS)
        streaming_client.set_server_address(OPTITRACK_ADDRESS)
        streaming_client.set_use_multicast(USE_MULTICAST)
        streaming_client.set_websocket_connection_url(WEBSOCKET_SERVER_ADDRESS, is_DNS=True)
        streaming_client.set_logger(loggerManager)

        # Start up the streaming client
        is_running = streaming_client.run()
        if not is_running:
            loggerManager.error("Could not start streaming client.")
            streaming_client.shutdown()
            sys.exit(1)
        else:
            loggerManager.debug("Streaming client running")
        time.sleep(PROGRAM_SLEEP_TIME)

        # Check if the streaming client is connected to the server
        if streaming_client.connected() is False:
            loggerManager.error("Streaming client failed to connect to server at address: " + OPTITRACK_ADDRESS)
            streaming_client.shutdown()
            sys.exit(2)
        else:
            loggerManager.debug("Streaming client connected")
        time.sleep(PROGRAM_SLEEP_TIME)
    except Exception as e:
        logger.error("An exception occurred while initializing the streaming client. \n" + traceback.format_exc())
        streaming_client.shutdown()
        sys.exit(3)
    else:
        loggerManager.debug("Streaming client initialized successfully")


    ##### Run the streaming client loop #####
    exit_code = 0
    try:
        while True:
            time.sleep(PROGRAM_LOOP_SLEEP_TIME)
            if streaming_client.need_shutdown():
                break
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.error("ERROR: An exception occurred while running the streaming client loop.")
        exit_code = 4
    finally:
        streaming_client.shutdown()
        sys.exit(exit_code)