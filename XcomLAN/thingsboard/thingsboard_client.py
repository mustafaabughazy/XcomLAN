# !/usr/bin/env python
# -*- coding: utf-8 -*-
#
"""
This file contains definition/implementation of a ThingsBoardClient Class
that Manages dealing with / pushing data to ThingsBoard server.
"""
# TODO: enhance this file documentation
# TODO: enhance exceptions handling

import csv
import logging
import re

from datetime import datetime
from time import sleep
from time import time

from tb_device_mqtt import TBPublishInfo
from tb_gateway_mqtt import TBGatewayMqttClient


# -------------------------------------------------------------------------------------------------------------------- #
# ---------------------------------------------  ThingsBoardClient Class  -------------------------------------------- #
# -------------------------------------------------------------------------------------------------------------------- #
class ThingsBoardClient(TBGatewayMqttClient):
    """
    ThingsBoardClient Class
    """

    def __init__(self, host, token=None, port=1883,
                 gateway=None, quality_of_service=1,
                 node_profile='Studer Xcom-LAN Node'):
        super(ThingsBoardClient, self).__init__(host, token, port, gateway, quality_of_service)
        self._node_profile = node_profile
        self.log = logging.getLogger(__name__ + ":" + self._node_profile)
        # Initialize and Connect The Gateway Device
        self.connect()

    def __del__(self):
        self.disconnect()

    @property
    def node_profile(self):
        """
        Returns the Node Profile.

        :return:
        """
        return self._node_profile

    # telemetry === UserInfo
    def send_node_telemetry(self, node_name, telemetry_values):
        log = logging.getLogger(__name__ + ":" + self.node_profile + ":" + node_name)

        # Connect The Device
        # device_type: will be used only when creating not existing device
        self.gw_connect_device(node_name, device_type=self.node_profile)

        # Sending Telemetry Data (UserInfo) to TB Device
        telemetry = {  # Contains JSON/Dict
            'ts': int(round(time() * 1000)),
            'values': telemetry_values
        }
        result = self.gw_send_telemetry(node_name, telemetry)
        result_status = result.get() == TBPublishInfo.TB_ERR_SUCCESS
        log.info('Send to Node: ' + node_name + ' Telemetry Content: ' + str(telemetry) +
                 ' Sending Telemetry Result Status: ' + str(result_status))

        self.gw_disconnect_device(node_name)

    # attribute === Parameter
    def send_node_attributes(self, node_name, attributes_values):
        log = logging.getLogger(__name__ + ":" + self.node_profile + ":" + node_name)

        # Connect The Device
        # device_type: will be used only when creating not existing device
        self.gw_connect_device(node_name, device_type=self.node_profile)

        # Sending Attributes Data (Parameter) to TB Device
        attributes = attributes_values  # Contains JSON/Dict
        result = self.gw_send_attributes(node_name, attributes)
        result_status = result.get() == TBPublishInfo.TB_ERR_SUCCESS
        log.info('Send to Node: ' + node_name + ' Attributes Content: ' + str(attributes) +
                 ' Sending Attributes Result Status: ' + str(result_status))

        self.gw_disconnect_device(node_name)

    @classmethod
    def _generate_dict_header_for_csv_log_file(cls, csv_log_file_path):
        # supports only nodes with single Xtender device
        first_row, second_row, third_row = list(csv.reader(open(csv_log_file_path, 'r')))[0:3]
        header = ['ts'] + [''] * (len(first_row) - 2)

        for idx in range(1, len(first_row) - 1):
            if first_row[idx] == '':
                first_row[idx] = first_row[idx - 1]

            if first_row[idx].startswith('XT') or first_row[idx].startswith('DEV XT'):
                header[idx] = 'XT' + '1' + second_row[idx]
            elif first_row[idx].startswith('VS') or first_row[idx].startswith('DEV VS'):
                header[idx] = 'VS' + third_row[idx] + second_row[idx]
            elif first_row[idx].startswith('VT') or first_row[idx].startswith('DEV VT'):
                header[idx] = 'VT' + third_row[idx] + second_row[idx]
            elif first_row[idx].startswith('BSP'):
                header[idx] = 'BSP' + second_row[idx]
            elif first_row[idx].startswith('DEV'):
                header[idx] = 'DEV' + second_row[idx]
            elif first_row[idx] == 'Solar power (ALL) [kW]':
                header[idx] = 'SolarPowerALL' + second_row[idx]
            else:
                header[idx] = re.sub('[^0-9a-zA-Z]+', '', first_row[idx]) + third_row[idx] + second_row[idx]
        return header

    @classmethod
    def _parse_value_from_csv_log_file(cls, value):
        if value.isdigit():
            return int(value)
        elif len(value) > 1 and value[0] in ('-', '+') and value[1:].isdigit():
            return int(value)
        elif value.replace('.', '', 1).isdigit():
            return float(value)
        elif len(value) > 1 and value[0] in ('-', '+') and value.replace('.', '', 1)[1:].isdigit():
            return float(value)
        else:
            return value

    def push_csv_input_to_tb(self, node_name, csv_log_file_path, feed_as_realtime=False):
        log = logging.getLogger(__name__ + ":" + self.node_profile + ":" + node_name)

        # Connect The Device
        # device_type: will be used only when creating not existing device
        self.gw_connect_device(node_name, device_type=self.node_profile)

        telemetry = {}
        attributes = {}

        # Define Fields Names
        fieldnames = self._generate_dict_header_for_csv_log_file(csv_log_file_path)

        # Creating A CSV DictReader object
        csv_dict_reader = list(csv.DictReader(open(csv_log_file_path, 'r'), fieldnames=fieldnames))

        # Read (CSVDictReader), Skip First 3 Rows. Focus on Telemetries
        for index, row in enumerate(csv_dict_reader[3:1443]):
            try:
                logging.info('CSV ROW Number: ' + str(index + 4))
                date_time_str = row['ts']
                date_time_obj = datetime.strptime(date_time_str, '%d.%m.%Y %H:%M')
                timestamp = date_time_obj.timestamp()
                telemetry['ts'] = int(timestamp * 1000) if not feed_as_realtime else int(round(time() * 1000))
                telemetry['values'] = {i: self._parse_value_from_csv_log_file(row[i]) for i in fieldnames[1:]}

                result = self.gw_send_telemetry(node_name, telemetry)
                result_status = result.get() == TBPublishInfo.TB_ERR_SUCCESS
                log.info('Node: ' + node_name + ' Telemetry Content: ' + str(telemetry))
                log.info('Node: ' + node_name + ' File: ' + csv_log_file_path +
                         ' Send Telemetry Result Status: ' + str(result_status))
            except Exception as e:
                logging.exception(e)

        # Read (CSVDictReader), Skip First 1443 Rows. Focus on Attributes
        for index, row in enumerate(csv_dict_reader[1443:]):
            if re.match(r'[PI][0-9]+', row[fieldnames[0]]):
                attributes[row[fieldnames[0]]] = self._parse_value_from_csv_log_file(row[fieldnames[1]])

        result = self.gw_send_attributes(node_name, attributes)
        result_status = result.get() == TBPublishInfo.TB_ERR_SUCCESS
        log.info('Node: ' + node_name + ' File: ' + csv_log_file_path + ' Attributes Content: ' + str(attributes))
        log.info('Node: ' + node_name + ' Send Attributes Result Status: ' + str(result_status))

        # Disconnect The Device
        self.gw_disconnect_device(node_name)

        if feed_as_realtime:
            sleep(60)

# -------------------------------------------------------------------------------------------------------------------- #
# -----------------------------------------  End of ThingsBoardClient Class  ----------------------------------------- #
# -------------------------------------------------------------------------------------------------------------------- #
