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
"""Add a cognito user to the project user group

Function is triggered by a new user being added to AWS cognito.
Cognito does not automatically add users to a group, a lambda fucntion is required to be triggered on user create.
Code adds the user to group

 26/6/22: MN: initial version

"""
import boto3


# add user to cognito user group
def lambda_handler(event, context):
    """
    This function is triggered by cognito when a user registers themselves using the app.
    The

    Args:
        event: {
            'version': '1',
            'region': 'ap-southeast-1',
            'userPoolId': 'ap-us-east-1_w1SlOiN61',
            'userName': 'bdcae07c5-23a3-2342-91cf-a23471f234',
            'callerContext': {
                'awsSdkVersion': 'aws-sdk-unknown-unknown',
                'clientId': None
            },
            'triggerSource': 'PostConfirmation_ConfirmSignUp',
            'request': {
                'userAttributes': {
                    'sub': 'bdcae07c5-23a3-2342-91cf-a23471f234',
                    'cognito:email_alias': '<user email>@gmail.com',
                    'cognito:user_status': 'CONFIRMED',
                    'email_verified': 'false',
                    'email': '<user email>@gmail.com'
                }
            },
            'response': {}
        }
        context: unused

    Returns:
      event: input event must be returned for cognito to know this was executed successfully
      "Amazon Cognito expects the return value of the function to have the same format as the input."
      # https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-events.html
    """
    client = boto3.client('cognito-idp')
    response = client.admin_add_user_to_group(
        GroupName='UserGroup',
        UserPoolId=event['userPoolId'],
        Username=event['userName']
    )
    print('add user to group: ', response)

    return event