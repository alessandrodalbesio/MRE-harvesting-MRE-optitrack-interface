from modules.settings import *
from modules.NatNetClient import *

if __name__ == '__main__': 
    try:
        ##### Initialize the streaming client #####
        streaming_client = NatNetClient()
        streaming_client.set_client_address(CLIENT_ADDRESS)
        streaming_client.set_server_address(OPTITRACK_ADDRESS)
        streaming_client.set_use_multicast(USE_MULTICAST)
        streaming_client.set_websocket_connection_url(WEBSOCKET_SERVER_ADDRESS, is_DNS=IS_WEBSOCKET_ADDRESS_DNS)

        ##### Start the streaming client #####
        streaming_client.start()

        ##### Run the streaming client loop #####
        streaming_client.run()
    except Exception as e:
        pass