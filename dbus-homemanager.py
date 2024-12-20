#!/usr/bin/env python3

import contextlib
import logging
import time
from gi.repository import GLib as gobject
from dbus.mainloop.glib import DBusGMainLoop
import sys
import os
import _thread as thread
from module_m_decoder import ModuleM

# necessary packages from victron
sys.path.insert(1, os.path.join(os.path.dirname(__file__), '/opt/victronenergy/dbus-systemcalc-py/ext/velib_python')) # './ext/velib_python'
from vedbus import VeDbusService

VERSION = '2024.01'


class DbusENERTYService:
    def __init__(self, servicename, deviceinstance, productname='ENERTY Module M reciever'):
        self.module_m = ModuleM()

        # Read data from Home Manager once to get the serial number and firmware version
        # if not self.home_manager._read_data(timeout=10):
        #     logging.error('Could not read data from Home Manager, aborting startup')
        #     sys.exit(1)
        # self.home_manager._decode_data()

        self._dbusservice = VeDbusService("{}.http_{:02d}".format(servicename, deviceinstance))
        logging.debug(f"{servicename} /DeviceInstance = {deviceinstance}")

        # Register management objects, see dbus-api for more information
        self._dbusservice.add_path('/Mgmt/ProcessName', productname)
        self._dbusservice.add_path('/Mgmt/ProcessVersion', VERSION)
        self._dbusservice.add_path('/Mgmt/Connection', None)

        # Register mandatory objects
        self._dbusservice.add_path('/DeviceInstance', deviceinstance)
        self._dbusservice.add_path('/ProductId', 45058)  # value used in ac_sensor_bridge.cpp of dbus-cgwacs
        self._dbusservice.add_path('/ProductName', productname)
        # self._dbusservice.add_path('/FirmwareVersion', self.home_manager.hmdata['fw_version'])
        self._dbusservice.add_path('/HardwareVersion', 0)
        self._dbusservice.add_path('/Connected', 1)
        self._dbusservice.add_path('/Serial', "00000000000")
        self._dbusservice.add_path('/ErrorCode', 'No Errors detected. This is just a test\nmaybe this should be on the second line?. Or maybe not, who knows?\nThis is a third error.\nThis is a fourth error.')
        self._dbusservice.add_path('/Ac/Power', 0, gettextcallback=self._get_text_for_w)
        self._dbusservice.add_path('/Ac/L1/Voltage', 0, gettextcallback=self._get_text_for_v)
        self._dbusservice.add_path('/Ac/L2/Voltage', 0, gettextcallback=self._get_text_for_v)
        self._dbusservice.add_path('/Ac/L3/Voltage', 0, gettextcallback=self._get_text_for_v)
        self._dbusservice.add_path('/Ac/L1/Current', 0, gettextcallback=self._get_text_for_a)
        self._dbusservice.add_path('/Ac/L2/Current', 0, gettextcallback=self._get_text_for_a)
        self._dbusservice.add_path('/Ac/L3/Current', 0, gettextcallback=self._get_text_for_a)
        self._dbusservice.add_path('/Ac/L1/Power', 0, gettextcallback=self._get_text_for_w)
        self._dbusservice.add_path('/Ac/L2/Power', 0, gettextcallback=self._get_text_for_w)
        self._dbusservice.add_path('/Ac/L3/Power', 0, gettextcallback=self._get_text_for_w)

        self._dbusservice.add_path('/Ac/L1/Energy/Forward', 0, gettextcallback=self._get_text_for_kwh)
        self._dbusservice.add_path('/Ac/L2/Energy/Forward', 0, gettextcallback=self._get_text_for_kwh)
        self._dbusservice.add_path('/Ac/L3/Energy/Forward', 0, gettextcallback=self._get_text_for_kwh)
        self._dbusservice.add_path('/Ac/L1/Energy/Reverse', 0, gettextcallback=self._get_text_for_kwh)
        self._dbusservice.add_path('/Ac/L2/Energy/Reverse', 0, gettextcallback=self._get_text_for_kwh)
        self._dbusservice.add_path('/Ac/L3/Energy/Reverse', 0, gettextcallback=self._get_text_for_kwh)
        self._dbusservice.add_path('/Ac/Energy/Forward', 0, gettextcallback=self._get_text_for_kwh)
        self._dbusservice.add_path('/Ac/Energy/Reverse', 0, gettextcallback=self._get_text_for_kwh)
        self._dbusservice.add_path('/Ac/Current', 0, gettextcallback=self._get_text_for_a)

        gobject.timeout_add(300, self._update)

        self.last_error_switch = time.time()

    def _update(self):

        # Check for errors every 10 seconds
        if time.time() - self.last_error_switch > 10:
            if len(self.module_m.errors) == 0:
                self._dbusservice['/ErrorCode'] = None
            else:
                if self.module_m.errors_show_index > len(self.module_m.errors) - 1:
                    self.module_m.errors_show_index = 0
                self._dbusservice['/ErrorCode'] = self.module_m.errors[self.module_m.errors_show_index]
                self.module_m.errors_show_index += 1

        if self.module_m._read_data() and self.module_m._decode_data():
            pass
        else:
            if time.time() - self.module_m.last_update > 10:
                logging.error('No data received from Module M for 10 seconds, setting all values to zero')
                self.module_m.mmdata.set_all_to_zero()
                self.module_m.last_update = time.time()
        
        # settings or errors from the module_m object
        if self.module_m.new_port_name:
            self._dbusservice['/Mgmt/Connection'] = self.module_m.ser.portstr
            self.module_m.new_port_name = False
        if self.module_m.new_serialnumber:
            try:
                self._dbusservice['/Serial'] = self.module_m.serialnumber.decode('utf-8')
            except Exception as e:
                logging.error(f"Error setting serial number: {e}")
            self.module_m.new_serialnumber = False


        with contextlib.suppress(KeyError):
            # Check if the Home Manager is single phase or three phase
            if self.module_m.mmdata.I2 == 0 and self.module_m.mmdata.I3 == 0 and self.module_m.mmdata.U2 == 0 and self.module_m.mmdata.U3 == 0:
                single_phase = True
            else:
                single_phase = False
            
            # Calculate the total current
            if single_phase:
                current = round(self.module_m.mmdata.I1 / 1000, 3)
            else:
                current = round((self.module_m.mmdata.I1 + self.module_m.mmdata.I2 +
                                self.module_m.mmdata.I3) / 1000, 3)
                
            self._dbusservice['/Ac/Current'] = current

            P1 = -self.module_m.mmdata.P1 if self.module_m.mmdata.export_CT1 else self.module_m.mmdata.P1 # W
            P2 = -self.module_m.mmdata.P2 if self.module_m.mmdata.export_CT2 else self.module_m.mmdata.P2 # W
            P3 = -self.module_m.mmdata.P3 if self.module_m.mmdata.export_CT3 else self.module_m.mmdata.P3 # W

            self._dbusservice['/Ac/Power'] = (P1 + P2 + P3) / 1000  #kw
            
            self._dbusservice['/Ac/Energy/Forward'] = self.module_m.mmdata.energy_forward / 1000  #kWh
            self._dbusservice['/Ac/Energy/Reverse'] = self.module_m.mmdata.energy_reverse / 1000

            self._dbusservice['/Ac/L1/Voltage'] = self.module_m.mmdata.U1 / 1000
            self._dbusservice['/Ac/L2/Voltage'] = self.module_m.mmdata.U2 / 1000
            self._dbusservice['/Ac/L3/Voltage'] = self.module_m.mmdata.U3 / 1000
            self._dbusservice['/Ac/L1/Current'] = self.module_m.mmdata.I1 / 1000
            self._dbusservice['/Ac/L2/Current'] = self.module_m.mmdata.I2 / 1000
            self._dbusservice['/Ac/L3/Current'] = self.module_m.mmdata.I3 / 1000

            self._dbusservice['/Ac/L1/Power'] = P1 / 1000
            self._dbusservice['/Ac/L2/Power'] = P2 / 1000
            self._dbusservice['/Ac/L3/Power'] = P3 / 1000
            
            # return here if all values are set to zero. This way the AC totals are not updated and still visible in the dbus
            if self.module_m.mmdata.I1 == 0 and self.module_m.mmdata.U1 == 0:
                return True
            if single_phase:
                self._dbusservice['/Ac/L1/Energy/Forward'] = self.module_m.mmdata.energy_forward / 1000
                self._dbusservice['/Ac/L2/Energy/Forward'] = 0
                self._dbusservice['/Ac/L3/Energy/Forward'] = 0
                self._dbusservice['/Ac/L1/Energy/Reverse'] = self.module_m.mmdata.energy_reverse / 1000
                self._dbusservice['/Ac/L2/Energy/Reverse'] = 0
                self._dbusservice['/Ac/L3/Energy/Reverse'] = 0
            else:
                self._dbusservice['/Ac/L1/Energy/Forward'] = round(self.module_m.mmdata.energy_forward / 3000, 3)
                self._dbusservice['/Ac/L2/Energy/Forward'] = round(self.module_m.mmdata.energy_forward / 3000, 3)
                self._dbusservice['/Ac/L3/Energy/Forward'] = round(self.module_m.mmdata.energy_forward / 3000, 3)
                self._dbusservice['/Ac/L1/Energy/Reverse'] = round(self.module_m.mmdata.energy_reverse / 3000, 3)
                self._dbusservice['/Ac/L2/Energy/Reverse'] = round(self.module_m.mmdata.energy_reverse / 3000, 3)
                self._dbusservice['/Ac/L3/Energy/Reverse'] = round(self.module_m.mmdata.energy_reverse / 3000, 3)
        return True # Return True to keep looping

    def _handle_changed_value(self, value):
        logging.debug(f"Object {self} has been changed to {value}")
        return True # Return True to keep looping

    def _get_text_for_kwh(self, path, value):
        return "%.2FkWh" % (float(value))

    def _get_text_for_w(self, path, value):
        return "%iW" % (float(value))

    def _get_text_for_v(self, path, value):
        return "%.2FV" % (float(value))

    def _get_text_for_a(self, path, value):
        return "%.1FA" % (float(value))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    thread.daemon = True
    DBusGMainLoop(set_as_default=True)
    DbusENERTYService(servicename='com.victronenergy.grid.tcpip_239_12_255_254', deviceinstance=40)
    logging.info('Connected to dbus, switching over to gobject.MainLoop()')
    mainloop = gobject.MainLoop()
    mainloop.run()
