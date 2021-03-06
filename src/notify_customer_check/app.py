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
"""Check user-device mapping table for new errors

Function is triggered by a modification to the user-device mapping table.
If a new error is detected, a message is sent to a queue which triggers an email notification

 26/6/22: MN: initial version
 3/7/22:  MN: code tidy up, fixes to notification handling due to UserMappingTable key changes

"""

import os
import json
from boto3.dynamodb.conditions import Key
import boto3


##############################################################################################
# CONSTANTS
##############################################################################################


# read constants from environmental variables
USER_CONTROLLER_MAPPING_TABLE = os.environ['USER_MAPPING_TABLE']
EMAILER_QUEUE_URL = os.environ['EMAILER_QUEUE_URL']


##############################################################################################
# DATABASE SUPPORT FUNCTIONS
##############################################################################################


def get_cognito_id_from_device_id(device_id):
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
        KeyConditionExpression=Key('deviceID').eq(device_id),
    )

    cognito_id = ''
    if len(response['Items']) > 0:
        cognito_id = response['Items'][0]['userID']

    return cognito_id


##############################################################################################
# QUEUE SUPPORT FUNCTIONS
##############################################################################################


def send_email_notification(cognito_id):
    """
    this function sends a message to a queue, which triggers a function to email a
    notification to a user

    Args:
        cognito_id: String containing the unique ID of the user account we wish to notify

    Returns:
        none
    """
    sqs_message = {
        'cognitoID': cognito_id,
    }
    sqs = boto3.client('sqs')
    response = sqs.send_message(
        QueueUrl=EMAILER_QUEUE_URL,
        MessageBody=json.dumps(sqs_message)
    )
    print('Error message added to emailer queue: ', response)


##############################################################################################
# ENTRY POINT
##############################################################################################


def lambda_handler(event, context):
    """
    This function is triggered by changes to the user-device mapping table
    Check the data that has been updated in the table and compare it what was replaced.
    If there is a new error, send a message to the customer notification queue.

    Args:
        event: dict
        {
            'Records': [
                {
                    'eventID': '4611b81c6556234570b2345aff585917',
                    'eventName': 'MODIFY',
                    'eventVersion': '1.1',
                    'eventSource': 'aws:dynamodb',
                    'awsRegion': 'us-east-1',
                    'dynamodb': {
                        'ApproximateCreationDateTime': 1656853180.0,
                        'Keys': {
                            'userID': {
                                'S': 'ed8d2345-2345-4e5c-a236-2345e82345'
                            }
                        },
                        'NewImage': {
                            'error_msg': {
                                'S': 'An error occurred with a sensor'
                            },
                            'deviceID': {
                                'S': 'AAAAAAAAAAAA'
                            },
                            'userID': {
                                'S': 'ed8d2345-2345-4e5c-a236-2345e82345'
                            },
                            'timestamp': {
                                'N': '1656407708'
                            }
                        },
                        'OldImage': {
                            'deviceID': {
                                'S': 'AAAAAAAAAAAA'
                            },
                            'userID': {
                                'S': 'ed8d2345-2345-4e5c-a236-2345e82345'
                            },
                            'timestamp': {
                                'N': '1656407708'
                            }
                        },
                        'SequenceNumber': '2517660000000000000000000',
                        'SizeBytes': 236,
                        'StreamViewType': 'NEW_AND_OLD_IMAGES'
                    },
                    'eventSourceARN': 'arn:aws:dynamodb:us-east-1:xxxxxxxxxxxx:table/UserController.....
                }
            ]
        }


        context: unused

    Returns:
      none
    """
    print(event)
    # only pay attention to a record that has been modified
    # records that are CREATED are new entries due to the creating of a mapping between
    # a user & a device
    if 'MODIFY' == event['Records'][0]['eventName']:
        dbentry = event['Records'][0]['dynamodb']
        if 'error_msg' in dbentry['NewImage']:
            # notify the customer if there is an error_msg and it's different to the
            # previous recorded error
            old_msg = ''
            if 'error_msg' in dbentry['OldImage']:
                old_msg = dbentry['OldImage']['error_msg']
            new_msg = ''
            if 'error_msg' in dbentry['NewImage']:
                new_msg = dbentry['NewImage']['error_msg']

            if len(new_msg) > 0:
                if old_msg != new_msg:
                    print('sensor error:', dbentry['NewImage'])
                    cognito_id = dbentry['NewImage']['userID']['S']
                    send_email_notification(cognito_id)
