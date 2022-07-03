# MIT License
#
# Copyright (c) 2022 matthew018987
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

# -*- coding: utf-8 -*-
"""Create entries in a two-week summary table

The two-week table can be used to populate a two-week history chart, the chart will contain
24 * 14 == 336 data points.
The two-week table will auto delete any data points more than 2 week old.

Function is triggered by a message being received at AWS IoT core with endpoint:
    iot/data/1.0.0/<device unique ID>
Check if this message occurs in a new hour compared to the previous message.
If it is in a new hour, get the last hours worth of data, summarise it and store
the summary in the two-week table.

 26/6/22: MN: initial version
 3/7/22:  MN: code tidy up

"""
import os
from datetime import datetime
from decimal import Decimal
import boto3
from boto3.dynamodb.conditions import Key
import constants


##############################################################################################
# CONSTANTS
##############################################################################################

# read constants from environmental variables
SENSOR_DATA_TABLE = os.environ['SENSOR_DATA_TABLE']
TWO_WEEK_TABLE = os.environ['TWO_WEEK_TABLE']


##############################################################################################
# TIME FUNCTIONS
##############################################################################################


def get_now():
    """
    get current time in seconds since epoch

    Args:
        none

    Returns:
        none
    """
    epoch = datetime.utcfromtimestamp(0)
    epoch_secs = int((datetime.now() - epoch).total_seconds())
    return epoch_secs


def round_time_down_to_hour():
    """
    get current time in seconds since epoch rounded down to the hour

    Args:
        none

    returns:
        none
    """
    current_datetime = datetime.fromtimestamp(get_now())
    adjusted_datetime = current_datetime.replace(
                            hour=current_datetime.hour,
                            minute=0,
                            second=0,
                            microsecond=0
                        )
    epoch = datetime.utcfromtimestamp(0)
    epoch_secs_by_hour = int((adjusted_datetime - epoch).total_seconds())
    return epoch_secs_by_hour


##############################################################################################
# DATABASE SUPPORT FUNCTIONS
##############################################################################################


def get_previous_sensor_data(device_id, timestamp):
    """
    get the last recorded data point for a given device unique ID

    Args:
        device_id: String containing the unique ID of the IoT device
        timestamp: IoT rule writes directly to the database so we need to ensure we ignore
          messages with the timetamp of the one we are currently processing

    Returns:
        dictionary: last recorded set of data points
    """
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(SENSOR_DATA_TABLE)
    response = table.query(
        KeyConditionExpression=Key('deviceID').eq(device_id) & Key('timestamp').lt(timestamp),
        Limit=1,
        ScanIndexForward=False
    )

    prev_data = {}
    if response['Count'] > 0:
        prev_data = response['Items'][0]
    return prev_data


def get_last_hour_of_sensor_data(device_id, start_time, end_time):
    """
    get the last recorded data point for a given device unique ID

    Args:
        device_id: String containing the unique ID of the IoT device

    Returns:
        dictionary: last recorded set of data points
    """
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(SENSOR_DATA_TABLE)
    response = table.query(
        KeyConditionExpression=
            Key('deviceID').eq(device_id) &
            Key('timestamp').between(start_time, end_time),
        Limit=60,
        ScanIndexForward=False
    )

    prev_data = {}
    if response['Count'] > 0:
        prev_data = response['Items']
    return prev_data


def write_two_week_data(device_id, summary):
    """
    update two week table with a new entry

    Args:
        device_id: string:
            the unique ID of the IoT device
        timestamp: int
            used as sort key in the table, this is the timestamp of the end of the hour
        summary: dict
            summarised data points to write to the database
            {
                'temp': 24.5,
                'hum': 65
            }

    Returns:
        none
    """
    timestamp = round_time_down_to_hour()
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(TWO_WEEK_TABLE)
    # the expiry timestamp is used by dynamodb to delete entries when the current time
    # passes the expiry timestamp value
    expire_timestamp = timestamp + (14 * 24 * 60 * 60)

    response = table.put_item(
        Item = {
            'deviceID': device_id,
            'timestamp':  timestamp,
            'temp': Decimal(summary['temp']).quantize(Decimal('0.01')),
            'hum': int(round(summary['hum'])),
            'expiretimestamp': expire_timestamp
        }
    )
    print('two week entry write: ', response)


##############################################################################################
# PROCESS DATA FUNCTIONS
##############################################################################################


def calculate_average_from_set(data_set):
    """
    Calculate the average temperature & average humidity from an array of values.
    Ignore any that are out of expected range.

    Args:
        data_set: array of dict
        dict: {
            'temp': 25.4,
            'hum': 54
        }

    Return:
        dict containing average temp & humidity
        {
            'temp': 36.4,
            'hum': 56
        } 
    """
    summary = {}
    sum_temp = 0
    sum_hum = 0
    valid_count = 0
    for point in data_set:
        # check if data point is inside limits (not erroneous)
        print(point)
        inside_limits = \
            int(point['temp']) in range(
                constants.LOWER_TEMP_LIMIT,
                constants.UPPER_TEMP_LIMIT
            ) and int(point['hum']) in range(
                constants.LOWER_HUM_LIMIT,
                constants.UPPER_HUM_LIMIT
            )
        if inside_limits:
            # only use points that exist within the expected range
            sum_temp = sum_temp + point['temp']
            sum_hum = sum_hum + point['hum']
            valid_count = valid_count + 1
        else:
            print('point outside limits:', point, constants.LOWER_TEMP_LIMIT, constants.UPPER_TEMP_LIMIT, constants.LOWER_HUM_LIMIT, constants.UPPER_HUM_LIMIT)
    # calculate the average
    if valid_count > 0:
        av_temp = sum_temp / valid_count
        av_hum = sum_hum / valid_count
        summary = {
            'temp': av_temp,
            'hum': av_hum
        }
        print('summary:', summary)
    else:
        print('no valid data points found, summary empty')
    return summary


def two_week_update_check(device_id, event):
    """
    check if two week table entry is required
        get the last recorded data point for this device unique ID
        if the new message occurred in the next hour:
            get all data for the last hour for this device unique ID
            create a summary and store the summary in the two-week table

    Args:
        device_id: String containing the unique ID of the IoT device
        event: {
            'hum': 60,
            'temp': 25.4,
            'timestamp': 1656050903,
            'recvtimestamp': 1656062452486,
            'topic': 'iot/data/0.3.0/AAAAAAAAAAAA'
        }

    Returns:
        none
    """
    last_data_point = get_previous_sensor_data(device_id, event['timestamp'])
    print('last data point:', last_data_point)
    if last_data_point:
        # get the hour from the timestamp when these messages occurred
        hour_when_current_data_occurred = event['timestamp'] // 3600
        hour_when_previous_data_occurred = last_data_point['timestamp'] // 3600
        print('hour_when_current_data_occurred: ', hour_when_current_data_occurred)
        print('hour_when_previous_data_occurred: ', hour_when_previous_data_occurred)
        if hour_when_current_data_occurred > hour_when_previous_data_occurred:
            # we've passed the hour, get the last hour's data for this device
            # summarise the data and store in the two-week table
            prev_hour_start = hour_when_previous_data_occurred * 3600
            prev_hour_end = prev_hour_start + 3600
            hour_of_data = get_last_hour_of_sensor_data(device_id, prev_hour_start, prev_hour_end)
            print('hour_of_data: ', hour_of_data)

            # create a summary
            summary = calculate_average_from_set(hour_of_data)

            # store summary in 2 week table
            if summary:
                write_two_week_data(device_id, summary)


##############################################################################################
# ENTRY POINT
##############################################################################################


def lambda_handler(event, context):
    """
    this function is triggered by incoming sensor data from IoT Core and used to process
    streaming data

    if sensor data is received:
        update 2 weekly table if we've just passed the hour
        check for error in sensor data
    if version info is received:
        the version is compared against the target version
        if firmware version out of date:
            trigger ota
        else:
            send current time to device to sync device clock with cloud

    Args:
        event: dict
        the incoming message varies depending on what the device is reporting
        {
            'hum': 60,
            'temp': 25.4,
            'timestamp': 1656050903,
            'recvtimestamp': 1656062452486,
            'topic': 'iot/data/0.3.0/AAAAAAAAAAAA'
        }
        context: unused

    Returns:
        none
    """
    print(event)
    # get device ID from incoming message
    topic = event['topic']
    # topic: iot/data/1.0.0/3FDA4A6722
    # device_id is 3FDA4A6722
    device_id = topic.split('/')[3]

    # sanity check for correct input parameters
    if ('temp' in event) and ('hum' in event):
        # check whether we need to update the 2 week table
        two_week_update_check(device_id, event)
