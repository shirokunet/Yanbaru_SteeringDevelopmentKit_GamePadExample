#!/usr/bin/python3
# -*- coding: utf-8 -*-

import ctypes
import serial
import serial.tools.list_ports
import time
from enum import Enum
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


class SerilaMp():
    def __init__(self, logger, port='/dev/ttyACM_f446re', baud=115200, timeout=0.1):
        self._logger = logger
        self.is_run = Value(ctypes.c_bool, False)

        # communication variables
        self.request_mode = Value(ctypes.c_int, Action_t.ACTION_NONE.value)
        self.target_angle = Value(ctypes.c_double, 0.0)

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
            self._logger.debug('Open Nucleo COM Port')
            self._ser = serial.Serial(use_port, baud, timeout=timeout)
            self._ser.readline()
            # dummy message to clear buffer
            self._ser.write(b'\n')
        except:
            self._logger.error('Serial Nucleo COM Port Open Error')
            return

        # z1
        self._target_angle_z1 = 0.0

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

                elif self.request_mode.value == Action_t.ACTION_VELOCITY_CTRL.value \
                        and self.target_angle.value != self._target_angle_z1:
                    self._logger.info('ACTION_VELOCITY_CTRL {}'.format(self.target_angle.value))
                    self._ser.write('p,{}\n\r'.format(int(self.target_angle.value * 1000.0)).encode())
                    self.request_mode.value = Action_t.ACTION_NONE.value
                    self._target_angle_z1 = self.target_angle.value

                else:
                    self.request_mode.value = Action_t.ACTION_NONE.value

                time.sleep(0.01)
        except:
            self.is_run.value = False
        self._ser.close()
