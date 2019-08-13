#!/usr/bin/python3
# -*- coding: utf-8 -*-

import ctypes
from inputs.inputs import DeviceManager
from multiprocessing import Process, Value


class GamePadMp():
    def __init__(self, logger):
        self._logger = logger
        self.is_run = Value(ctypes.c_bool, False)

        # communication variables
        self.gp_code = Value(ctypes.c_int, 0)
        self.gp_value = Value(ctypes.c_int, 0)

        # try to connect gamepad
        try:
            devices = DeviceManager()
            self.gp_dict_code = devices.codes['Absolute']
            self.gp_dict_code.update(devices.codes['Key'])
            self._gamepad = devices.gamepads[0]
        except:
            self._logger.error("No gamepad found.")
            return

        # start process
        self.is_run.value = True
        self._p = Process(target=self._process, args=())
        self._p.start()
        return

    def close(self):
        self.is_run.value = False

    def is_up(self, data, data_z1, key):
        if data_z1['gp_code'] != key \
                and data['gp_code'] == key and data['gp_value'] == 1:
            return True
        elif data_z1['gp_code'] == key and data_z1['gp_value'] == 0 \
                and data['gp_code'] == key and data['gp_value'] == 1:
            return True
        else:
            return False

    def get_keys_from_value(self, d, val):
        return [k for k, v in d.items() if v == val]

    def _process(self):
        try:
            while self.is_run.value:
                events = self._gamepad.read()
                for event in events:
                    if event.ev_type == 'Sync':
                        continue
                    try:
                        key = self.get_keys_from_value(self.gp_dict_code, event.code)[0]
                        self.gp_code.value = int(key)
                        self.gp_value.value = event.state
                    except:
                        self._logger.error('Could not find {}'.format(event.code))
        except:
            self._logger.error('Close GamePad Process')
            self.is_run.value = False
