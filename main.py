#!/usr/bin/python3
# -*- coding: utf-8 -*-

import datetime
import json
import logging
import time
import yaml
from device.gamepad_mp import GamePadMp
from device.odrive_mp import OdriveMp
from device.serial_mp import SerilaMp, Action_t


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
        filename = dir + current_datetime.strftime('20%y%m%d_%H%M_') + name + filetype
        fh = logging.FileHandler(filename, )
        fh.setFormatter(formatter)
        logger.addHandler(fh)

    return logger


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
        gamepad_mp = GamePadMp(logger_main)
        odrive_mp = OdriveMp(
            logger_main, port=cfg['odrive_port'], baud=cfg['odrive_baud'],
            speed_lim=cfg['odrive_speed_lim'], current_lim=cfg['odrive_current_lim'])
        serial_mp = SerilaMp(logger_main, port=cfg['nucleo_port'], baud=cfg['nucleo_baud'])
        logger_main.debug('GamePad: {}'.format(gamepad_mp.is_run.value))
        logger_main.debug('Serial: {}'.format(serial_mp.is_run.value))

        # z1
        console_time_z1 = time.time()
        gp_data_z1 = False

        # main loop
        while gamepad_mp.is_run.value and serial_mp.is_run.value and odrive_mp.is_run.value:
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
            elif gamepad_mp.is_up(gp_data, gp_data_z1, '0x13c'):
                serial_mp.request_mode.value = Action_t.ACTION_CALIBRATION.value
                odrive_mp.request_mode.value = Action_t.ACTION_CALIBRATION.value
            elif gamepad_mp.is_up(gp_data, gp_data_z1, '0x13b'):
                serial_mp.request_mode.value = Action_t.ACTION_CLOSEDLOOP.value
                odrive_mp.request_mode.value = Action_t.ACTION_CLOSEDLOOP.value
            elif gamepad_mp.is_up(gp_data, gp_data_z1, '0x13a'):
                serial_mp.request_mode.value = Action_t.ACTION_IDLE.value
                odrive_mp.request_mode.value = Action_t.ACTION_IDLE.value
            elif gp_data['gp_code'] == '0x3':
                serial_mp.request_mode.value = Action_t.ACTION_VELOCITY_CTRL.value
                serial_mp.target_angle.value = float(gp_data['gp_value']) / 32768.0 * 360.0 * 3.0
            elif gp_data['gp_code'] == '0x5':
                odrive_mp.request_mode.value = Action_t.ACTION_VELOCITY_CTRL.value
                odrive_mp.target_angle_0.value = float(gp_data['gp_value']) / 256.0 * 360.0
            elif gp_data['gp_code'] == '0x2':
                odrive_mp.request_mode.value = Action_t.ACTION_VELOCITY_CTRL.value
                odrive_mp.target_angle_1.value = float(gp_data['gp_value']) / 256.0 * 360.0

            # debug console
            if time_now - console_time_z1 > cfg['debug_console_interval']:
                console_time_z1 = time_now
                logger_main.debug(json.dumps(gp_data))
                logger_main.debug(json.dumps(rx_data))
                logger_main.debug('\n')

            # store z1
            gp_data_z1 = gp_data

            time.sleep(0.01)
    except KeyboardInterrupt:
        pass

    gamepad_mp.close()
    odrive_mp.close()
    serial_mp.close()
    logger_main.debug('End Program')


if __name__ == '__main__':
    main()
