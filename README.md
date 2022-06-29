# IoT end-to-end AWS cloud example
This project aims to provide an demonstration of an end-to-end cloud stack for an IoT application.

The project includes the following:
- IoT core endpoint with rules for message routing
- IoT device firmware OTA process
- data storage using NoSQL (dynamodb) tables
- functions to check for sensors errors and notify customers via email if an error is detected
- cognito for user management
- AppSync graphql API for interfacing with web/mobile apps, including user authentication and IoT device pairing process


# Cloud services diagram:

![alt text](https://github.com/matthew018987/iot-end-to-end-cloud/blob/main/docs/IoT%20cloud%20service%20diagram.drawio.png?raw=true)

# Deployment Steps:
1. install AWS cli and AWS SAM cli
    https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html
    https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-install.html
2. log into your AWS account and create an access key that has privileges to deploy cloudformation
    https://docs.aws.amazon.com/powershell/latest/userguide/pstools-appendix-sign-up.html
3. store access key and secret key in aws cli credentials
    https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-configure.html
4. create a domain identity in AWS SES
    To create a domain identity refer to:
    https://docs.aws.amazon.com/ses/latest/dg/creating-identities.html
5. open project in your preferred IDE
6. deploy project to AWS using SAM deployment (Pycharm has a menu feature to do this for you)
    https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/sam-cli-command-reference-sam-deploy.html
