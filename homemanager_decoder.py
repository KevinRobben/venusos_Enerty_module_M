import select
import struct
import logging
import socket
import sys
import time

MCAST_GRP = '239.12.255.254'
MCAST_PORT = 9522


class HomeManager20:
    OBIS_OBJECTS = {
        0x00010400: {'measurement': 'positive_active_demand', 'format': '>I', 'scale': 10},
        0x00010800: {'measurement': 'positive_active_energy', 'format': '>Q', 'scale': 3600000},
        0x00020400: {'measurement': 'negative_active_demand', 'format': '>I', 'scale': 10},
        0x00020800: {'measurement': 'negative_active_energy', 'format': '>Q', 'scale': 3600000},
        0x00030400: {'measurement': 'positive_reactive_demand', 'format': '>I', 'scale': 10},
        0x00030800: {'measurement': 'positive_reactive_energy', 'format': '>Q', 'scale': 3600000},
        0x00040400: {'measurement': 'negative_reactive_demand', 'format': '>I', 'scale': 10},
        0x00040800: {'measurement': 'negative_reactive_energy', 'format': '>Q', 'scale': 3600000},
        0x00090400: {'measurement': 'positive_apparent_demand', 'format': '>I', 'scale': 10},
        0x00090800: {'measurement': 'positive_apparent_energy', 'format': '>Q', 'scale': 3600000},
        0x000a0400: {'measurement': 'negative_apparent_demand', 'format': '>I', 'scale': 10},
        0x000a0800: {'measurement': 'negative_apparent_energy', 'format': '>Q', 'scale': 3600000},
        0x000d0400: {'measurement': 'power_factor', 'format': '>I', 'scale': 1000},
        0x000e0400: {'measurement': 'frequency', 'format': '>I', 'scale': 1000},
        0x00150400: {'measurement': 'positive_active_demand_L1', 'format': '>I', 'scale': 10},
        0x00150800: {'measurement': 'positive_active_energy_L1', 'format': '>Q', 'scale': 3600000},
        0x00160400: {'measurement': 'negative_active_demand_L1', 'format': '>I', 'scale': 10},
        0x00160800: {'measurement': 'negative_active_energy_L1', 'format': '>Q', 'scale': 3600000},
        0x00170400: {'measurement': 'positive_reactive_demand_L1', 'format': '>I', 'scale': 10},
        0x00170800: {'measurement': 'positive_reactive_energy_L1', 'format': '>Q', 'scale': 3600000},
        0x00180400: {'measurement': 'negative_reactive_demand_L1', 'format': '>I', 'scale': 10},
        0x00180800: {'measurement': 'negative_reactive_energy_L1', 'format': '>Q', 'scale': 3600000},
        0x001d0400: {'measurement': 'positive_apparent_demand_L1', 'format': '>I', 'scale': 10},
        0x001d0800: {'measurement': 'positive_apparent_energy_L1', 'format': '>Q', 'scale': 3600000},
        0x001e0400: {'measurement': 'negative_apparent_demand_L1', 'format': '>I', 'scale': 10},
        0x001e0800: {'measurement': 'negative_apparent_energy_L1', 'format': '>Q', 'scale': 3600000},
        0x001f0400: {'measurement': 'current_L1', 'format': '>I', 'scale': 1000},
        0x00200400: {'measurement': 'voltage_L1', 'format': '>I', 'scale': 1000},
        0x00210400: {'measurement': 'power_factor_L1', 'format': '>I', 'scale': 1000},
        0x00290400: {'measurement': 'positive_active_demand_L2', 'format': '>I', 'scale': 10},
        0x00290800: {'measurement': 'positive_active_energy_L2', 'format': '>Q', 'scale': 3600000},
        0x002a0400: {'measurement': 'negative_active_demand_L2', 'format': '>I', 'scale': 10},
        0x002a0800: {'measurement': 'negative_active_energy_L2', 'format': '>Q', 'scale': 3600000},
        0x002b0400: {'measurement': 'positive_reactive_demand_L2', 'format': '>I', 'scale': 10},
        0x002b0800: {'measurement': 'positive_reactive_energy_L2', 'format': '>Q', 'scale': 3600000},
        0x002c0400: {'measurement': 'negative_reactive_demand_L2', 'format': '>I', 'scale': 10},
        0x002c0800: {'measurement': 'negative_reactive_energy_L2', 'format': '>Q', 'scale': 3600000},
        0x00310400: {'measurement': 'positive_apparent_demand_L2', 'format': '>I', 'scale': 10},
        0x00310800: {'measurement': 'positive_apparent_energy_L2', 'format': '>Q', 'scale': 3600000},
        0x00320400: {'measurement': 'negative_apparent_demand_L2', 'format': '>I', 'scale': 10},
        0x00320800: {'measurement': 'negative_apparent_energy_L2', 'format': '>Q', 'scale': 3600000},
        0x00330400: {'measurement': 'current_L2', 'format': '>I', 'scale': 1000},
        0x00340400: {'measurement': 'voltage_L2', 'format': '>I', 'scale': 1000},
        0x00350400: {'measurement': 'power_factor_L2', 'format': '>I', 'scale': 1000},
        0x003d0400: {'measurement': 'positive_active_demand_L3', 'format': '>I', 'scale': 10},
        0x003d0800: {'measurement': 'positive_active_energy_L3', 'format': '>Q', 'scale': 3600000},
        0x003e0400: {'measurement': 'negative_active_demand_L3', 'format': '>I', 'scale': 10},
        0x003e0800: {'measurement': 'negative_active_energy_L3', 'format': '>Q', 'scale': 3600000},
        0x003f0400: {'measurement': 'positive_reactive_demand_L3', 'format': '>I', 'scale': 10},
        0x003f0800: {'measurement': 'positive_reactive_energy_L3', 'format': '>Q', 'scale': 3600000},
        0x00400400: {'measurement': 'negative_reactive_demand_L3', 'format': '>I', 'scale': 10},
        0x00400800: {'measurement': 'negative_reactive_energy_L3', 'format': '>Q', 'scale': 3600000},
        0x00450400: {'measurement': 'positive_apparent_demand_L3', 'format': '>I', 'scale': 10},
        0x00450800: {'measurement': 'positive_apparent_energy_L3', 'format': '>Q', 'scale': 3600000},
        0x00460400: {'measurement': 'negative_apparent_demand_L3', 'format': '>I', 'scale': 10},
        0x00460800: {'measurement': 'negative_apparent_energy_L3', 'format': '>Q', 'scale': 3600000},
        0x00470400: {'measurement': 'current_L3', 'format': '>I', 'scale': 1000},
        0x00480400: {'measurement': 'voltage_L3', 'format': '>I', 'scale': 1000},
        0x00490400: {'measurement': 'power_factor_L3', 'format': '>I', 'scale': 1000},
        0x000402a0: {'measurement': 'current_transformer_ratio', 'format': '>I', 'scale': 1},
        0x024c0010: {'measurement': 'serial', 'format': '>xxxxIxxxx', 'scale': 1},
        0x90000000: {'measurement': 'fw_version', 'format': '>BBBc', 'scale': 1},
    }

    def __init__(self):
        self.datagram = None
        self.hmdata = {}
        self.last_update = time.time()
            
        try:
            # Create the UDP socket
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            # # Increase the receive buffer size
            # sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 2**20)
            

            # Join the multicast group
            mreq = struct.pack("4sL", socket.inet_aton(MCAST_GRP), socket.INADDR_ANY)
            self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
            print(f"Joined multicast group {MCAST_GRP}")

            

            # Bind the socket to the multicast port
            self.sock.bind(('', MCAST_PORT))
            print(f"Socket bound to :{MCAST_PORT}")

        except Exception as e:
            print(f'Could not connect to multicast group or bind to given interface: {e}')
            sys.exit(1)




    def _read_data(self, timeout:int):
        ready = select.select([self.sock], [], [], timeout)

        if not ready[0]:
            return False

        self.datagram = self.sock.recv(608)
        if len(self.datagram) < 500: # too short
            return False
        
        return True


    def _decode_data(self):    
            
        if self.datagram[:4] != b'SMA\x00':
            print('wrong header')
            return

        if int.from_bytes(self.datagram[16:18], byteorder='big') != 0x6069 : # wrong protocol?
            print('wrong protocol')
            return
    
        serial = int.from_bytes(self.datagram[20:24], byteorder='big')
        if serial == 0xffffffff : # wrong serial?
            print('wrong serial')
            return
        


        self.last_update = time.time()
        self.hmdata = {}
        i = 4
        while i < len(self.datagram):
            obis = struct.unpack('>I', self.datagram[i:i + 4])[0]
            i += 4
            if obis > 0:
                try:
                    key = self.OBIS_OBJECTS[obis]['measurement']
                    size = struct.calcsize(self.OBIS_OBJECTS[obis]['format'])
                    values = struct.unpack(self.OBIS_OBJECTS[obis]['format'], self.datagram[i:i + size])
                    if key != 'fw_version':
                        value = values[0] / self.OBIS_OBJECTS[obis]['scale']
                    else:
                        value = f'{values[0]}.{values[1]}.{values[2]}.{values[3].decode()}'
                    self.hmdata.update({key: value})
                    print(f'update = {key}: {value}')
                    i += size
                except KeyError:
                    logging.debug(f'Unknown OBIS ID: 0x{obis:08x}')
                    print(f'Unknown OBIS ID: 0x{obis:08x} - {obis}')
                    i += 4
                    return



if __name__ == "__main__":
    sma = HomeManager20()

    while True:
        if sma._read_data(timeout=1):
            sma._decode_data()
            print(sma.hmdata)
        else:
            if sma.last_update + 5 < time.time():
                print('not updated for 5 seconds')
                sma.hmdata = {}
    