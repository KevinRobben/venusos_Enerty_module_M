
import threading
import socket
import time
import sys
import struct
import select


_dbusservice = {
    '/Ac/Power': 0,
    '/Ac/Energy/Forward': 0,
    '/Ac/Energy/Reverse': 0,
    '/Ac/L1/Energy/Forward': 0,
    '/Ac/L1/Energy/Reverse': 0,
    '/Ac/L1/Power': 0,
    '/Ac/L1/Voltage': 0,
    '/Ac/L1/Current': 0,
    '/Ac/L2/Energy/Forward': 0,
    '/Ac/L2/Energy/Reverse': 0,
    '/Ac/L2/Power': 0,
    '/Ac/L2/Voltage': 0,
    '/Ac/L2/Current': 0,
    '/Ac/L3/Energy/Forward': 0,
    '/Ac/L3/Energy/Reverse': 0,
    '/Ac/L3/Power': 0,
    '/Ac/L3/Voltage': 0,
    '/Ac/L3/Current': 0,
    '/Ac/Current': 0,
    '/Serial': 0
}

def sma_receiver_thread() :
    
    # ipbind = '0.0.0.0'
    MCAST_GRP = '239.12.255.254'
    MCAST_PORT = 9522
            
    try:
        # Create the UDP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # # Increase the receive buffer size
        # sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 2**20)
        

        # Join the multicast group
        mreq = struct.pack("4sL", socket.inet_aton(MCAST_GRP), socket.INADDR_ANY)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        print(f"Joined multicast group {MCAST_GRP}")

        

        # Bind the socket to the multicast port
        sock.bind(('', MCAST_PORT))
        print(f"Socket bound to :{MCAST_PORT}")

    except Exception as e:
        print(f'Could not connect to multicast group or bind to given interface: {e}')
        sys.exit(1)

    while True:
        ready = select.select([sock], [], [], 1) # timeout 200ms

        if not ready[0]:
            print('timeout')
            _dbusservice['/Ac/L1/Power'] = 0 # set power to zero if timeout
            _dbusservice['/Ac/L2/Power'] = 0 # set power to zero if timeout
            _dbusservice['/Ac/L3/Power'] = 0 # set power to zero if timeout
            _dbusservice['/Ac/Power'] = 0 # set power to zero if timeout
            continue
 
        b = sock.recv(608)
        print(f"Received data: {b}")

            
        try:
            if len(b) < 500: # too short
                print('too short')
                continue
                
            if int.from_bytes(b[16:18], byteorder='big') != 0x6069 : # wrong protocol?
                print('wrong protocol')
                continue
                
            serial = int.from_bytes(b[20:24], byteorder='big')
            if serial == 0xffffffff : # wrong serial?
                print('wrong serial')
                continue

            print('serial number:', serial)
                
            _dbusservice['/Ac/Power'] = (int.from_bytes(b[32:36], byteorder='big') - int.from_bytes(b[52:56], byteorder='big')) / 10
            _dbusservice['/Ac/Energy/Forward'] = int.from_bytes(b[40:48], byteorder='big') / 3600 / 1000
            _dbusservice['/Ac/Energy/Reverse'] = int.from_bytes(b[60:68], byteorder='big') / 3600 / 1000
            
            offset = 156 # 164 for energy meter, 156 for home manager 2
            _dbusservice['/Ac/L1/Energy/Forward'] = int.from_bytes(b[offset + 12:offset + 20], byteorder='big') / 3600 / 1000
            _dbusservice['/Ac/L1/Energy/Reverse'] = int.from_bytes(b[offset + 32:offset + 40], byteorder='big') / 3600 / 1000
            _dbusservice['/Ac/L1/Power'] = (int.from_bytes(b[offset + 4:offset + 8], byteorder='big') - int.from_bytes(b[offset + 24:offset + 28], byteorder='big')) / 10
            _dbusservice['/Ac/L1/Voltage'] = int.from_bytes(b[offset + 132:offset + 136], byteorder='big') / 1000
            _dbusservice['/Ac/L1/Current'] = _dbusservice['/Ac/L1/Power'] / _dbusservice['/Ac/L1/Voltage']

            offset = 300 # 308 for energy meter, 300 for home manager 2
            _dbusservice['/Ac/L2/Energy/Forward'] = int.from_bytes(b[offset + 12:offset + 20], byteorder='big') / 3600 / 1000
            _dbusservice['/Ac/L2/Energy/Reverse'] = int.from_bytes(b[offset + 32:offset + 40], byteorder='big') / 3600 / 1000
            _dbusservice['/Ac/L2/Power'] = (int.from_bytes(b[offset + 4:offset + 8], byteorder='big') - int.from_bytes(b[offset + 24:offset + 28], byteorder='big')) / 10
            _dbusservice['/Ac/L2/Voltage'] = int.from_bytes(b[offset + 132:offset + 136], byteorder='big') / 1000
            _dbusservice['/Ac/L2/Current'] = _dbusservice['/Ac/L2/Power'] / _dbusservice['/Ac/L2/Voltage']
            
            offset = 444 # 452 for energy meter, 444 for home manager 2
            _dbusservice['/Ac/L3/Energy/Forward'] = int.from_bytes(b[offset + 12:offset + 20], byteorder='big') / 3600 / 1000
            _dbusservice['/Ac/L3/Energy/Reverse'] = int.from_bytes(b[offset + 32:offset + 40], byteorder='big') / 3600 / 1000
            _dbusservice['/Ac/L3/Power'] = (int.from_bytes(b[offset + 4:offset + 8], byteorder='big') - int.from_bytes(b[offset + 24:offset + 28], byteorder='big')) / 10
            _dbusservice['/Ac/L3/Voltage'] = int.from_bytes(b[offset + 132:offset + 136], byteorder='big') / 1000
            _dbusservice['/Ac/L3/Current'] = _dbusservice['/Ac/L3/Power'] / _dbusservice['/Ac/L3/Voltage']
            
            _dbusservice['/Ac/Current'] = _dbusservice['/Ac/L1/Current'] + _dbusservice['/Ac/L2/Current'] + _dbusservice['/Ac/L3/Current']
            
            _dbusservice['/Serial'] = int.from_bytes(b[20:24], byteorder='big')

            print(_dbusservice)
        except:
            print('error parsing energy meter values')   

receive_thread = threading.Thread(target=sma_receiver_thread)
receive_thread.daemon = True
receive_thread.start() 

while True:
    # print(_dbusservice)
    time.sleep(1)
