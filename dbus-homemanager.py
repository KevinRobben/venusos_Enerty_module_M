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
        self._dbusservice.add_path('/Mgmt/Connection', f'LORA connection')

        # Register mandatory objects
        self._dbusservice.add_path('/DeviceInstance', deviceinstance)
        self._dbusservice.add_path('/ProductId', 45058)  # value used in ac_sensor_bridge.cpp of dbus-cgwacs
        self._dbusservice.add_path('/ProductName', productname)
        # self._dbusservice.add_path('/FirmwareVersion', self.home_manager.hmdata['fw_version'])
        self._dbusservice.add_path('/HardwareVersion', 0)
        self._dbusservice.add_path('/Connected', 1)
        # self._dbusservice.add_path('/Serial', self.home_manager.hmdata['serial'])
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
        # self._dbusservice.add_path('/Ac/L1/Energy/Forward', 0, gettextcallback=self._get_text_for_kwh)
        # self._dbusservice.add_path('/Ac/L2/Energy/Forward', 0, gettextcallback=self._get_text_for_kwh)
        # self._dbusservice.add_path('/Ac/L3/Energy/Forward', 0, gettextcallback=self._get_text_for_kwh)
        # self._dbusservice.add_path('/Ac/L1/Energy/Reverse', 0, gettextcallback=self._get_text_for_kwh)
        # self._dbusservice.add_path('/Ac/L2/Energy/Reverse', 0, gettextcallback=self._get_text_for_kwh)
        # self._dbusservice.add_path('/Ac/L3/Energy/Reverse', 0, gettextcallback=self._get_text_for_kwh)
        # self._dbusservice.add_path('/Ac/Energy/Forward', 0, gettextcallback=self._get_text_for_kwh)
        # self._dbusservice.add_path('/Ac/Energy/Reverse', 0, gettextcallback=self._get_text_for_kwh)
        self._dbusservice.add_path('/Ac/Current', 0, gettextcallback=self._get_text_for_a)

        gobject.timeout_add(450, self._update)

    def _update(self):
        if self.module_m._read_data():
            self.module_m._decode_data()
        else:
            if time.time() - self.module_m.last_update > 20:
                logging.error('No data received from Module M for 20 seconds, setting all values to zero and trying to reconnect')
                self.module_m.mmdata.set_all_to_zero()
                self.module_m.last_update = time.time()
                # try to reconnect to the serial port, the port might have been disconnected (physically or by the OS)
                self.module_m._connect_serial()

        with contextlib.suppress(KeyError):
            # Check if the Home Manager is single phase or three phase
            if self.module_m.mmdata.I2 == 0 and self.module_m.mmdata.I3 == 0:
                single_phase = True
            else:
                single_phase = False
            
            # Calculate the total current
            if single_phase:
                current = self.module_m.mmdata.I1
            else:
                current = round((self.module_m.mmdata.I1 + self.module_m.mmdata.I2 +
                                self.module_m.mmdata.I3) / 1000, 3)
                
            self._dbusservice['/Ac/Current'] = current

            P1 = -self.module_m.mmdata.P1 if self.module_m.mmdata.export_CT1 else self.module_m.mmdata.P1 # W
            P2 = -self.module_m.mmdata.P2 if self.module_m.mmdata.export_CT2 else self.module_m.mmdata.P2 # W
            P3 = -self.module_m.mmdata.P3 if self.module_m.mmdata.export_CT3 else self.module_m.mmdata.P3 # W

            self._dbusservice['/Ac/Power'] = (P1 + P2 + P3) / 1000  #kw
            
            # self._dbusservice['/Ac/Energy/Forward'] = self.module_m.hmdata.get('positive_active_energy', 0)
            # self._dbusservice['/Ac/Energy/Reverse'] = self.module_m.hmdata.get('negative_active_energy', 0)


            self._dbusservice['/Ac/L1/Voltage'] = self.module_m.mmdata.U1 / 1000
            self._dbusservice['/Ac/L2/Voltage'] = self.module_m.mmdata.U2 / 1000
            self._dbusservice['/Ac/L3/Voltage'] = self.module_m.mmdata.U3 / 1000
            self._dbusservice['/Ac/L1/Current'] = self.module_m.mmdata.I1 / 1000
            self._dbusservice['/Ac/L2/Current'] = self.module_m.mmdata.I2 / 1000
            self._dbusservice['/Ac/L3/Current'] = self.module_m.mmdata.I3 / 1000

            self._dbusservice['/Ac/L1/Power'] = P1 / 1000
            self._dbusservice['/Ac/L2/Power'] = P2 / 1000
            self._dbusservice['/Ac/L3/Power'] = P3 / 1000
            
            # self._dbusservice['/Ac/L1/Energy/Forward'] = self.module_m.hmdata.get('positive_active_energy_L1', 0)
            # self._dbusservice['/Ac/L2/Energy/Forward'] = self.module_m.hmdata.get('positive_active_energy_L2', 0)
            # self._dbusservice['/Ac/L3/Energy/Forward'] = self.module_m.hmdata.get('positive_active_energy_L3', 0)
            # self._dbusservice['/Ac/L1/Energy/Reverse'] = self.module_m.hmdata.get('negative_active_energy_L1', 0)
            # self._dbusservice['/Ac/L2/Energy/Reverse'] = self.module_m.hmdata.get('negative_active_energy_L2', 0)
            # self._dbusservice['/Ac/L3/Energy/Reverse'] = self.module_m.hmdata.get('negative_active_energy_L3', 0)
        return True

    def _handle_changed_value(self, value):
        logging.debug(f"Object {self} has been changed to {value}")
        return True

    def _get_text_for_kwh(self, path, value):
        return "%.3FkWh" % (float(value) / 1000.0)

    def _get_text_for_w(self, path, value):
        return "%.1FW" % (float(value))

    def _get_text_for_v(self, path, value):
        return "%.2FV" % (float(value))

    def _get_text_for_a(self, path, value):
        return "%.2FA" % (float(value))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    thread.daemon = True
    DBusGMainLoop(set_as_default=True)
    DbusENERTYService(servicename='com.victronenergy.grid.tcpip_239_12_255_254', deviceinstance=40)
    logging.info('Connected to dbus, switching over to gobject.MainLoop()')
    mainloop = gobject.MainLoop()
    mainloop.run()
