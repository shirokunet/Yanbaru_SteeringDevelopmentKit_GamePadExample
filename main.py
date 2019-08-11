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
from enum import Enum
from inputs.inputs import DeviceManager
from multiprocessing import Process, Value


class Action_t(Enum):
    ACTION_NONE = -1
    ACTION_CALIBRATION = 0
    ACTION_IDLE = 1
    ACTION_CLOSEDLOOP = 2
    ACTION_POSITION_CTRL = 3
    ACTION_TRAJECTRY_CTRL = 4
    ACTION_VELOCITY_CTRL = 5
    ACTION_GET_POSITION = 6


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
                        self.gp_value.value = event.state
                    except:
                        self._logger.error('Could not find {}'.format(event.code))
        except:
            self._logger.error('Close GamePad Process')
            self.is_run.value = False


class SerilaMp():
    def __init__(self, logger, port='/dev/ttyACM_f446re', baud=115200, timeout=0.1):
        self._logger = logger
        self.is_run = Value(ctypes.c_bool, False)

        # communication variables
        self.request_mode = Value(ctypes.c_int, Action_t.ACTION_NONE.value)

        self.rx_stw_mode = Value(ctypes.c_int, 0)
        self.rx_actual_angle_lpf = Value(ctypes.c_double, 0.0)
        self.rx_target_angle_lpf = Value(ctypes.c_double, 0.0)
        self.rx_selector_switch = Value(ctypes.c_int, 0)
        self.rx_actual_encoder_pos = Value(ctypes.c_int, 0)
        self.rx_potentio_a_raw = Value(ctypes.c_int, 0)

        # try to open com port
        try:
            if port == 'auto':
                use_port = self._search_com_port()
            else:
                use_port = port
            self._logger.debug('Open COM Port')
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
                if self.request_mode.value == Action_t.ACTION_NONE.value:
                    # receive task
                    string_data = self._ser.readline().decode('utf-8')
                    dlist = string_data.split(',')
                    if dlist[0] == '#' and len(dlist) == 12:
                        self.rx_stw_mode.value = int(dlist[1])
                        self.rx_actual_angle_lpf.value = float(dlist[2])
                        self.rx_target_angle_lpf.value = float(dlist[3])
                        self.rx_selector_switch.value = int(dlist[4])
                        self.rx_actual_encoder_pos.value = int(dlist[5])
                        self.rx_potentio_a_raw.value = int(dlist[6])
                    else:
                        self._logger.error('--- Unexpected Rx Data ---')
                        self._logger.info(len(dlist))
                        self._logger.info(dlist)

                elif self.request_mode.value == Action_t.ACTION_CALIBRATION.value:
                    self._logger.info('ACTION_CALIBRATION')
                    self._ser.write(b'c\n')
                    self.request_mode.value = Action_t.ACTION_NONE.value

                elif self.request_mode.value == Action_t.ACTION_CLOSEDLOOP.value:
                    self._logger.info('ACTION_CLOSEDLOOP')
                    self._ser.write(b'l\n')
                    self.request_mode.value = Action_t.ACTION_NONE.value

                elif self.request_mode.value == Action_t.ACTION_IDLE.value:
                    self._logger.info('ACTION_IDLE')
                    self._ser.write(b'i\n')
                    self.request_mode.value = Action_t.ACTION_NONE.value

                else:
                    self.request_mode.value = Action_t.ACTION_NONE.value

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


def is_up(data, data_z1, key):
    if data_z1['gp_code'] != key \
            and data['gp_code'] == key and data['gp_value'] == 1:
        return True
    elif data_z1['gp_code'] == key and data_z1['gp_value'] == 0 \
            and data['gp_code'] == key and data['gp_value'] == 1:
        return True
    else:
        return False


def main():
    try:
        # get yaml config file
        ymlfile = open('config.yml')
        cfg = yaml.load(ymlfile)
        ymlfile.close()

        # logging setting
        if cfg['log_level'] == 'debug':
            logger_main = set_logging('main', level=logging.DEBUG)
        else:
            logger_main = set_logging('main')

        # instance setting
        serial_mp = SerilaMp(logger_main, baud=cfg['stw_baud'])
        gamepad_mp = GamePadMp(logger_main)
        logger_main.debug('GamePad: {}'.format(gamepad_mp.is_run.value))
        logger_main.debug('Serial: {}'.format(serial_mp.is_run.value))

        # z1
        console_time_z1 = time.time()
        gp_data_z1 = False
        rx_data_z1 = False

        # main loop
        while gamepad_mp.is_run.value and serial_mp.is_run.value:
            time_now = time.time()

            # update sensors
            gp_data = {'gp_code': hex(gamepad_mp.gp_code.value),
                       'gp_value': gamepad_mp.gp_value.value}
            rx_data = {'rx_stw_mode': serial_mp.rx_stw_mode.value,
                       'rx_actual_angle_lpf': serial_mp.rx_actual_angle_lpf.value,
                       'rx_target_angle_lpf': serial_mp.rx_target_angle_lpf.value,
                       'rx_selector_switch': serial_mp.rx_selector_switch.value,
                       'rx_actual_encoder_pos': serial_mp.rx_actual_encoder_pos.value,
                       'rx_potentio_a_raw': serial_mp.rx_potentio_a_raw.value}

            # action
            if not gp_data_z1:
                pass
            elif gp_data['gp_code'] == '0x3':
                serial_mp.request_mode.value = Action_t.ACTION_VELOCITY_CTRL.value
            elif is_up(gp_data, gp_data_z1, '0x13c'):
                serial_mp.request_mode.value = Action_t.ACTION_CALIBRATION.value
            elif is_up(gp_data, gp_data_z1, '0x13b'):
                serial_mp.request_mode.value = Action_t.ACTION_CLOSEDLOOP.value
            elif is_up(gp_data, gp_data_z1, '0x13a'):
                serial_mp.request_mode.value = Action_t.ACTION_IDLE.value

            # debug console
            if time_now - console_time_z1 > 0.1:
                console_time_z1 = time_now
                logger_main.debug(json.dumps(gp_data))
                logger_main.debug(json.dumps(rx_data))
                logger_main.debug('\n')

            # store z1
            gp_data_z1 = gp_data
            rx_data_z1 = rx_data

            time.sleep(0.01)
    except KeyboardInterrupt:
        pass

    serial_mp.close()
    gamepad_mp.close()
    print('End Program')


if __name__ == '__main__':
    main()
