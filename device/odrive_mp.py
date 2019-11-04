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


class AxisState_t(Enum):
    AXIS_STATE_UNDEFINED = 0
    AXIS_STATE_IDLE = 1
    AXIS_STATE_STARTUP_SEQUENCE = 2
    AXIS_STATE_FULL_CALIBRATION_SEQUENCE = 3
    AXIS_STATE_MOTOR_CALIBRATION = 4
    AXIS_STATE_SENSORLESS_CONTROL = 5
    AXIS_STATE_ENCODER_INDEX_SEARCH = 6
    AXIS_STATE_ENCODER_OFFSET_CALIBRATION = 7
    AXIS_STATE_CLOSED_LOOP_CONTROL = 8


class OdriveMp():
    def __init__(
            self, logger,
            port='/dev/ttyACM_odrive', baud=115200, timeout=0.1,
            speed_lim=40000.0, current_lim=70.0, lpf_gain=0.05, calibration_current=10.0):
        self._logger = logger
        self.is_run = Value(ctypes.c_bool, False)
        self._speed_lim = speed_lim
        self._current_lim = current_lim

        # communication variables
        self.request_mode = Value(ctypes.c_int, Action_t.ACTION_NONE.value)
        self.target_angle_0 = Value(ctypes.c_double, 0.0)
        self.target_angle_1 = Value(ctypes.c_double, 0.0)

        # try to open com port
        try:
            self._logger.debug('Open Odrive COM Port')
            self._ser = serial.Serial(port, baud, timeout=timeout)
            self._ser.readline()
            # dummy message to clear buffer
            self._ser.write(b'\n')
            # set limit
            for i in range(0, 2):
                self._ser.write(('w axis{}.motor.config.calibration_current {}\n'.format(i, calibration_current)).encode())
                self._ser.write(('w axis{}.motor.config.current_lim {}\n'.format(i, current_lim)).encode())
                self._ser.write(('w axis{}.controller.config.vel_limit {}\n'.format(i, speed_lim)).encode())
                # disable vel_limit_tolerance
                self._ser.write(('w axis{}.controller.config.vel_limit_tolerance {}\n'.format(i, 0)).encode())
        except:
            self._logger.error('Odrive COM Port Open Error')
            return

        # lpf
        self._target_angle_0_lpf = 0.0
        self._target_angle_1_lpf = 0.0
        self._lpf_gain = lpf_gain

        # start process
        self.is_run.value = True
        self._p = Process(target=self._process, args=())
        self._p.start()

    def close(self):
        self.is_run.value = False

    def _process(self):
        try:
            while self.is_run.value:
                if self.request_mode.value == Action_t.ACTION_CALIBRATION.value:
                    self._logger.info('ACTION_CALIBRATION')
                    for i in range(0, 2):
                        self._ser.write(('w axis{}.requested_state {}\n'.format(
                            i, AxisState_t.AXIS_STATE_FULL_CALIBRATION_SEQUENCE.value)).encode())
                    self.request_mode.value = Action_t.ACTION_NONE.value

                elif self.request_mode.value == Action_t.ACTION_CLOSEDLOOP.value:
                    self._logger.info('ACTION_CLOSEDLOOP')
                    for i in range(0, 2):
                        self._ser.write(('w axis{}.requested_state {}\n'.format(
                            i, AxisState_t.AXIS_STATE_CLOSED_LOOP_CONTROL.value)).encode())
                    self.request_mode.value = Action_t.ACTION_NONE.value

                elif self.request_mode.value == Action_t.ACTION_IDLE.value:
                    self._logger.info('ACTION_IDLE')
                    for i in range(0, 2):
                        self._ser.write(('w axis{}.requested_state {}\n'.format(
                            i, AxisState_t.AXIS_STATE_IDLE.value)).encode())
                    self.request_mode.value = Action_t.ACTION_NONE.value

                elif self.request_mode.value == Action_t.ACTION_VELOCITY_CTRL.value:
                    if abs(self.target_angle_0.value - self._target_angle_0_lpf) > 1.0:
                        self._target_angle_0_lpf = self.target_angle_0.value * self._lpf_gain \
                            + self._target_angle_0_lpf * (1 - self._lpf_gain)
                        target_step = self._target_angle_0_lpf / 360.0 * 8192.0 * 10.0
                        self._logger.info('ACTION_VELOCITY_CTRL_0 {}'.format(self.target_angle_0.value))
                        self._ser.write(('p {} {} {} {}\n'.format(
                            0, target_step, 0.0, 0.0)).encode())
                    if abs(self.target_angle_1.value - self._target_angle_1_lpf) > 1.0:
                        self._target_angle_1_lpf = self.target_angle_1.value * self._lpf_gain \
                            + self._target_angle_1_lpf * (1 - self._lpf_gain)
                        target_step = self._target_angle_1_lpf / 360.0 * 8192.0 * 10.0
                        self._logger.info('ACTION_VELOCITY_CTRL_1 {}'.format(self.target_angle_1.value))
                        self._ser.write(('p {} {} {} {}\n'.format(
                            1, target_step, 0.0, 0.0)).encode())
                    self.request_mode.value = Action_t.ACTION_NONE.value

                else:
                    self.request_mode.value = Action_t.ACTION_NONE.value

                time.sleep(0.01)
        except:
            self.is_run.value = False
        self._ser.close()
