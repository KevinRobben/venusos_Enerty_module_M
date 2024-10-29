#!/usr/bin/env python3

import contextlib
import logging
import time
from gi.repository import GLib as gobject
from dbus.mainloop.glib import DBusGMainLoop
import sys
import os
import _thread as thread
from homemanager_decoder import HomeManager20, MCAST_GRP

# necessary packages from victron
sys.path.insert(1, os.path.join(os.path.dirname(__file__), '/opt/victronenergy/dbus-systemcalc-py/ext/velib_python')) # './ext/velib_python'
from vedbus import VeDbusService

VERSION = '2024.01'


class DbusSmaService:
    def __init__(self, servicename, deviceinstance, productname='Home Manager 2.0 dbus-bridge'):
        self.home_manager = HomeManager20()

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
        self._dbusservice.add_path('/Mgmt/Connection', f'TCP/IP multicast group {MCAST_GRP}')

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
        self._dbusservice.add_path('/Ac/L1/Energy/Forward', 0, gettextcallback=self._get_text_for_kwh)
        self._dbusservice.add_path('/Ac/L2/Energy/Forward', 0, gettextcallback=self._get_text_for_kwh)
        self._dbusservice.add_path('/Ac/L3/Energy/Forward', 0, gettextcallback=self._get_text_for_kwh)
        self._dbusservice.add_path('/Ac/L1/Energy/Reverse', 0, gettextcallback=self._get_text_for_kwh)
        self._dbusservice.add_path('/Ac/L2/Energy/Reverse', 0, gettextcallback=self._get_text_for_kwh)
        self._dbusservice.add_path('/Ac/L3/Energy/Reverse', 0, gettextcallback=self._get_text_for_kwh)
        self._dbusservice.add_path('/Ac/Energy/Forward', 0, gettextcallback=self._get_text_for_kwh)
        self._dbusservice.add_path('/Ac/Energy/Reverse', 0, gettextcallback=self._get_text_for_kwh)
        self._dbusservice.add_path('/Ac/Current', 0, gettextcallback=self._get_text_for_a)

        gobject.timeout_add(1000, self._update)

    def _update(self):
        if self.home_manager._read_data(timeout=1):
            self.home_manager._decode_data()
        else:
            if self.home_manager.last_update + 2 < time.time():
                logging.error('No data received from Home Manager for 2 seconds, setting all values to zero')
                self.home_manager.hmdata = {}
            
        if not self.home_manager.hmdata.get('serial', False):
            print("No serial number found, aborting update")
            return True

        with contextlib.suppress(KeyError):
            # Check if the Home Manager is single phase or three phase
            if self.home_manager.hmdata.get('current_L2', False) is False and self.home_manager.hmdata.get('current_L3', False) is False:
                single_phase = True
            else:
                single_phase = False
            
            # Calculate the total current
            if single_phase:
                current = self.home_manager.hmdata.get('current_L1', 0)
            else:
                current = round((self.home_manager.hmdata.get('current_L1', 0) + self.home_manager.hmdata.get('current_L2', 0) +
                                self.home_manager.hmdata.get('current_L3', 0)) / 3, 3)
                
            self._dbusservice['/Ac/Current'] = current
            self._dbusservice['/Ac/Power'] = self.home_manager.hmdata.get('positive_active_demand', 0) - \
                                             self.home_manager.hmdata.get('negative_active_demand', 0)
            
            self._dbusservice['/Ac/Energy/Forward'] = self.home_manager.hmdata.get('positive_active_energy', 0)
            self._dbusservice['/Ac/Energy/Reverse'] = self.home_manager.hmdata.get('negative_active_energy', 0)


            self._dbusservice['/Ac/L1/Voltage'] = self.home_manager.hmdata.get('voltage_L1', 0)
            self._dbusservice['/Ac/L2/Voltage'] = self.home_manager.hmdata.get('voltage_L2', 0)
            self._dbusservice['/Ac/L3/Voltage'] = self.home_manager.hmdata.get('voltage_L3', 0)
            self._dbusservice['/Ac/L1/Current'] = self.home_manager.hmdata.get('current_L1', 0)
            self._dbusservice['/Ac/L2/Current'] = self.home_manager.hmdata.get('current_L2', 0)
            self._dbusservice['/Ac/L3/Current'] = self.home_manager.hmdata.get('current_L3', 0)

            self._dbusservice['/Ac/L1/Power'] = self.home_manager.hmdata.get('positive_active_demand_L1', 0) - \
                                                self.home_manager.hmdata.get('negative_active_demand_L1', 0)
            self._dbusservice['/Ac/L2/Power'] = self.home_manager.hmdata.get('positive_active_demand_L2', 0) - \
                                                self.home_manager.hmdata.get('negative_active_demand_L2', 0)
            self._dbusservice['/Ac/L3/Power'] = self.home_manager.hmdata.get('positive_active_demand_L3', 0) - \
                                                self.home_manager.hmdata.get('negative_active_demand_L3', 0)
            
            self._dbusservice['/Ac/L1/Energy/Forward'] = self.home_manager.hmdata.get('positive_active_energy_L1', 0)
            self._dbusservice['/Ac/L2/Energy/Forward'] = self.home_manager.hmdata.get('positive_active_energy_L2', 0)
            self._dbusservice['/Ac/L3/Energy/Forward'] = self.home_manager.hmdata.get('positive_active_energy_L3', 0)
            self._dbusservice['/Ac/L1/Energy/Reverse'] = self.home_manager.hmdata.get('negative_active_energy_L1', 0)
            self._dbusservice['/Ac/L2/Energy/Reverse'] = self.home_manager.hmdata.get('negative_active_energy_L2', 0)
            self._dbusservice['/Ac/L3/Energy/Reverse'] = self.home_manager.hmdata.get('negative_active_energy_L3', 0)
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
    DbusSmaService(servicename='com.victronenergy.grid.tcpip_239_12_255_254', deviceinstance=40)
    logging.info('Connected to dbus, switching over to gobject.MainLoop()')
    mainloop = gobject.MainLoop()
    mainloop.run()
