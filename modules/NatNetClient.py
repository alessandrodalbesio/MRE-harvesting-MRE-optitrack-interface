﻿# Copyright © 2018 Naturalpoint
#
# Licensed under the Apache License, Version 2.0 (the "License")
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# OptiTrack NatNet direct depacketization library for Python 3.x

##### This is a modified version of the original NatNetClient module. #####

# Import all the needed libraries
import socket
import struct
from threading import Thread
import copy
import time
import modules.DataDescriptions as DataDescriptions
import modules.MoCapData as MoCapData
import websockets
import json
from modules.settings import *
import traceback
import sys
import asyncio
import signal
from modules.logging import logger
import random


# Function used by the NatNetClient class to print the messages. Uncomment the one you want to use.
def trace( *args ):
    #  print( "".join(map(str,args)) )
    pass

#Used for Data Description functions
def trace_dd( *args ):
    #print( "".join(map(str,args)) )
    pass

#Used for MoCap Frame Data functions
def trace_mf( *args ):
    # print( "".join(map(str,args)) )
    pass

# Create structs for reading various object types to speed up parsing.
Vector2 = struct.Struct( '<ff' )
Vector3 = struct.Struct( '<fff' )
Quaternion = struct.Struct( '<ffff' )
FloatValue = struct.Struct( '<f' )
DoubleValue = struct.Struct( '<d' )
NNIntValue = struct.Struct( '<I')
FPCalMatrixRow = struct.Struct( '<ffffffffffff' )
FPCorners      = struct.Struct( '<ffffffffffff')

class NetworkConnectionError(Exception):
    pass

class WebsocketConnectionLost(Exception):
    pass

# Definition of the personalized NatNetClient class
class NatNetClient:   
    # Client/server message ids
    NAT_CONNECT               = 0
    NAT_SERVERINFO            = 1
    NAT_REQUEST               = 2
    NAT_RESPONSE              = 3
    NAT_REQUEST_MODELDEF      = 4
    NAT_MODELDEF              = 5
    NAT_REQUEST_FRAMEOFDATA   = 6
    NAT_FRAMEOFDATA           = 7
    NAT_MESSAGESTRING         = 8
    NAT_DISCONNECT            = 9
    NAT_KEEPALIVE             = 10
    NAT_UNRECOGNIZED_REQUEST  = 100
    NAT_UNDEFINED             = 999999.9999

    # Costructor of the class
    def __init__( self ):
        self.logger = logger(log_on_stout = LOGGING_ON_STDOUT)
        # Verify that the connection is working
        if(self.check_connection() == False):
            self.logger.error("ERROR: No internet connection. Please connect to internet and try again.")
            raise NetworkConnectionError

        # Change this value to the IP address of the NatNet server.
        self.server_ip_address = "127.0.0.1"

        # Change this value to the IP address of your local network interface
        self.local_ip_address = "127.0.0.1"

        # This should match the multicast address listed in Motive's streaming settings.
        self.multicast_address = "239.255.42.99"

        # NatNet Command channel
        self.command_port = 1510

        # NatNet Data channel
        self.data_port = 1511

        # Define if you want to use multicast or unicast
        self.use_multicast = True

        # Set this to a callback method of your choice to receive per-rigid-body data at each frame.
        self.rigid_body_listener = None
        self.new_frame_listener  = None

        # Set Application Name
        self.__application_name = "Not Set"

        # NatNet stream version serveris capable of. This will be updated during initialization only.
        self.__nat_net_stream_version_server = [0,0,0,0]

        # NatNet stream version. This will be updated to the actual version the server is using during runtime.
        self.__nat_net_requested_version = [0,0,0,0]

        # server stream version. This will be updated to the actual version the server is using during initialization.
        self.__server_version = [0,0,0,0]

        # Lock values once run is called
        self.__is_locked = False

        # Server has the ability to change bitstream version
        self.__can_change_bitstream_version = False

        self.command_thread = None
        self.data_thread = None
        self.command_socket = None
        self.data_socket = None

        self.stop_threads=False

        # Define the websocket connection url
        self.websocket_connection_url = ""

        # With this function it's possible to define from inside the threads that the program should stop (otherwise the shutdown process won't work)
        self.shutdown_threads = False

        self.isReady = False

    def need_shutdown(self):
        return self.shutdown_threads

    def set_shutdown(self):
        self.shutdown_threads = True

    # Set and get functions
    def get_message_id(self, data):
        message_id = int.from_bytes( data[0:2], byteorder='little' )
        return message_id

    def set_client_address(self, local_ip_address):
        if not self.__is_locked:
            self.local_ip_address = local_ip_address

    def get_client_address(self):
        return self.local_ip_address

    def set_server_address(self,server_ip_address):
        if not self.__is_locked:
            self.server_ip_address = server_ip_address

    def get_server_address(self):
        return self.server_ip_address

    def set_websocket_connection_url(self, address, is_DNS=False, port=8080):
        """ Set the websocket connection url (don't define the ws:// part because it's added automatically)"""
        if not self.__is_locked:
            if is_DNS:
                self.websocket_connection_url = "ws://" + address
            else:
                self.websocket_connection_url = "ws://" + address + ":" + str(port)

    def get_websocket_connection_url(self):
        return self.websocket_connection_url

    def set_use_multicast(self, use_multicast):
        if not self.__is_locked:
            self.use_multicast = use_multicast

    def can_change_bitstream_version(self):
        return self.__can_change_bitstream_version

    def set_nat_net_version(self, major, minor):
        """checks to see if stream version can change, then changes it with position reset"""
        return_code = -1
        if self.__can_change_bitstream_version and \
            (major != self.__nat_net_requested_version[0]) and\
            (minor != self.__nat_net_requested_version[1]):
            sz_command = "Bitstream,%1.1d.%1.1d"%(major, minor)
            return_code = self.send_command(sz_command)
            if return_code >=0:
                self.__nat_net_requested_version[0] = major
                self.__nat_net_requested_version[1] = minor
                self.__nat_net_requested_version[2] = 0
                self.__nat_net_requested_version[3] = 0
                print("changing bitstream MAIN")
                # get original output state
                #print_results = self.get_print_results()
                #turn off output
                #self.set_print_results(False)
                # force frame send and play reset
                self.send_command("TimelinePlay")
                time.sleep(0.1)
                tmpCommands=["TimelinePlay",
                    "TimelineStop",
                    "SetPlaybackCurrentFrame,0",
                    "TimelineStop"]
                self.send_commands(tmpCommands,False)
                time.sleep(2)
                #reset to original output state
                #self.set_print_results(print_results)
        return return_code


    def get_major(self):
        return self.__nat_net_requested_version[0]

    def get_minor(self):
        return self.__nat_net_requested_version[1]

    def connected(self):
        """ Return true if connected to server, false otherwise """
        is_connected = True

        # check sockets
        if self.command_socket == None:
            is_connected = False
        elif self.data_socket ==None:
            is_connected = False
        # check versions
        elif self.get_application_name() == "Not Set":
            is_connected = False
        elif (self.__server_version[0] == 0) and\
            (self.__server_version[1] == 0) and\
            (self.__server_version[2] == 0) and\
            (self.__server_version[3] == 0):
            is_connected = False

        # Return status
        return is_connected

    def check_connection(self):
        if VERIFY_CONNECTION == False:
            return
        try:
            socket.gethostbyname(DNS_CONNECTION_TESTING)
        except Exception as e:
            return False
        else:
            return True

    # Create a command socket to attach to the NatNet stream
    def __create_command_socket( self ):
        result = None
        if self.use_multicast :
            # Multicast case
            result = socket.socket( socket.AF_INET, socket.SOCK_DGRAM, 0 )
            # allow multiple clients on same machine to use multicast group address/port
            result.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                result.bind( ('', 0) )
            except socket.error as msg:
                print("ERROR: command socket error occurred:\n%s" %msg)
                print("Check Motive/Server mode requested mode agreement.  You requested Multicast ")
                result = None
            except  socket.herror:
                print("ERROR: command socket herror occurred")
                result = None
            except  socket.gaierror:
                print("ERROR: command socket gaierror occurred")
                result = None
            except  socket.timeout:
                print("ERROR: command socket timeout occurred. Server not responding")
                result = None
            # set to broadcast mode
            result.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            # set timeout to allow for keep alive messages
            result.settimeout(2.0)
        else:
            # Unicast case
            result = socket.socket( socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            try:
                result.bind( (self.local_ip_address, 0) )
            except socket.error as msg:
                print("ERROR: command socket error occurred:\n%s" %msg)
                print("Check Motive/Server mode requested mode agreement.  You requested Unicast ")
                result = None
            except socket.herror:
                print("ERROR: command socket herror occurred")
                result = None
            except socket.gaierror:
                print("ERROR: command socket gaierror occurred")
                result = None
            except socket.timeout:
                print("ERROR: command socket timeout occurred. Server not responding")
                result = None

            # set timeout to allow for keep alive messages
            result.settimeout(2.0)
            result.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        return result

    # Create a data socket to attach to the NatNet stream
    def __create_data_socket( self, port ):
        result = None

        if self.use_multicast:
            # Multicast case
            result = socket.socket( socket.AF_INET,     # Internet
                                  socket.SOCK_DGRAM,
                                  0)    # UDP
            result.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            result.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, socket.inet_aton(self.multicast_address) + socket.inet_aton(self.local_ip_address))
            try:
                result.bind( (self.local_ip_address, port) )
            except socket.error as msg:
                print("ERROR: data socket error occurred:\n%s" %msg)
                print("  Check Motive/Server mode requested mode agreement.  You requested Multicast ")
                result = None
            except socket.herror:
                print("ERROR: data socket herror occurred")
                result = None
            except socket.gaierror:
                print("ERROR: data socket gaierror occurred")
                result = None
            except socket.timeout:
                print("ERROR: data socket timeout occurred. Server not responding")
                result = None
        else:
            # Unicast case
            result = socket.socket( socket.AF_INET,     # Internet
                                  socket.SOCK_DGRAM,
                                  socket.IPPROTO_UDP)
            result.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            #result.bind( (self.local_ip_address, port) )
            try:
                result.bind( ('', 0) )
            except socket.error as msg:
                print("ERROR: data socket error occurred:\n%s" %msg)
                print("Check Motive/Server mode requested mode agreement.  You requested Unicast ")
                result = None
            except socket.herror:
                print("ERROR: data socket herror occurred")
                result = None
            except socket.gaierror:
                print("ERROR: data socket gaierror occurred")
                result = None
            except socket.timeout:
                print("ERROR: data socket timeout occurred. Server not responding")
                result = None
            
            if(self.multicast_address != "255.255.255.255"):
                result.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, socket.inet_aton(self.multicast_address) + socket.inet_aton(self.local_ip_address))

        return result

     # Unpack a rigid body object from a data packet
    def __unpack_rigid_body( self, data, major, minor, rb_num):
        offset = 0

        # ID (4 bytes)
        new_id = int.from_bytes( data[offset:offset+4], byteorder='little' )
        offset += 4

        trace_mf( "RB: %3.1d ID: %3.1d"% (rb_num, new_id))

        # Position and orientation
        pos = Vector3.unpack( data[offset:offset+12] )
        offset += 12
        trace_mf( "\tPosition    : [%3.2f, %3.2f, %3.2f]"% (pos[0], pos[1], pos[2] ))

        rot = Quaternion.unpack( data[offset:offset+16] )
        offset += 16
        trace_mf( "\tOrientation : [%3.2f, %3.2f, %3.2f, %3.2f]"% (rot[0], rot[1], rot[2], rot[3] ))

        rigid_body = MoCapData.RigidBody(new_id, pos, rot)

        # Send information to any listener.
        if self.rigid_body_listener is not None:
            self.rigid_body_listener( new_id, pos, rot )

        # RB Marker Data ( Before version 3.0.  After Version 3.0 Marker data is in description )
        if( major < 3  and major != 0) :
            # Marker count (4 bytes)
            marker_count = int.from_bytes( data[offset:offset+4], byteorder='little' )
            offset += 4
            marker_count_range = range( 0, marker_count )
            trace_mf( "\tMarker Count:", marker_count )

            rb_marker_list=[]
            for i in marker_count_range:
                rb_marker_list.append(MoCapData.RigidBodyMarker())

            # Marker positions
            for i in marker_count_range:
                pos = Vector3.unpack( data[offset:offset+12] )
                offset += 12
                trace_mf( "\tMarker", i, ":", pos[0],",", pos[1],",", pos[2] )
                rb_marker_list[i].pos=pos


            if major >= 2:
                # Marker ID's
                for i in marker_count_range:
                    new_id = int.from_bytes( data[offset:offset+4], byteorder='little' )
                    offset += 4
                    trace_mf( "\tMarker ID", i, ":", new_id )
                    rb_marker_list[i].id=new_id

                # Marker sizes
                for i in marker_count_range:
                    size = FloatValue.unpack( data[offset:offset+4] )
                    offset += 4
                    trace_mf( "\tMarker Size", i, ":", size[0] )
                    rb_marker_list[i].size=size

            for i in marker_count_range:
                rigid_body.add_rigid_body_marker(rb_marker_list[i])
        if major >= 2 :
            marker_error, = FloatValue.unpack( data[offset:offset+4] )
            offset += 4
            trace_mf( "\tMarker Error: %3.2f"% marker_error )
            rigid_body.error = marker_error

        # Version 2.6 and later
        if ( ( major == 2 ) and ( minor >= 6 ) ) or major > 2 :
            param, = struct.unpack( 'h', data[offset:offset+2] )
            tracking_valid = ( param & 0x01 ) != 0
            offset += 2
            is_valid_str='False'
            if tracking_valid:
                is_valid_str = 'True'
            trace_mf( "\tTracking Valid: %s"%is_valid_str)
            if tracking_valid:
                rigid_body.tracking_valid = True
            else:
                rigid_body.tracking_valid = False


        return offset, rigid_body

    # Unpack a skeleton object from a data packet
    def __unpack_skeleton( self, data, major, minor):

        offset = 0
        new_id = int.from_bytes( data[offset:offset+4], byteorder='little' )
        offset += 4
        trace_mf( "ID:", new_id )
        skeleton = MoCapData.Skeleton(new_id)

        rigid_body_count = int.from_bytes( data[offset:offset+4], byteorder='little' )
        offset += 4
        trace_mf( "Rigid Body Count : %3.1d"% rigid_body_count )
        for rb_num in range( 0, rigid_body_count ):
            offset_tmp, rigid_body = self.__unpack_rigid_body( data[offset:], major, minor, rb_num )
            skeleton.add_rigid_body(rigid_body)
            offset+=offset_tmp

        return offset, skeleton

#Unpack Mocap Data Functions
    def __unpack_frame_prefix_data( self, data):
        offset = 0
        # Frame number (4 bytes)
        frame_number = int.from_bytes( data[offset:offset+4], byteorder='little' )
        offset += 4
        trace_mf( "Frame #:", frame_number )
        frame_prefix_data=MoCapData.FramePrefixData(frame_number)
        return offset, frame_prefix_data

    def __unpack_marker_set_data( self, data, packet_size, major, minor):
        marker_set_data=MoCapData.MarkerSetData()
        offset = 0
        # Marker set count (4 bytes)
        marker_set_count = int.from_bytes( data[offset:offset+4], byteorder='little' )
        offset += 4
        trace_mf( "Marker Set Count:", marker_set_count )

        for i in range( 0, marker_set_count ):
            marker_data = MoCapData.MarkerData()
            # Model name
            model_name, separator, remainder = bytes(data[offset:]).partition( b'\0' )
            offset += len( model_name ) + 1
            trace_mf( "Model Name      : ", model_name.decode( 'utf-8' ) )
            marker_data.set_model_name(model_name)
            # Marker count (4 bytes)
            marker_count = int.from_bytes( data[offset:offset+4], byteorder='little' )
            offset += 4
            trace_mf( "Marker Count    : ", marker_count )

            for j in range( 0, marker_count ):
                pos = Vector3.unpack( data[offset:offset+12] )
                offset += 12
                trace_mf( "\tMarker %3.1d : [%3.2f,%3.2f,%3.2f]"%( j, pos[0], pos[1], pos[2] ))
                marker_data.add_pos(pos)
            marker_set_data.add_marker_data(marker_data)

        # Unlabeled markers count (4 bytes)
        unlabeled_markers_count = int.from_bytes( data[offset:offset+4], byteorder='little' )
        offset += 4
        trace_mf( "Unlabeled Markers Count:", unlabeled_markers_count )

        for i in range( 0, unlabeled_markers_count ):
            pos = Vector3.unpack( data[offset:offset+12] )
            offset += 12
            trace_mf( "\tMarker %3.1d : [%3.2f,%3.2f,%3.2f]"%( i, pos[0], pos[1], pos[2] ))
            marker_set_data.add_unlabeled_marker(pos)
        return offset, marker_set_data

    def __unpack_rigid_body_data( self, data, packet_size, major, minor):
        rigid_body_data = MoCapData.RigidBodyData()
        offset = 0
        # Rigid body count (4 bytes)
        rigid_body_count = int.from_bytes( data[offset:offset+4], byteorder='little' )
        offset += 4
        trace_mf( "Rigid Body Count:", rigid_body_count )

        for i in range( 0, rigid_body_count ):
            offset_tmp, rigid_body = self.__unpack_rigid_body( data[offset:], major, minor, i )
            offset += offset_tmp
            rigid_body_data.add_rigid_body(rigid_body)

        return offset, rigid_body_data


    def __unpack_skeleton_data( self, data, packet_size, major, minor):
        skeleton_data = MoCapData.SkeletonData()

        offset = 0
        # Version 2.1 and later
        skeleton_count = 0
        if( ( major == 2 and minor > 0 ) or major > 2 ):
            skeleton_count = int.from_bytes( data[offset:offset+4], byteorder='little' )
            offset += 4
            trace_mf( "Skeleton Count:", skeleton_count )
            for _ in range( 0, skeleton_count ):
                rel_offset, skeleton = self.__unpack_skeleton( data[offset:], major, minor )
                offset += rel_offset
                skeleton_data.add_skeleton(skeleton)

        return offset, skeleton_data

    def __decode_marker_id(self, new_id):
        model_id = 0
        marker_id = 0
        model_id = new_id >> 16
        marker_id = new_id & 0x0000ffff
        return model_id, marker_id

    def __unpack_labeled_marker_data( self, data, packet_size, major, minor):
        labeled_marker_data = MoCapData.LabeledMarkerData()
        offset = 0
        # Labeled markers (Version 2.3 and later)
        labeled_marker_count = 0
        if( ( major == 2 and minor > 3 ) or major > 2 ):
            labeled_marker_count = int.from_bytes( data[offset:offset+4], byteorder='little' )
            offset += 4
            trace_mf( "Labeled Marker Count:", labeled_marker_count )
            for _ in range( 0, labeled_marker_count ):
                model_id = 0
                marker_id = 0
                tmp_id = int.from_bytes( data[offset:offset+4], byteorder='little' )
                offset += 4
                model_id, marker_id = self.__decode_marker_id(tmp_id)
                pos = Vector3.unpack( data[offset:offset+12] )
                offset += 12
                size = FloatValue.unpack( data[offset:offset+4] )
                offset += 4
                trace_mf("ID     : [MarkerID: %3.1d] [ModelID: %3.1d]"%(marker_id,model_id))
                trace_mf("  pos  : [%3.2f, %3.2f, %3.2f]"%(pos[0],pos[1],pos[2]))
                trace_mf("  size : [%3.2f]"%size)


                # Version 2.6 and later
                param = 0
                if( ( major == 2 and minor >= 6 ) or major > 2):
                    param, = struct.unpack( 'h', data[offset:offset+2] )
                    offset += 2
                    #occluded = ( param & 0x01 ) != 0
                    #point_cloud_solved = ( param & 0x02 ) != 0
                    #model_solved = ( param & 0x04 ) != 0

                # Version 3.0 and later
                residual = 0.0
                if major >= 3 :
                    residual, = FloatValue.unpack( data[offset:offset+4] )
                    offset += 4
                    trace_mf( "  err  : [%3.2f]"% residual )

                labeled_marker = MoCapData.LabeledMarker(tmp_id,pos,size,param, residual)
                labeled_marker_data.add_labeled_marker(labeled_marker)

        return offset, labeled_marker_data

    def __unpack_force_plate_data( self, data, packet_size, major, minor):
        force_plate_data = MoCapData.ForcePlateData()
        n_frames_show_max = 4
        offset = 0
        # Force Plate data (version 2.9 and later)
        force_plate_count = 0
        if( ( major == 2 and minor >= 9 ) or major > 2 ):
            force_plate_count = int.from_bytes( data[offset:offset+4], byteorder='little' )
            offset += 4
            trace_mf( "Force Plate Count:", force_plate_count )
            for i in range( 0, force_plate_count ):
                # ID
                force_plate_id = int.from_bytes( data[offset:offset+4], byteorder='little' )
                offset += 4
                force_plate = MoCapData.ForcePlate(force_plate_id)

                # Channel Count
                force_plate_channel_count = int.from_bytes( data[offset:offset+4], byteorder='little' )
                offset += 4

                trace_mf( "\tForce Plate %3.1d ID: %3.1d Num Channels: %3.1d"% (i, force_plate_id, force_plate_channel_count ))

                # Channel Data
                for j in range( force_plate_channel_count ):
                    fp_channel_data = MoCapData.ForcePlateChannelData()
                    force_plate_channel_frame_count = int.from_bytes( data[offset:offset+4], byteorder='little' )
                    offset += 4
                    out_string="\tChannel %3.1d: "%( j )
                    out_string+="  %3.1d Frames - Frame Data: "%(force_plate_channel_frame_count)

                    # Force plate frames
                    n_frames_show = min(force_plate_channel_frame_count, n_frames_show_max)
                    for k in range( force_plate_channel_frame_count ):
                        force_plate_channel_val = FloatValue.unpack( data[offset:offset+4] )
                        offset += 4
                        fp_channel_data.add_frame_entry(force_plate_channel_val)

                        if k < n_frames_show:
                            out_string += "%3.2f "%(force_plate_channel_val)
                    if n_frames_show < force_plate_channel_frame_count:
                        out_string += " showing %3.1d of %3.1d frames"%(n_frames_show, force_plate_channel_frame_count)
                    trace_mf( "%s"% out_string )
                    force_plate.add_channel_data(fp_channel_data)
                force_plate_data.add_force_plate(force_plate)
        return offset, force_plate_data

    def __unpack_device_data( self, data, packet_size, major, minor):
        device_data = MoCapData.DeviceData()
        n_frames_show_max = 4
        offset = 0
        # Device data (version 2.11 and later)
        device_count = 0
        if ( major == 2 and minor >= 11 ) or (major > 2) :
            device_count = int.from_bytes( data[offset:offset+4], byteorder='little' )
            offset += 4
            trace_mf( "Device Count:", device_count )
            for i in range( 0, device_count ):

                # ID
                device_id = int.from_bytes( data[offset:offset+4], byteorder='little' )
                offset += 4
                device = MoCapData.Device(device_id)
                # Channel Count
                device_channel_count = int.from_bytes( data[offset:offset+4], byteorder='little' )
                offset += 4

                trace_mf( "\tDevice %3.1d      ID: %3.1d Num Channels: %3.1d"% (i, device_id, device_channel_count ))

                # Channel Data
                for j in range( 0, device_channel_count ):
                    device_channel_data = MoCapData.DeviceChannelData()
                    device_channel_frame_count = int.from_bytes( data[offset:offset+4], byteorder='little' )
                    offset += 4
                    out_string="\tChannel %3.1d "% (j)
                    out_string+="  %3.1d Frames - Frame Data: "%(device_channel_frame_count)

                    # Device Frame Data
                    n_frames_show = min(device_channel_frame_count, n_frames_show_max)
                    for k in range( 0, device_channel_frame_count ):
                        device_channel_val = int.from_bytes( data[offset:offset+4], byteorder='little' )
                        device_channel_val = FloatValue.unpack( data[offset:offset+4] )
                        offset += 4
                        if k < n_frames_show:
                            out_string += "%3.2f "%(device_channel_val)

                        device_channel_data.add_frame_entry(device_channel_val)
                    if n_frames_show < device_channel_frame_count:
                        out_string += " showing %3.1d of %3.1d frames"%(n_frames_show, device_channel_frame_count)
                    trace_mf( "%s"% out_string )
                    device.add_channel_data(device_channel_data)
                device_data.add_device(device)
        return offset, device_data

    def __unpack_frame_suffix_data( self, data, packet_size, major, minor):
        frame_suffix_data = MoCapData.FrameSuffixData()
        offset = 0

        # Timecode
        timecode = int.from_bytes( data[offset:offset+4], byteorder='little' )
        offset += 4
        frame_suffix_data.timecode = timecode

        timecode_sub = int.from_bytes( data[offset:offset+4], byteorder='little' )
        offset += 4
        frame_suffix_data.timecode_sub = timecode_sub

        # Timestamp (increased to double precision in 2.7 and later)
        if ( major == 2 and minor >= 7 ) or (major > 2 ):
            timestamp, = DoubleValue.unpack( data[offset:offset+8] )
            offset += 8
        else:
            timestamp, = FloatValue.unpack( data[offset:offset+4] )
            offset += 4
        trace_mf("Timestamp : %3.2f"%timestamp)
        frame_suffix_data.timestamp = timestamp

        # Hires Timestamp (Version 3.0 and later)
        if major >= 3 :
            stamp_camera_mid_exposure = int.from_bytes( data[offset:offset+8], byteorder='little' )
            trace_mf("Mid-exposure timestamp         : %3.1d"%stamp_camera_mid_exposure)
            offset += 8
            frame_suffix_data.stamp_camera_mid_exposure = stamp_camera_mid_exposure

            stamp_data_received = int.from_bytes( data[offset:offset+8], byteorder='little' )
            offset += 8
            frame_suffix_data.stamp_data_received = stamp_data_received
            trace_mf("Camera data received timestamp : %3.1d"%stamp_data_received)

            stamp_transmit = int.from_bytes( data[offset:offset+8], byteorder='little' )
            offset += 8
            trace_mf("Transmit timestamp             : %3.1d"%stamp_transmit)
            frame_suffix_data.stamp_transmit = stamp_transmit


        # Frame parameters
        param, = struct.unpack( 'h', data[offset:offset+2] )
        is_recording = ( param & 0x01 ) != 0
        tracked_models_changed = ( param & 0x02 ) != 0
        offset += 2
        frame_suffix_data.param = param
        frame_suffix_data.is_recording = is_recording
        frame_suffix_data.tracked_models_changed = tracked_models_changed

        return offset, frame_suffix_data

    # Unpack data from a motion capture frame message
    def __unpack_mocap_data( self, data : bytes, packet_size, major, minor):
        def makeDataReadyForWebsocket(data):
            # The division in marker data and rigid body data is done to make the data easier to manage and easier to modify in the future
            # It's indeed important to underline that some of the informations in the rigid body data are also present in the marker data

            # If the rigidbody filter is off return everything
            if RIGIDBODY_FILTER_ON == False:
                return data
            
            # Get marker data
            return_data = []
            markers = data.get_marker_set_data().get_labeled_data()
            for markerSet in markers:
                if markerSet.get_model_name_str() in [filter['name'] for filter in RIGIDBODY_FILTER]:
                    points = markerSet.get_pos_list()
                    counter_id = 0
                    for i in points:
                        counter_id  += 1
                        return_data.append({
                            'type': 'marker',
                            'ID': counter_id,
                            'rigidBody': markerSet.get_model_name_str(),
                            'x': i[0],
                            'y': i[1],
                            'z': i[2]
                        })
            
            # Get rigid body data
            rigid_bodies = data.get_rigid_body_data().get_rigid_body_list()
            for rigid_body in rigid_bodies:
                if rigid_body.get_id() in [filter['id'] for filter in RIGIDBODY_FILTER]:
                    return_data.append({
                            'type': 'rigidBody',
                            'ID': rigid_body.get_id(),
                            'x': rigid_body.get_pos()[0],
                            'y': rigid_body.get_pos()[1],
                            'z': rigid_body.get_pos()[2],
                            'qx': rigid_body.get_rot()[0],
                            'qy': rigid_body.get_rot()[1],
                            'qz': rigid_body.get_rot()[2],
                            'qw': rigid_body.get_rot()[3]
                    })
            return return_data

        mocap_data = MoCapData.MoCapData()
        data = memoryview( data )
        offset = 0
        rel_offset = 0

        #Frame Prefix Data
        rel_offset, frame_prefix_data = self.__unpack_frame_prefix_data(data[offset:])
        offset += rel_offset
        mocap_data.set_prefix_data(frame_prefix_data)
        frame_number = frame_prefix_data.frame_number

        #Marker Set Data
        rel_offset, marker_set_data =self.__unpack_marker_set_data(data[offset:], (packet_size - offset),major, minor)
        offset += rel_offset
        mocap_data.set_marker_set_data(marker_set_data)
        marker_set_count = marker_set_data.get_marker_set_count()
        unlabeled_markers_count = marker_set_data.get_unlabeled_marker_count()

        # Rigid Body Data
        rel_offset, rigid_body_data = self.__unpack_rigid_body_data(data[offset:], (packet_size - offset),major, minor)
        offset += rel_offset
        mocap_data.set_rigid_body_data(rigid_body_data)
        rigid_body_count = rigid_body_data.get_rigid_body_count()

        # Skeleton Data
        rel_offset, skeleton_data = self.__unpack_skeleton_data(data[offset:], (packet_size - offset),major, minor)
        offset += rel_offset
        mocap_data.set_skeleton_data(skeleton_data)
        skeleton_count = skeleton_data.get_skeleton_count()

        # Labeled Marker Data
        rel_offset, labeled_marker_data = self.__unpack_labeled_marker_data(data[offset:], (packet_size - offset),major, minor)
        offset += rel_offset
        mocap_data.set_labeled_marker_data(labeled_marker_data)
        labeled_marker_count = labeled_marker_data.get_labeled_marker_count()

        # Force Plate Data
        rel_offset, force_plate_data = self.__unpack_force_plate_data(data[offset:], (packet_size - offset),major, minor)
        offset += rel_offset
        mocap_data.set_force_plate_data(force_plate_data)

        # Device Data
        rel_offset,device_data = self.__unpack_device_data(data[offset:], (packet_size - offset),major, minor)
        offset += rel_offset
        mocap_data.set_device_data(device_data)

        # Frame Suffix Data
        #rel_offset, timecode, timecode_sub, timestamp, is_recording, tracked_models_changed = \
        rel_offset, frame_suffix_data =   self.__unpack_frame_suffix_data(data[offset:], (packet_size - offset),major, minor)
        offset += rel_offset
        mocap_data.set_suffix_data(frame_suffix_data)


        timecode = frame_suffix_data.timecode
        timecode_sub= frame_suffix_data.timecode_sub
        timestamp = frame_suffix_data.timestamp
        is_recording = frame_suffix_data.is_recording
        tracked_models_changed = frame_suffix_data.tracked_models_changed

        return {
            "frame_number": frame_number,
            "timestamp": timestamp,
            "mocap_data": makeDataReadyForWebsocket(mocap_data)
        }

    # Unpack a marker set description packet
    def __unpack_marker_set_description( self, data, major, minor):
        ms_desc = DataDescriptions.MarkerSetDescription()

        offset = 0

        name, separator, remainder = bytes(data[offset:]).partition( b'\0' )
        offset += len( name ) + 1
        trace_dd( "Marker Set Name: %s" % (name.decode( 'utf-8' )) )
        ms_desc.set_name(name)

        marker_count = int.from_bytes( data[offset:offset+4], byteorder='little' )
        offset += 4
        trace_dd( "Marker Count : %3.1d" % marker_count)
        for i in range( 0, marker_count ):
            name, separator, remainder = bytes(data[offset:]).partition( b'\0' )
            offset += len( name ) + 1
            trace_dd( "\t%2.1d Marker Name: %s"%(i, name.decode( 'utf-8' ) ))
            ms_desc.add_marker_name(name)

        return offset, ms_desc

    # Unpack a rigid body description packet
    def __unpack_rigid_body_description( self, data, major, minor):
        rb_desc=DataDescriptions.RigidBodyDescription()
        offset = 0

        # Version 2.0 or higher
        if (major >= 2) or (major == 0):
            name, separator, remainder = bytes(data[offset:]).partition( b'\0' )
            offset += len( name ) + 1
            rb_desc.set_name(name)
            trace_dd( "\tRigid Body Name   : ", name.decode( 'utf-8' ) )

        # ID
        new_id = int.from_bytes( data[offset:offset+4], byteorder='little' )
        offset += 4
        rb_desc.set_id(new_id)
        trace_dd( "\tID                : ", str(new_id))

        #Parent ID
        parent_id = int.from_bytes( data[offset:offset+4], byteorder='little' )
        offset += 4
        rb_desc.set_parent_id(parent_id)
        trace_dd( "\tParent ID         : ", parent_id)

        # Position Offsets
        pos = Vector3.unpack( data[offset:offset+12] )
        offset += 12
        rb_desc.set_pos(pos[0],pos[1],pos[2])

        trace_dd( "\tPosition          : [%3.2f, %3.2f, %3.2f]"% (pos[0], pos[1], pos[2] ))

        # Version 3.0 and higher, rigid body marker information contained in description
        if (major >= 3) or (major == 0) :
            # Marker Count
            marker_count = int.from_bytes( data[offset:offset+4], byteorder='little' )
            offset += 4
            trace_dd( "\tNumber of Markers : ", marker_count )

            marker_count_range = range( 0, marker_count )
            offset1 = offset
            offset2 = offset1 + (12*marker_count)
            offset3 = offset2 + (4*marker_count)
            # Marker Offsets X,Y,Z
            marker_name=""
            for marker in marker_count_range:
                # Offset
                marker_offset = Vector3.unpack(data[offset1:offset1+12])
                offset1 +=12

                # Active Label
                active_label = int.from_bytes(data[offset2:offset2+4],byteorder = 'little')
                offset2 += 4

                #Marker Name
                if (major >= 4) or (major == 0):
                    # markername
                    marker_name, separator, remainder = bytes(data[offset3:]).partition( b'\0' )
                    marker_name = marker_name.decode( 'utf-8' )
                    offset3 += len( marker_name ) + 1

                rb_marker=DataDescriptions.RBMarker(marker_name,active_label,marker_offset)
                rb_desc.add_rb_marker(rb_marker)
                trace_dd( "\t%3.1d Marker Label: %s Position: [%3.2f %3.2f %3.2f] %s" % (marker,active_label,\
                   marker_offset[0], marker_offset[1], marker_offset[2],marker_name ))

            offset = offset3
        
        trace_dd("\tunpack_rigid_body_description processed bytes: ", offset)
        return offset, rb_desc

    # Unpack a skeleton description packet
    def __unpack_skeleton_description( self, data, major, minor):
        skeleton_desc = DataDescriptions.SkeletonDescription()
        offset = 0

        #Name
        name, separator, remainder = bytes(data[offset:]).partition( b'\0' )
        offset += len( name ) + 1
        skeleton_desc.set_name(name)
        trace_dd( "Name : %s"% name.decode( 'utf-8' ) )

        #ID
        new_id = int.from_bytes( data[offset:offset+4], byteorder='little' )
        offset += 4
        skeleton_desc.set_id(new_id)
        trace_dd( "ID : %3.1d"% new_id )

        # # of RigidBodies
        rigid_body_count = int.from_bytes( data[offset:offset+4], byteorder='little' )
        offset += 4
        trace_dd( "Rigid Body (Bone) Count : %3.1d" % rigid_body_count)

        # Loop over all Rigid Bodies
        for i in range( 0, rigid_body_count ):
            trace_dd("Rigid Body (Bone) ", i)
            offset_tmp, rb_desc_tmp = self.__unpack_rigid_body_description( data[offset:], major, minor )
            offset+= offset_tmp
            skeleton_desc.add_rigid_body_description(rb_desc_tmp)
        return offset, skeleton_desc

    def __unpack_force_plate_description(self, data, major, minor):
        fp_desc = None
        offset = 0
        if major >= 3:
            fp_desc = DataDescriptions.ForcePlateDescription()
            # ID
            new_id = int.from_bytes( data[offset:offset+4], byteorder='little' )
            offset += 4
            fp_desc.set_id(new_id)
            trace_dd("\tID : ", str(new_id))

            # Serial Number
            serial_number, separator, remainder = bytes(data[offset:]).partition( b'\0' )
            offset += len( serial_number ) + 1
            fp_desc.set_serial_number(serial_number)
            trace_dd( "\tSerial Number : ", serial_number.decode( 'utf-8' ) )

            # Dimensions
            f_width = FloatValue.unpack( data[offset:offset+4])
            offset += 4
            trace_dd( "\tWidth  : %3.2f"% f_width)
            f_length = FloatValue.unpack( data[offset:offset+4])
            offset += 4
            fp_desc.set_dimensions(f_width[0], f_length[0])
            trace_dd( "\tLength : %3.2f"% f_length)

            # Origin
            origin = Vector3.unpack( data[offset:offset+12] )
            offset += 12
            fp_desc.set_origin(origin[0],origin[1],origin[2])
            trace_dd( "\tOrigin : %3.2f, %3.2f, %3.2f"%( origin[0], origin[1], origin[2] ))

            # Calibration Matrix 12x12 floats
            trace_dd("Cal Matrix:")
            cal_matrix_tmp= [[0.0 for col in range(12)] for row in range(12)]

            for i in range(0,12):
                cal_matrix_row=FPCalMatrixRow.unpack(data[offset:offset+(12*4)])
                trace_dd("\t%3.1d %3.3e %3.3e %3.3e %3.3e %3.3e %3.3e %3.3e %3.3e %3.3e %3.3e %3.3e %3.3e" % (i
                      , cal_matrix_row[0], cal_matrix_row[1], cal_matrix_row[2], cal_matrix_row[3]
                      , cal_matrix_row[4], cal_matrix_row[5], cal_matrix_row[6], cal_matrix_row[7]
                      , cal_matrix_row[8], cal_matrix_row[9], cal_matrix_row[10], cal_matrix_row[11]))
                cal_matrix_tmp[i] = copy.deepcopy(cal_matrix_row)
                offset += (12*4)
            fp_desc.set_cal_matrix(cal_matrix_tmp)
            # Corners 4x3 floats
            corners = FPCorners.unpack(data[offset:offset + (12*4)])
            offset += (12*4)
            o_2=0
            trace_dd("Corners:")
            corners_tmp = [[0.0 for col in range(3)] for row in range(4)]
            for i in range(0,4):
                trace_dd("\t%3.1d %3.3e %3.3e %3.3e"%(i, corners[o_2], corners[o_2+1], corners[o_2+2]))
                corners_tmp[i][0]=corners[o_2]
                corners_tmp[i][1]=corners[o_2+1]
                corners_tmp[i][2]=corners[o_2+2]
                o_2+=3
            fp_desc.set_corners(corners_tmp)

            # Plate Type int
            plate_type = int.from_bytes( data[offset:offset+4], byteorder='little' )
            offset+=4
            fp_desc.set_plate_type(plate_type)
            trace_dd ("Plate Type : ", plate_type)

            # Channel Data Type int
            channel_data_type = int.from_bytes( data[offset:offset+4], byteorder='little' )
            offset+=4
            fp_desc.set_channel_data_type(channel_data_type)
            trace_dd("Channel Data Type : ", channel_data_type)

            # Number of Channels int
            num_channels = int.from_bytes( data[offset:offset+4], byteorder='little' )
            offset+=4
            trace_dd("Number of Channels : ", num_channels)

            # Channel Names list of NoC strings
            for i in range(0, num_channels):
                channel_name, separator, remainder = bytes(data[offset:]).partition( b'\0' )
                offset += len( channel_name ) + 1
                trace_dd( "\tChannel Name %3.1d: %s"%(i, channel_name.decode( 'utf-8' ) ))
                fp_desc.add_channel_name(channel_name)

        trace_dd("unpackForcePlate processed ", offset, " bytes")
        return offset, fp_desc

    def __unpack_device_description(self, data, major, minor):
        device_desc=None
        offset = 0
        if major >= 3:
            # new_id
            new_id = int.from_bytes( data[offset:offset+4], byteorder='little' )
            offset += 4
            trace_dd("\tID : ", str(new_id))

            # Name
            name, separator, remainder = bytes(data[offset:]).partition( b'\0' )
            offset += len( name ) + 1
            trace_dd( "\tName : ", name.decode( 'utf-8' ) )

            # Serial Number
            serial_number, separator, remainder = bytes(data[offset:]).partition( b'\0' )
            offset += len( serial_number ) + 1
            trace_dd( "\tSerial Number : ", serial_number.decode( 'utf-8' ) )


            # Device Type int
            device_type = int.from_bytes( data[offset:offset+4], byteorder='little' )
            offset+=4
            trace_dd ("Device Type : ", device_type)

            # Channel Data Type int
            channel_data_type = int.from_bytes( data[offset:offset+4], byteorder='little' )
            offset+=4
            trace_dd("Channel Data Type : ", channel_data_type)

            device_desc = DataDescriptions.DeviceDescription(new_id,name,serial_number,device_type,channel_data_type)

            # Number of Channels int
            num_channels = int.from_bytes( data[offset:offset+4], byteorder='little' )
            offset+=4
            trace_dd("Number of Channels ", num_channels)

            # Channel Names list of NoC strings
            for i in range(0, num_channels):
                channel_name, separator, remainder = bytes(data[offset:]).partition( b'\0' )
                offset += len( channel_name ) + 1
                device_desc.add_channel_name(channel_name)
                trace_dd( "\tChannel ",i," Name : ", channel_name.decode( 'utf-8' ) )

        trace_dd("unpack_device_description processed ", offset, " bytes")
        return offset, device_desc

    def __unpack_camera_description(self, data, major, minor):
        offset = 0
        # Name
        name, separator, remainder = bytes(data[offset:]).partition( b'\0' )
        offset += len( name ) + 1
        trace_dd( "\tName       : %s"% name.decode( 'utf-8' ) )
        # Position
        position = Vector3.unpack( data[offset:offset+12] )
        offset += 12
        trace_dd( "\tPosition   : [%3.2f, %3.2f, %3.2f]"% (position[0], position[1], position[2] ))

        # Orientation
        orientation = Quaternion.unpack( data[offset:offset+16] )
        offset += 16
        trace_dd( "\tOrientation: [%3.2f, %3.2f, %3.2f, %3.2f]"% (orientation[0], orientation[1], orientation[2], orientation[3] ))
        trace_dd("unpack_camera_description processed %3.1d bytes"% offset)

        camera_desc=DataDescriptions.CameraDescription(name, position, orientation)
        return offset, camera_desc


    # Unpack a data description packet
    def __unpack_data_descriptions( self, data : bytes, packet_size, major, minor):
        data_descs = DataDescriptions.DataDescriptions()
        offset = 0
        # # of data sets to process
        dataset_count = int.from_bytes( data[offset:offset+4], byteorder='little' )
        offset += 4
        trace_dd("Dataset Count : ", str(dataset_count))
        for i in range( 0, dataset_count ):
            trace_dd("Dataset ", str(i))
            data_type = int.from_bytes( data[offset:offset+4], byteorder='little' )
            offset += 4
            data_tmp=None
            if data_type == 0 :
                trace_dd("Type: 0 Markerset")
                offset_tmp, data_tmp = self.__unpack_marker_set_description( data[offset:], major, minor )
            elif data_type == 1 :
                trace_dd("Type: 1 Rigid Body")
                offset_tmp, data_tmp = self.__unpack_rigid_body_description( data[offset:], major, minor )
            elif data_type == 2 :
                trace_dd("Type: 2 Skeleton")
                offset_tmp, data_tmp = self.__unpack_skeleton_description( data[offset:], major, minor )
            elif data_type == 3 :
                trace_dd("Type: 3 Force Plate")
                offset_tmp, data_tmp = self.__unpack_force_plate_description(data[offset:], major, minor)
            elif data_type == 4 :
                trace_dd("Type: 4 Device")
                offset_tmp, data_tmp = self.__unpack_device_description(data[offset:], major, minor)
            elif data_type == 5 :
                trace_dd("Type: 5 Camera")
                offset_tmp, data_tmp = self.__unpack_camera_description(data[offset:], major, minor)
            else:
                print("Type: " + str(data_type) + " UNKNOWN")
                print("ERROR: Type decode failure" )
                print("\t"+ str(i + 1) +" datasets processed of " + str(dataset_count))
                print("\t "+ str(offset) +" bytes processed of " + str(packet_size) )
                print("\tPACKET DECODE STOPPED")
                return offset
            offset += offset_tmp
            data_descs.add_data(data_tmp)
            trace_dd("\t"+ str(i) +" datasets processed of " + str(dataset_count))
            trace_dd("\t "+ str(offset) +" bytes processed of " + str(packet_size) )

        return offset, data_descs


    # __unpack_server_info is for local use of the client
    # and will update the values for the versions/ NatNet capabilities
    # of the server.
    def __unpack_server_info(self, data, packet_size, major, minor):
        offset = 0
        # Server name
        #szName = data[offset: offset+256]
        self.__application_name, separator, remainder = bytes(data[offset: offset+256]).partition( b'\0' )
        self.__application_name=str(self.__application_name, "utf-8")
        offset += 256
        # Server Version info
        server_version = struct.unpack( 'BBBB', data[offset:offset+4] )
        offset += 4
        self.__server_version[0] = server_version[0]
        self.__server_version[1] = server_version[1]
        self.__server_version[2] = server_version[2]
        self.__server_version[3] = server_version[3]

        # NatNet Version info
        nnsvs = struct.unpack( 'BBBB', data[offset:offset+4] )
        offset += 4
        self.__nat_net_stream_version_server[0]=nnsvs[0]
        self.__nat_net_stream_version_server[1]=nnsvs[1]
        self.__nat_net_stream_version_server[2]=nnsvs[2]
        self.__nat_net_stream_version_server[3]=nnsvs[3]
        if (self.__nat_net_requested_version[0] == 0) and\
           (self.__nat_net_requested_version[1] == 0):
            self.__nat_net_requested_version[0] = self.__nat_net_stream_version_server[0]
            self.__nat_net_requested_version[1] = self.__nat_net_stream_version_server[1]
            self.__nat_net_requested_version[2] = self.__nat_net_stream_version_server[2]
            self.__nat_net_requested_version[3] = self.__nat_net_stream_version_server[3]
            # Determine if the bitstream version can be changed
            if (self.__nat_net_stream_version_server[0] >= 4) and (self.use_multicast == False):
                self.__can_change_bitstream_version = True

        trace_mf("Sending Application Name: ", self.__application_name)
        trace_mf("NatNetVersion " , str(self.__nat_net_stream_version_server[0]), " "
            , str(self.__nat_net_stream_version_server[1]), " "
            , str(self.__nat_net_stream_version_server[2]), " "
                , str(self.__nat_net_stream_version_server[3]))

        trace_mf("ServerVersion " , str(self.__server_version[0]), " "
            , str(self.__server_version[1]), " "
            , str(self.__server_version[2]), " "
                , str(self.__server_version[3]) )
        return offset


    def __command_thread_function( self, in_socket, stop):
        if not self.use_multicast:
            in_socket.settimeout(2.0)
        data=bytearray(0)
        # 64k buffer size
        recv_buffer_size=64*1024
        while not stop():
            # Block for input
            try:
                data, addr = in_socket.recvfrom( recv_buffer_size )
            except socket.error as msg:
                pass
            except  socket.herror:
                print("ERROR: command socket access herror occurred")
                return 2
            except  socket.gaierror:
                print("ERROR: command socket access gaierror occurred")
                return 3
            except  socket.timeout:
                if(self.use_multicast):
                    print("ERROR: command socket access timeout occurred. Server not responding")
                    #return 4

            if len( data ) > 0 : 
                self.__process_message( data )
                data=bytearray(0)

            if not self.use_multicast:
                if not stop():
                    self.send_keep_alive(in_socket, self.server_ip_address, self.command_port)
        return 0

    def __data_thread_function_wrap( self, in_socket, stop):
        # Execute the data thread function
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.__data_thread_function(in_socket, stop))

        # Wait for all tasks to be completed
        pending = asyncio.all_tasks(loop=loop)
        loop.run_until_complete(asyncio.gather(*pending))
        loop.close()

        # Shut down everything
        self.set_shutdown()

    async def __data_thread_function(self, in_socket, stop):
        try:
            # Define the data buffer
            data=bytearray(0)
            recv_buffer_size=64*1024 # 64k buffer size
            websocket_attempts = 0
            connection_attempts = 0

            while not stop():
                try:
                    # Verify that the system is ready
                    if self.isReady == False:
                        await asyncio.sleep(0.5) # Wait for 500 ms
                        continue

                    # Verify that the computer is connected to internet
                    if self.check_connection() == False:
                        raise NetworkConnectionError("Connection to the server lost")
                    connection_attempts = 0

                    # Start websocket connection
                    async with websockets.connect(self.websocket_connection_url) as websocket:
                        websocket_attempts = 0
                        while not stop():
                            # Wait for the input from the websocket
                            try:
                                data, addr = in_socket.recvfrom( recv_buffer_size )
                            except socket.error as msg:
                                if not stop():
                                    self.logger.error("ERROR: data socket access error occurred:\n  %s" %msg)
                                    return 1
                            except  socket.herror:
                                print("ERROR: data socket access herror occurred")
                                #return 2
                            except  socket.gaierror:
                                print("ERROR: data socket access gaierror occurred")
                                #return 3
                            except  socket.timeout:
                                #if self.use_multicast:
                                print("ERROR: data socket access timeout occurred. Server not responding")
                                #return 4

                            # If the data is not null send it to the websocket                
                            if len( data ) > 0 :
                                processed_data = self.__process_message( data )
                                await websocket.send(json.dumps({'type': 'optitrack-data', 'data': json.dumps(processed_data)}))
                                await asyncio.sleep(0)
                                data = bytearray(0)
                except websockets.ConnectionClosedOK:
                    continue
                except websockets.ConnectionClosedError:
                    continue
                except websockets.InvalidStatusCode as e: # This is to handle when the server is not turned on
                    websocket_attempts += 1
                    if websocket_attempts > MAX_ATTEMPTS_TO_CONNECT:
                        self.logger.error("Websocket connection failed. Verify that the websocket server is on.")
                        return 1
                    time_to_sleep = 2**websocket_attempts + random.randint(0, 1000) / 1000 # Exponential backoff
                    await asyncio.sleep(time_to_sleep)
                    continue
                except NetworkConnectionError as e: # This is to handle when the connection is lost
                    connection_attempts += 1
                    if connection_attempts > MAX_ATTEMPTS_TO_CONNECT:
                        self.logger.error("Your connection has been lost for too long.")
                        return 1
                    time_to_sleep = 2**connection_attempts + random.randint(0, 1000) / 1000 # Exponential backoff
                    await asyncio.sleep(time_to_sleep)
                    continue
            return 0
        except KeyboardInterrupt:
            return 0
        except Exception as e:
            self.logger.error("Error: " + str(e))
            return 1

    def __process_message( self, data : bytes):
        # Get usefull informations
        major = self.get_major()
        minor = self.get_minor()
        message_id = self.get_message_id(data)

        # Get the packet size
        packet_size = int.from_bytes( data[2:4], byteorder='little' )

        # Skip the 4 bytes for message ID and packet_size
        offset = 4
        if message_id == self.NAT_FRAMEOFDATA :
            return self.__unpack_mocap_data( data[offset:], packet_size, major, minor )
        elif message_id == self.NAT_MODELDEF :
            self.__unpack_data_descriptions( data[offset:], packet_size, major, minor)
        elif message_id == self.NAT_SERVERINFO :
            self.__unpack_server_info( data[offset:], packet_size, major, minor)
        
        # By default return an empty dictionary
        return {}

    def send_request( self, in_socket, command, command_str, address ):
        # Compose the message in our known message format
        packet_size = 0
        if command == self.NAT_REQUEST_MODELDEF or command == self.NAT_REQUEST_FRAMEOFDATA :
            packet_size = 0
            command_str = ""
        elif command == self.NAT_REQUEST :
            packet_size = len( command_str ) + 1
        elif command == self.NAT_CONNECT :
            command_str = "Ping"
            packet_size = len( command_str ) + 1
        elif command == self.NAT_KEEPALIVE:
            packet_size = 0
            command_str = ""

        data = command.to_bytes( 2, byteorder='little' )
        data += packet_size.to_bytes( 2, byteorder='little' )

        data += command_str.encode( 'utf-8' )
        data += b'\0'

        return in_socket.sendto( data, address )

    def send_command( self, command_str):
        nTries = 3
        ret_val = -1
        while nTries:
            nTries -= 1
            ret_val = self.send_request( self.command_socket, self.NAT_REQUEST, command_str,  (self.server_ip_address, self.command_port) )
            if (ret_val != -1):
                break
        return ret_val

    def send_commands(self,tmpCommands, print_results: bool =True):
        for sz_command in tmpCommands:
            return_code = self.send_command(sz_command)
            if(print_results):
                self.logger.info("Command: %s - return_code: %d"% (sz_command, return_code) )

    def send_keep_alive(self,in_socket, server_ip_address, server_port):
        return self.send_request(in_socket, self.NAT_KEEPALIVE, "", (server_ip_address, server_port))

    def get_command_port(self):
        return self.command_port

    def get_application_name(self):
        return self.__application_name

    def get_nat_net_requested_version(self):
        return self.__nat_net_requested_version

    def get_nat_net_version_server(self):
        return self.__nat_net_stream_version_server

    def get_server_version(self):
        return self.__server_version

    # Run the streaming client
    def __start( self ):
        # Create the data socket
        self.data_socket = self.__create_data_socket( self.data_port )
        if self.data_socket is None :
            self.logger.error( "Could not open data channel" )
            return False

        # Create the command socket
        self.command_socket = self.__create_command_socket()
        if self.command_socket is None :
            self.logger.error( "Could not open command channel" )
            return False
        
        self.__is_locked = True # Set the variable to avoid changing the parameters in the middle of execution

        self.stop_threads = False # Shared variable to stop the threads

        # Create a separate thread for receiving data packets
        self.data_thread = Thread( target = self.__data_thread_function_wrap, args = (self.data_socket, lambda : self.stop_threads, ))
        self.data_thread.start()

        # Create a separate thread for receiving command packets
        self.command_thread = Thread( target = self.__command_thread_function, args = (self.command_socket, lambda : self.stop_threads, ))
        self.command_thread.start()

        # Required for setup: Get NatNet and server versions
        self.send_request(self.command_socket, self.NAT_CONNECT, "",  (self.server_ip_address, self.command_port) )

        return True

    def start(self):
        try:
            # Start up the streaming client
            is_running = self.__start()
            if not is_running:
                self.logger.error("Could not start streaming client.")
                self.shutdown()
                sys.exit(1)
            else:
                self.logger.debug("Streaming client running")
            time.sleep(PROGRAM_SLEEP_TIME)

            # Check if the streaming client is connected to the server
            if self.connected() is False:
                self.logger.error("Streaming client failed to connect to server at address: " + OPTITRACK_ADDRESS)
                self.shutdown()
                sys.exit(1)
            else:
                self.logger.debug("Streaming client connected")
            time.sleep(PROGRAM_SLEEP_TIME)
        except KeyboardInterrupt:
            self.logger.debug("Optitrack Bridge service stopped by user.")
            self.shutdown()
            sys.exit(0)
        except Exception as e:
            self.logger.error("An exception occurred while initializing the streaming client. \n" + traceback.format_exc())
            self.shutdown()
            sys.exit(1)
        else:
            self.logger.debug("Streaming client initialized successfully")

    def run(self):
        try:
            print("Press Ctrl+C to stop the service.")
            self.isReady = True
            while not self.need_shutdown():
                time.sleep(PROGRAM_LOOP_SLEEP_TIME)
        except KeyboardInterrupt:
            self.shutdown()
            sys.exit(0)
        except Exception as e:
            self.logger.error("ERROR: An exception occurred while running the streaming client loop.")
            self.shutdown()
            sys.exit(1)
        else:
            self.shutdown()
            sys.exit(0)

    # Shut down the streaming client
    def shutdown(self):
        # Stop the ability for the user to press CTRL + C to stop the program (otherwise the program will stay alive indefinitely)
        signal.signal(signal.SIGINT, signal.SIG_IGN)

        # Log that the system is shutting down
        self.logger.debug("Shutting down. This might take a while.")

        # Update the shared variable to stop the threads
        self.stop_threads = True
        
        # Closing sockets causes blocking recvfrom to throw an exception and break the loop
        self.command_socket.close()
        self.data_socket.close()

        # Join the threads to make sure that they are closed at the end of the program
        self.command_thread.join()
        self.data_thread.join()

        # Log that the shutdown is complete
        self.logger.info("Shutdown complete.")
        