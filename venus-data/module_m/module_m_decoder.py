import copy
import select
import struct
import logging
import socket
import sys
import time
import serial
import serial.tools.list_ports
import subprocess

VID = 0x239A
PID = 0x80A4

# Open the serial port
WINDOWS = sys.platform.startswith('win')

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
        self.energy_forward: int = 0 # Wh
        self.energy_reverse: int = 0
        
    
    def set_all_to_zero(self):
        self.I1 = 0
        self.I2 = 0
        self.I3 = 0
        # self.U1 = 0 # let voltage be normal
        # self.U2 = 0
        # self.U3 = 0
        self.P1 = 0
        self.P2 = 0
        self.P3 = 0

    def __str__(self) -> str:
        return f"command: {self.command}, AC Phase L1: {self.U1 / 1000}V {self.I1 / 1000}A {self.P1 / 1000}W. AC Phase L2: {self.U2 / 1000}V {self.I2 / 1000}A {self.P2 / 1000}W. AC Phase L3: {self.U3 / 1000}V {self.I3 / 1000}A {self.P3 / 1000}W  -  ENERGY -> Forward: {self.energy_forward / 1000}kWh. Deverse: {self.energy_reverse / 1000}kWh"


class ModuleM:

    def __init__(self):
        self.ser = serial.Serial(None, 9600, timeout=0, rtscts=False, dsrdtr=False, xonxoff=False)
        self.datagram = b""
        self.serialnumber = None
        self.mmdata = VictronSerialAmpsAndVoltage()
        self.mmregistered = False # module m registered with *B command
        self.last_update = time.time()
        self.mmregistered_last_register_request = time.time()

        # communication signals for dbus-homemanager
        self.new_port_name = False
        self.new_serialnumber = False
        self.errors = []
        self.errors_show_index = 0 # the current displayed error in victron

    def _read_data(self):
        try:
            in_waiting = self.ser.in_waiting
            ready = in_waiting > 0
        except Exception as e: # attribute error is thrown when no port passed to serial.Serial
            print("Serial port closed")
            self.mmregistered = False
            if self.ser.port is not None and self.ser.is_open:
                self.ser.close()
            for port in serial.tools.list_ports.comports():
                if port.vid == VID and port.pid == PID:
                    port_name = port.name
                    if not WINDOWS:
                        port_name = f"/dev/{port_name}"
                        try:
                            subprocess.run(["/opt/victronenergy/serial-starter/stop-tty.sh", port.name])
                        except subprocess.CalledProcessError as e:
                            # Handle cases where the command fails
                            print(f"stop serial starter command CalledProcessError with return code: {e.returncode}")
                        except FileNotFoundError:
                            # Handle case where the script is not found
                            print("The stop serial starter command or script does not exist. Please check the path.")
                    self.ser.port = port_name
                    self.new_port_name = True
                    print(f"Found Module M on {port_name}")
                    self.ser.open()
                    in_waiting = self.ser.in_waiting
                    ready = in_waiting > 0
                    break
            else:
                print("Module M not found")
                return False
            
        if not self.mmregistered and time.time() - self.mmregistered_last_register_request > 2:
            self.mmregistered_last_register_request = time.time()
            print("Registering VictronGX, sending *A")
            try:
                self.ser.write(b'*A\n') # RegisterVictronGX_sendBackConfirmation
            except serial.SerialException as e:
                logging.error('Could not write to serial port: %s', e.args[0])
            return False

        if not ready and self.datagram == b'':
            # print('no data ready')
            return False

        self.datagram += self.ser.read(in_waiting)
        while len(self.datagram) > 1 and self.datagram[:1] != b'*': # remove garbage data
            # print('removing garbage data: ', self.datagram[:1])
            self.datagram = self.datagram[1:]
        if len(self.datagram) == 1 and self.datagram[0] != b'*': # remove garbage data
            self.datagram = b""
            return False
        
        return True


    def _decode_data(self):    
        if self.datagram[:1] != b'*':
            print('wrong magic start: ', self.datagram)
            self.datagram = self.datagram[1:]
            return False
        
        if self.datagram[1:2] not in [b"B", b"C", b"D", b"E"]:
            print('command not recognized: ', self.datagram)
            self.datagram = self.datagram[2:]
            return False
        self.last_update = time.time()
        
        if not self.mmregistered:
            # search for the registration command inside the datagram
            while len(self.datagram) > 2 and self.datagram[:2] != b'*B': # remove garbage data until we find RegisterVictronGXConfirmation
                self.datagram = self.datagram[1:]

            if len(self.datagram) >= 13:
                self.mmregistered = True
                self.datagram = self.datagram[2:13]
                self.serialnumber = copy.deepcopy(self.datagram)
                self.new_serialnumber = True
                print("Module M registered")
                return False
            print('module m not registered, trowing away data: ', self.datagram)
            self.datagram = b""
            return False

        if self.datagram[:2] == b'*E':  # Errors
            """struct VictronSerialErrorCodes {
                uint8_t magic_start;
                uint8_t command;
                uint8_t errorCodeLines; // the amount of lines that follow (\n) with error messages
            };"""
            print("recieved errors")
            if len(self.datagram) < 3:
                print('not enough data: ', self.datagram)
                return False
            # Parse the data. the recieved data is in the form of the above c struct
            unpacked_data = struct.unpack("=3B", self.datagram[0:3])
            if (unpacked_data[2] == 0):
                self.errors = []
                self.datagram = self.datagram[3:]
                return False
            errors = self.datagram.split(b"\r\n")
            if len(errors) < unpacked_data[2]:
                print('not enough data: ', self.datagram)
                return False
            errors[0] = errors[0][3:] # remove the first 3 bytes
            self.errors = errors[:unpacked_data[2]] # remove any extra data
            self.datagram = b"" # remove any extra data
            print("got ", unpacked_data[2], " new errors: ", self.errors)        
              
            

        if self.datagram[:2] == b'*C':  # AmpsAndVoltage
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
            if len(self.datagram) < 41:
                print('not enough data: ', self.datagram)
                return False
            print(f"Unpacked data length: {len(self.datagram)}")
            # Parse the data. the recieved data is in the form of the above c struct
            unpacked_data = struct.unpack("=2B3B9I", self.datagram[0:41])
            self.datagram = self.datagram[41:]

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
            # do not alter energy values. They stay the same until new *D data is received
            print("got new data: ", self.mmdata)    
            return True   
        
        if self.datagram[:2] == b'*D':  # Energy
            """struct VictronSerialAmpsVoltageAndEnergy {
                        struct VictronSerialAmpsAndVoltage ampsAndVoltage;
                        uint32_t energy_delivered; // Wh
                        uint32_t energy_returned; // Wh
                    };"""
            if len(self.datagram) < 49:
                print('not enough data: ', self.datagram)
                return False
            print(f"Unpacked data length: {len(self.datagram)}")
            # Parse the data. the recieved data is in the form of the above c struct
            unpacked_data = struct.unpack("=2B3B9I2I", self.datagram[0:49])
            self.datagram = self.datagram[41:]

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
            self.mmdata.energy_forward = unpacked_data[14]
            self.mmdata.energy_reverse = unpacked_data[15]
            print("got new data: ", self.mmdata)    
            return True   
        
        print("unknown command: ", self.datagram)
        self.datagram = b""
        return False

if __name__ == "__main__":
    sma = ModuleM()
    for port in serial.tools.list_ports.comports():
            print(port.vid, port.pid, "desc", port.name)
    
    while True:
        if sma._read_data() and sma._decode_data():
            # print(sma.mmdata)
            pass
        else:
            if sma.last_update + 5 < time.time():
                print('not updated for 5 seconds')
                sma.mmdata.set_all_to_zero()
        time.sleep(1)
    