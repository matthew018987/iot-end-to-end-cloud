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
"""Send an email to a customer using their cognito ID to notify them of a sensor problem

Function is triggered by a message being sent to the emailer queue.
Get the user contact details from the cognito service by usign the provided user ID.
Send a templated email using the SES service

 26/6/22: MN: initial version
 29/6/22: MN: fixed reference our of scope response variable
 3/7/22:  MN: code tidy up, fixes to notification handling due to UserMappingTable key changes

"""

import os
import json
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import email_templates
import botocore
import boto3


##############################################################################################
# CONSTANTS
##############################################################################################


# read constants from environmental variables
COGNITO_USER_POOL_ID = os.environ['COGNITO_USER_POOL_ID']
EMAILER_QUEUE_URL = os.environ['EMAILER_QUEUE_URL']


##############################################################################################
# DATABASE SUPPORT FUNCTIONS
##############################################################################################


def get_user_details_by_cognito_id(cognito_id):
    """
    get the customer name and email address from the cognito service by searching for the cognito_id

    Args:
        cognito_id: String containing the unique ID of the user account

    Returns:
        dictionary with users registered given name string and user email address string
    """
    user_details = {
        'given_name': '',
        'email_address': ''
    }

    # get username from cognito_id
    client = boto3.client('cognito-idp')
    cognito_filter = 'sub="' + cognito_id + '"'
    response = client.list_users(UserPoolId=COGNITO_USER_POOL_ID, Limit=1, Filter=cognito_filter)
    if len(response['Users']) > 0:
        for attribute in response['Users'][0]['Attributes']:
            if attribute['Name'] == 'email':
                user_details['email_address'] = attribute['Value']
                print('email address:', user_details['email_address'])
            if attribute['Name'] == 'custom:firstname':
                user_details['given_name'] = attribute['Value']
                print('given name:', user_details['given_name'])
    else:
        print('cognito_id not found: ', cognito_id)

    return user_details


##############################################################################################
# EMAIL FUNCTIONS
##############################################################################################


def send_email(user_details):
    """
    construct and send email to customer using the ses service

    Args:
        user_details: Dict:
            given_name: string: name of customer being emailed
            email_address: string: address of customer being emailed

    Returns:
        none
    """
    given_name = user_details['given_name']
    email_address = user_details['email_address']

    print('notify:', given_name, 'at address:', email_address)

    if (given_name != '') and (email_address != ''):
        client = boto3.client('ses')

        destination = email_address

        body_html = email_templates.sensor_error['body']
        subject = email_templates.sensor_error['subject']
        sender = email_templates.sensor_error['sender']

        if body_html != '':
            # replace the token ### with the users given name
            body_html = body_html.replace('###', given_name)

            charset = "utf-8"
            msg_body = MIMEMultipart('alternative')

            # Encode the text and HTML content and set the character encoding. This step is
            # necessary if you're sending a message with characters outside the ASCII range.
            html_part = MIMEText(body_html.encode(charset), 'html', charset)

            # Add the text and HTML parts to the child container.
            msg_body.attach(html_part)

            msg = MIMEMultipart('mixed')
            # Add subject, from and to lines.
            msg['Subject'] = subject
            msg['From'] = sender
            msg['To'] = destination

            msg.attach(msg_body)

            response = client.send_raw_email(
                Destinations=[destination],
                RawMessage={
                    'Data': msg.as_string(),
                },
                Source=sender,
            )
            print('email send status: ', response)


##############################################################################################
# QUEUE MANAGEMENT FUNCTIONS
##############################################################################################


def delete_sqs_message(event):
    """
    remove message from queue since it has been processed

    Args:
        event: dict:
            receiptHandle: string: address of message we want to delete from the queue

    Returns:
        none
    """
    if 'receiptHandle' in event:
        sqs = boto3.client('sqs')
        try:
            response = sqs.delete_message(
                QueueUrl=EMAILER_QUEUE_URL,
                ReceiptHandle=event['receiptHandle']
            )
            print('remove notification queue entry: ', response)
        except botocore.exceptions.ClientError as err:
            print('Error Message: {}'.format(err.response['Error']['Message']))


##############################################################################################
# ENTRY POINT
##############################################################################################


def lambda_handler(event, context):
    """
    This function is triggered by a the emailer queue
    A message from the queue contains the user ID of the customer we need to notify of a problem
    Construct an email from the template and user details.
    Send the email using the AWS SES service

    Args:
        event: dict
            event data structure contains required parameter named cognito_id
        event: {
            'Records': [
                {
                    'messageId': '1efb833b-43fd-4c9e-963b-ac335754d490',
                    'receiptHandle': 'AQEBl/EorTlj03vFSVDFVDFVHzU0/N3+uEviVFBnDFVDF.....
                    'body': "{
                        'cognitoID':'12345678'
                    }",
                    'attributes': {
                        'ApproximateReceiveCount': '1',
                        'SentTimestamp': '1620458414343',
                        'SenderId': 'AIDASDCACRGSDCJSDC3RE6',
                        'ApproximateFirstReceiveTimestamp': '1620458414386'
                    },
                    'messageAttributes': {},
                    'md5OfBody': '75937062a550dbe8abe1f7e7104f64bc',
                    'eventSource': 'aws:sqs',
                    'eventSourceARN': 'arn:aws:sqs:us-east-1:xxxxxxxx:devicestack1-.....
                    'awsRegion': 'us-east-1'
                }
            ]
        }
        context:
            unused

    Returns:
        non
    """

    for record in event['Records']:
        message = json.loads(record['body'].strip('\n').strip(' '))
        cognito_id = message['cognitoID']
        user_details = get_user_details_by_cognito_id(cognito_id)
        send_email(user_details)
        delete_sqs_message(record)
