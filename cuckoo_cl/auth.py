import os
import sys
import json
import getpass
import warrant
from warrant.aws_srp import AWSSRP
from botocore.exceptions import ClientError
import aws_resources
import config


CUCKOO_DIR = config.cuckoo_dir
USER_CONFIG = config.user_config
STAGE = config.stage


def get_user_config():
    '''
    Get username config if file exists, else return None.
    '''
    try:
        with open(USER_CONFIG, 'r') as f:
            cuckoo_config = json.load(f)
            return cuckoo_config
    except FileNotFoundError:
        return None
    except KeyError:
        return None


def set_user_config(cuckoo_config):
    # cuckoo_config = {
    #     'username': username,
    #     'password': password,
    #     'machine': machine,
    # }
    with open(USER_CONFIG, 'w') as f:
        json.dump(cuckoo_config, f)


def check_login_credentials(username,
                            password,
                            user_pool_id=config.attr[STAGE]['user_pool_id'],
                            app_client_id=config.attr[STAGE]['app_client_id']):
    '''
    On success, returns tokens, otherwise return None.
    '''
    idp_client = aws_resources.idp_client()
    aws = AWSSRP(username=username,
                 password=password,
                 pool_id=user_pool_id,
                 client_id=app_client_id,
                 client=idp_client)
    try:
        user_tokens = aws.authenticate_user()
        return user_tokens
    except ClientError as e:
        if e.__class__.__name__ in ['NotAuthorizedException',
                                    'UserNotFoundException']:
            return None
        else:
            raise e


def get_aws_credentials(user_tokens,
                        region,
                        user_pool_id=config.attr[STAGE]['user_pool_id'],
                        identity_pool_id=config.attr[STAGE]['identity_pool_id']):
    """
    Get account keys from login credentials

    user_tokens come from check_login_credentials method
    """
    identity_client = aws_resources.identity_client()
    access_token = user_tokens['AuthenticationResult']['AccessToken']
    id_token = user_tokens['AuthenticationResult']['IdToken']
    refresh_token = user_tokens['AuthenticationResult']['RefreshToken']

    identity_id = identity_client.get_id(IdentityPoolId=identity_pool_id,
        Logins={'cognito-idp.%s.amazonaws.com/%s' % (region, user_pool_id): id_token})['IdentityId']
    credentials = identity_client.get_credentials_for_identity(IdentityId=identity_id,
        Logins={'cognito-idp.%s.amazonaws.com/%s' % (region, user_pool_id): id_token})

    access_key_id = credentials['Credentials']['AccessKeyId']
    secret_key = credentials['Credentials']['SecretKey']
    session_token = credentials['Credentials']['SessionToken']

    aws_access_keys = {
        'aws_access_key_id': access_key_id,
        'aws_secret_access_key': secret_key,
        'aws_session_token': session_token,
    }

    return {
        'access_token': access_token,
        'id_token': id_token,
        'refresh_token': refresh_token,
        'identity_id': identity_id,
        'aws_access_keys': aws_access_keys,
    }


def interactive_login(region=config.attr[STAGE]['region'],
                      user_pool_id=config.attr[STAGE]['user_pool_id'],
                      app_client_id=config.attr[STAGE]['app_client_id'],
                      identity_pool_id=config.attr[STAGE]['identity_pool_id'],
                      bucket_name=config.attr[STAGE]['bucket_name']):
    """Handle login from user input and returns account keys"""
    user_config = get_user_config()
    if user_config:
        # Config file already exists
        username = user_config['username']
        password = user_config['password']
        machine = user_config['machine']
        user_tokens = check_login_credentials(username,
                                              password,
                                              user_pool_id,
                                              app_client_id)
        if user_tokens:
            aws_credentials = get_aws_credentials(user_tokens,
                                                  region,
                                                  user_pool_id,
                                                  identity_pool_id)
            aws_credentials['username'] = username
            aws_credentials['machine'] = machine
            aws_credentials['bucket_name'] = bucket_name
            return aws_credentials
        else:
            # Login failed; either incorrect login or
            # incorrectly formatted config file
            pass

    # Bad credentials - prompt login!
    attempt = 0
    while attempt < 3:
        if attempt == 0:
            print('Please log in.')
        else:
            print('Incorrect credentials. Please try again.')
        username = input('Username: ')
        password = getpass.getpass('Password: ')
        user_tokens = check_login_credentials(username,
                                              password,
                                              user_pool_id,
                                              app_client_id)
        if user_tokens:
            machine = input('Enter a custom label for this machine: ')
            cuckoo_config = {
                'username': username,
                'password': password,
                'machine': machine,
            }
            set_user_config(cuckoo_config)
            aws_credentials = get_aws_credentials(user_tokens,
                                                  region,
                                                  user_pool_id,
                                                  identity_pool_id)
            aws_credentials['username'] = username
            aws_credentials['machine'] = machine
            aws_credentials['bucket_name'] = bucket_name
            print('Successful login!')
            return aws_credentials
        else:
            attempt += 1
    print('Login attempt failed 3 times. Please make sure you have the '
          + 'correct username and password!')
    sys.exit(1)
