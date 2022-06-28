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
"""Check incoming version messages to see if OTA is required, else send time message

Function is triggered by a message being received at AWS IoT core with endpoint:
    iot/version/1.0.0/<device unique ID>
The version is compared against the version number in the version.txt file located
in the S3 bucket with path stored in the function environmental variable.
If the version numbers do not match, send a message to the device instructing and OTA.
If the version numbers do match, device is up-to-date and send a time sync message.

 26/6/22: MN: initial version

"""
import boto3
import json
import os
from datetime import datetime
from boto3.dynamodb.conditions import Key, Attr


########################################################################################################
# CONSTANTS
########################################################################################################

# read constants from environmental variables
FIRMWARE_BUCKET = os.environ['FW_BUCKET']
USER_CONTROLLER_MAPPING_TABLE = os.environ['USER_MAPPING_TABLE']

# constants
FIRMWARE_FILE_NAME = 'your_firmware_file.bin'
FIRMWARE_TARGET_VERSION_FILE = 'version.txt'


########################################################################################################
# TIME FUNCTIONS
########################################################################################################


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


########################################################################################################
# SEND INSTRUCTIONS TO IOT DEVICE
########################################################################################################


def do_ota(device_id):
    """
    send a message to a specific IoT device to instruct an over the air firmware update

    Args:
        device_id: String containing the unique ID of the IoT device

    Returns:
        none
    """

    # create signed S3 URL, this contains credentials to access file from s3
    s3client = boto3.client('s3')
    signed_url = s3client.generate_presigned_url(
        'get_object',
        Params={
            'Bucket': FIRMWARE_BUCKET,
            'Key': FIRMWARE_FILE_NAME
        },
        ExpiresIn=300
    )
    print(signed_url)

    # send message to MQTT endpoint
    client = boto3.client('iot-data')

    # tell the device what the new O2 target percent is
    response = client.publish(
        topic='iot/commands/' + device_id,
        qos=1,
        payload=json.dumps({"ota": signed_url}) + '\n'
    )
    print('publish OTA request: ', response)

    return


def send_time_sync(device_id):
    """
    send a message to a specific IoT device to sync its time with the cloud

    Args:
        device_id: String containing the unique ID of the IoT device

    Returns:
        none
    """
    now_time = get_now()

    # send message to MQTT endpoint
    client = boto3.client('iot-data')

    # tell the device what the new O2 target percent is
    response = client.publish(
        topic='iot/commands/' + device_id,
        qos=1,
        payload=json.dumps({"time": now_time})
    )
    print(response)
    return

########################################################################################################
# DATABASE SUPPORT FUNCTIONS
########################################################################################################


def get_latest_version():
    """
    get the target firmware version number to compare against the IoT device reported version number

    Args: none

    Returns:
        string containing the target version number
    """
    s3 = boto3.resource('s3')
    obj = s3.Object(FIRMWARE_BUCKET, FIRMWARE_TARGET_VERSION_FILE)
    version = obj.get()['Body'].read().decode('ascii')
    version = version.strip('\n').strip('\r')
    return version


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


def set_device_version_message_by_cognito_id(cognito_id, device_id, version):
    """
    update the UserMapping table with the device's version number that it reported

    Args:
        device_id: String containing the unique ID of the IoT device
        cognitoID: String containing the unique ID of the user
        version: String containing the device's version number that it reported

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
            ":version": version
        }
    )
    print('set version message: ', response)
    return


########################################################################################################
# ENTRY POINT
########################################################################################################


def lambda_handler(event, context):
    """
    this function is triggered by version message from IoT Core
    sanity check version info is received:
        the version is compared against the target version
        if firmware version out of date:
            trigger ota
        else:
            send current time to device to sync device clock with cloud

    Args:
        event: {
            "version": "1.0.0"
        }
        context:
            unused

    Returns:
      none
    """
    print(event)
    # get device ID from incoming message
    topic = event['topic']
    # topic: iot/version/3FDA4A6722
    # device_id is 3FDA4A6722
    device_id = topic.split('/')[2]

    # check firmware version reported by IoT device
    if 'version' in event:
        current_version = event['version']

        # get latest version number from s3 version.txt
        latest_version = get_latest_version()
        print(latest_version)

        if current_version != latest_version:
            # if reported version number doesn't match the latest version number, issue ota command
            do_ota(device_id)
        else:
            # if the firmware is up to date, send time sync message to IoT device
            send_time_sync(device_id)

            # keep a record of the version of firmware the device reported
            user_mapping = get_user_mapping_by_device_id()
            if user_mapping:
                set_device_version_message_by_cognito_id(user_mapping['userID'], device_id, current_version)

    return
