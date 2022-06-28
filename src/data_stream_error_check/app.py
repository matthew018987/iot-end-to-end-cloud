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
"""Check incoming data messages for errors, log error if it occurs

Function is triggered by a message being received at AWS IoT core with endpoint:
    iot/data/1.0.0/<device unique ID>
If an error is detected, a message is recorded in the device-user mapping table
in order for a user to be notified of a problem

 26/6/22: MN: initial version

"""
import boto3
import os
from boto3.dynamodb.conditions import Key, Attr
from constants import *


########################################################################################################
# CONSTANTS
########################################################################################################

# read constants from environmental variables
USER_CONTROLLER_MAPPING_TABLE = os.environ['USER_MAPPING_TABLE']

########################################################################################################
# DATABASE SUPPORT FUNCTIONS
########################################################################################################


def get_user_mapping_by_device_id(device_id):
    """
    get the user device mapping for a given device_id

    Args:
        device_id: String containing the unique ID of the IoT device

    Returns:
        entry from mapping table
    """
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(USER_CONTROLLER_MAPPING_TABLE)
    response = table.query(
        # Add the name of the index you want to use in your query.
        IndexName="DeviceIndex",
        KeyConditionExpression=Key('deviceID').eq(device_id)
    )
    mapping = {}
    if response['Count'] > 0:
        mapping = response['Items'][0]
    return mapping


def set_error_message_by_cognito_id(cognito_id, device_id, msg):
    """
    update an error flag in the user mapping table for a user and device_id

    Args:
        device_id: String containing the unique ID of the IoT device
        cognitoID: String containing the unique ID of the user
        msg: String containing the error message, blank if no error

    Returns:
        none
    """
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(USER_CONTROLLER_MAPPING_TABLE)
    response = table.update_item(
        Key={
            'userID': cognito_id,
            'deviceID': device_id
        },
        UpdateExpression="set error_msg = :error_msg",
        ExpressionAttributeValues={
            ":error_msg": msg
        }
    )
    print('set error message: ', response)
    return


########################################################################################################
# PROCESS DATA FUNCTIONS
########################################################################################################


def check_for_errors(device_id, event):
    """
    this function applies a series of checks to know if the data is good or bad

    Args:
        device_id: String containing the unique ID of the IoT device
        event: {
            temp: 22.2,
            hum: 67
        }

    Returns:
        bool: true if error detected
        String: error message
            note: if bool is false error message will be an empty string
    """
    # check environmental sensors are within defined boundaries
    inside_limits = \
        (event['temp'] in range(LOWER_TEMP_LIMIT, UPPER_TEMP_LIMIT)) and \
        (event['hum'] in range(LOWER_HUM_LIMIT, UPPER_HUM_LIMIT))

    all_correct = inside_limits
    msg = ''
    if not inside_limits:
        msg = 'An error occurred with a sensor'
        print(device_id, msg)

    if not all_correct:
        print(event)

    error = not all_correct
    return error, msg


########################################################################################################
# ENTRY POINT
########################################################################################################


def lambda_handler(event, context):
    """
    this function is triggered by incoming sensor data from IoT Core and used to process streaming data
    sanity check sensor data is received:
        update 2 weekly table if we've just passed the hour
        check for error in sensor data

    Args:
        sensor data event: {
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
        # check for erroneous data and events where we need to notify the customer of a problem
        error_detected, error_msg = check_for_errors(device_id, event)
        user_mapping = get_user_mapping_by_device_id(device_id)
        if error_detected:
            # if error is detected check for a mapping to a user account
            if user_mapping:
                # a user account has been found, set error flag in database
                print('IoT device error detected, device_id:', device_id, 'cognitoID:', user_mapping['userID'])
                # set error message in UserControllerMappingTable
                set_error_message_by_cognito_id(user_mapping['userID'], user_mapping['device_id'], error_msg)
            else:
                # no user account mapping found, log event
                print('controller error detected, device_id:', device_id, 'no user has onboarded this device')
        else:
            # if no error found, clear any existing error flags
            if user_mapping:
                if 'error_msg' in user_mapping:
                    if user_mapping['error_msg'] != '':
                        set_error_message_by_cognito_id(user_mapping['userID'], user_mapping['deviceID'], '')

    return
