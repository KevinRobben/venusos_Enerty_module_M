import select
import struct
import logging
import socket
import sys
import time
import serial
import serial.tools.list_ports

VID = 0x239A
PID = 0x80A4
port_name = None
WINDOWS = False

"""struct VictronSerialAmpsAndVoltage {
        uint8_t magic_start; // * 
        uint8_t command;     // C
        bool export_CT1;
        bool export_CT2;
        bool export_CT3;
        uint32_t I1; // mA
        uint32_t I2;
        uint32_t I3;
        uint32_t U1; // mV
        uint32_t U2;
        uint32_t U3;
        uint32_t P1; // W
        uint32_t P2;
        uint32_t P3;
    };"""

class VictronSerialAmpsAndVoltage:
    def __init__(self) -> None:
        self.command: int = 0
        self.export_CT1: bool = False
        self.export_CT2: bool = False
        self.export_CT3: bool = False
        self.I1: int = 0 # mA
        self.I2: int = 0
        self.I3: int = 0
        self.U1: int = 0 # mV
        self.U2: int = 0
        self.U3: int = 0
        self.P1: int = 0 # Watt
        self.P2: int = 0
        self.P3: int = 0 


class ModuleM:

    def __init__(self):
        self.ser: serial.Serial = None
        self.datagram = None
        self.mmdata = VictronSerialAmpsAndVoltage()
        self.mmregistered = False # module m registered with *B command
        self.last_update = time.time()
            
        self._connect_serial()



    def _read_data(self, timeout:int):
        if not self.ser:
            if not self._connect_serial():
                return False

        if not self.mmregistered:
            self.ser.write(b'*A\n') # RegisterVictronGX_sendBackConfirmation

        ready = self.ser.in_waiting > 0

        if not ready:
            return False

        self.datagram = self.ser.read(self.ser.in_waiting)
        if len(self.datagram) < 41: # too short
            return False
        
        return True


    def _decode_data(self):    
            
        if self.datagram[:1] != b'*':
            print('wrong magic start')
            return
        
        if ["B", "C"] not in self.datagram[1:2]:
            print('command not recognized')
            return
        self.last_update = time.time()
        
        if self.datagram[1:2] == b'B': # RegisterVictronGXConfirmation
            self.mmregistered = True
            return
        
        if not self.mmregistered:
            print('module m not registered, trowing away data')
            return

        if self.datagram[1:2] == b'C':  # AmpsAndVoltage
            """struct VictronSerialAmpsAndVoltage {
                        uint8_t magic_start; // * 
                        uint8_t command;     // C
                        bool export_CT1;
                        bool export_CT2;
                        bool export_CT3;
                        uint32_t I1; // mA
                        uint32_t I2;
                        uint32_t I3;
                        uint32_t U1; // mV
                        uint32_t U2;
                        uint32_t U3;
                        uint32_t P1; // W
                        uint32_t P2;
                        uint32_t P3;
                    };"""
            print(f"Unpacked data length: {len(self.datagram)}")
            # Parse the data. the recieved data is in the form of the above c struct
            unpacked_data = struct.unpack("=2B3B9I", self.datagram[0:41])

            self.mmdata.command = unpacked_data[1]
            self.mmdata.export_CT1 = bool(unpacked_data[2])
            self.mmdata.export_CT2 = bool(unpacked_data[3])
            self.mmdata.export_CT3 = bool(unpacked_data[4])
            self.mmdata.I1 = unpacked_data[5]
            self.mmdata.I2 = unpacked_data[6]
            self.mmdata.I3 = unpacked_data[7]
            self.mmdata.U1 = unpacked_data[8]
            self.mmdata.U2 = unpacked_data[9]
            self.mmdata.U3 = unpacked_data[10]
            self.mmdata.P1 = unpacked_data[11]
            self.mmdata.P2 = unpacked_data[12]
            self.mmdata.P3 = unpacked_data[13]
            print("got new data: ", self.mmdata)

    

    def _connect_serial(self):
        self.ser = None
        port_name = None
        for port in serial.tools.list_ports.comports():
            if port.vid == VID and port.pid == PID:
                port_name = port.name
                break

        if port_name is None:
            logging.error('No Module M found')
            return False
        
        if not WINDOWS:
            port_name = f"/dev/{port_name}"
        
        self.ser = serial.Serial(port_name, 115200, timeout=1)
        return True
        


if __name__ == "__main__":
    # sma = ModuleM()
    for port in serial.tools.list_ports.comports():
            print(port.vid, port.pid, "desc", port.name)
    exit()
    while True:
        if sma._read_data(timeout=1):
            sma._decode_data()
            print(sma.hmdata)
        else:
            if sma.last_update + 5 < time.time():
                print('not updated for 5 seconds')
                sma.hmdata = {}
    