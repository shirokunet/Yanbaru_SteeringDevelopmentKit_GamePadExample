#!/usr/bin/python3
# -*- coding: utf-8 -*-

import ctypes
import datetime
import json
import logging
import serial
import serial.tools.list_ports
import time
import yaml
from inputs import DeviceManager
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
                        self.gp_value.value = int(event.state)
                    except:
                        self._logger.error('Could not find {}'.format(event.code))
        except:
            self._logger.error('Close GamePad Process')
            self.is_run.value = False


class SerilaMp():
    def __init__(self, logger, baud=115200, timeout=0.1):
        self._logger = logger
        self.is_run = Value(ctypes.c_bool, False)

        # communication variables
        self.stw_mode = Value(ctypes.c_int, 0)
        self.actual_angle_lpf = Value(ctypes.c_double, 0.0)
        self.target_angle_lpf = Value(ctypes.c_double, 0.0)
        self.selector_switch = Value(ctypes.c_int, 0)
        self.actual_encoder_pos = Value(ctypes.c_int, 0)
        self.potentio_a_raw = Value(ctypes.c_int, 0)

        # try to open com port
        try:
            self._logger.debug('Open COM Port')
            use_port = self._search_com_port()
            self._ser = serial.Serial(use_port, baud, timeout=timeout)
            self._ser.readline()
        except:
            self._logger.error('Serial COM Port Open Error')
            return

        # start process
        self.is_run.value = True
        self._p = Process(target=self._process, args=())
        self._p.start()

    def close(self):
        self.is_run.value = False

    def _search_com_port(self):
        coms = serial.tools.list_ports.comports()
        comlist = []
        for com in coms:
            comlist.append(com.device)
        self._logger.debug('Connected COM ports: ' + str(comlist))

        if len(comlist) > 0:
            use_port = comlist[0]
            self._logger.debug('Use COM port: ' + use_port)
        else:
            use_port = False
            self._logger.debug('Could not find COM port')
        return use_port

    def _process(self):
        try:
            while self.is_run.value:
                string_data = self._ser.readline().decode('utf-8')
                dlist = string_data.split(',')
                if dlist[0] == '#' and len(dlist) == 12:
                    self.stw_mode.value = int(dlist[1])
                    self.actual_angle_lpf.value = float(dlist[2])
                    self.target_angle_lpf.value = float(dlist[3])
                    self.selector_switch.value = int(dlist[4])
                    self.actual_encoder_pos.value = int(dlist[5])
                    self.potentio_a_raw.value = int(dlist[6])
                else:
                    self._logger.error('--- Unexpected Rx Data ---')
                    self._logger.info(len(dlist))
                    self._logger.info(dlist)
                time.sleep(0.01)
        except:
            self.is_run.value = False
        self._ser.close()


def set_logging(name, level=logging.INFO, stream=True, file=True, dir='log/', filetype='.log'):
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # StreamHandler
    if stream:
        formatter = logging.Formatter('[%(asctime)s] %(module)s.%(funcName)s %(levelname)s -> %(message)s')
        sh = logging.StreamHandler()
        sh.setFormatter(formatter)
        logger.addHandler(sh)

    # FileHandler
    if file:
        formatter = logging.Formatter('%(asctime)s,%(created)s,%(module)s,%(funcName)s,%(levelname)s,%(message)s')
        current_datetime = datetime.datetime.now()
        filename = dir + current_datetime.strftime('20%y%m%d_%H%M') + name + filetype
        fh = logging.FileHandler(filename, )
        fh.setFormatter(formatter)
        logger.addHandler(fh)

    return logger


def main():
    try:
        ymlfile = open('config.yml')
        cfg = yaml.load(ymlfile)
        ymlfile.close()

        # logging setting
        if cfg['log_level'] == 'debug':
            logger_main = set_logging('main', level=logging.DEBUG)
        else:
            logger_main = set_logging('main')

        serial_mp = SerilaMp(logger_main, baud=cfg['stw_baud'])
        gamepad_mp = GamePadMp(logger_main)

        logger_main.debug('GamePad: {}'.format(gamepad_mp.is_run.value))
        logger_main.debug('Serial: {}'.format(serial_mp.is_run.value))
        while gamepad_mp.is_run.value \
                and serial_mp.is_run.value:
            gp_data = {'gp_code': gamepad_mp.gp_code.value,
                       'gp_value': gamepad_mp.gp_value.value}
            rx_data = {'rx_stw_mode': serial_mp.stw_mode.value,
                       'rx_actual_angle_lpf': serial_mp.actual_angle_lpf.value,
                       'rx_target_angle_lpf': serial_mp.target_angle_lpf.value,
                       'rx_selector_switch': serial_mp.selector_switch.value,
                       'rx_actual_encoder_pos': serial_mp.actual_encoder_pos.value,
                       'rx_potentio_a_raw': serial_mp.potentio_a_raw.value}
            logger_main.debug(json.dumps(gp_data))
            logger_main.debug(json.dumps(rx_data))
            time.sleep(0.01)
    except KeyboardInterrupt:
        pass
    serial_mp.close()
    gamepad_mp.close()
    print('End Program')


if __name__ == '__main__':
    main()
