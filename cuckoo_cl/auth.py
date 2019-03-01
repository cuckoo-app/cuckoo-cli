import os
import sys
import json
import getpass
import warrant
from warrant.aws_srp import AWSSRP
from botocore.exceptions import ClientError
import aws_resources
import config


def login_with_credentials(username,
                           password,
                           region,
                           user_pool_id,
                           app_client_id,
                           identity_pool_id):
    """Get account keys from login credentials"""
    idp_client = aws_resources.idp_client()
    identity_client = aws_resources.identity_client()

    aws = AWSSRP(username=username,
                 password=password,
                 pool_id=user_pool_id,
                 client_id=app_client_id,
                 client=idp_client)
    tokens = aws.authenticate_user()
    access_token = tokens['AuthenticationResult']['AccessToken']
    id_token = tokens['AuthenticationResult']['IdToken']
    refresh_token = tokens['AuthenticationResult']['RefreshToken']

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


# def login(username,
#           password,
#           region=config.attr['dev']['region'],
#           user_pool_id=config.attr[stage]['user_pool_id'],
#           app_client_id=config.attr[stage]['app_client_id'],
#           identity_pool_id=config.attr[stage]['identity_pool_id']):
#     try:
#         login_with_credentials(username,
#                                password,
#                                region,
#                                user_pool_id,
#                                app_client_id,
#                                identity_pool_id)
#     except


def dynamic_login(region=config.attr['dev']['region'],
                  user_pool_id=config.attr[stage]['user_pool_id'],
                  app_client_id=config.attr[stage]['app_client_id'],
                  identity_pool_id=config.attr[stage]['identity_pool_id']):
    """Handle login from user input and returns account keys"""
    cuckoo_dir = '%s/.cuckoo' % os.path.expanduser('~')
    try:
        try:
            with open('%s/config.json' % cuckoo_dir, 'r') as f:
                cuckoo_config = json.load(f)
                username = cuckoo_config['username']
                password = cuckoo_config['password']
                machine = cuckoo_config['machine']
            user_keys = login_with_credentials(username,
                                               password,
                                               region,
                                               user_pool_id,
                                               app_client_id,
                                               identity_pool_id)
        except FileNotFoundError:
            print('No configuration file found.')
            username = input('Username: ')
            password = getpass.getpass('Password: ')
            machine = input('Enter a custom label for this machine: ')
            cuckoo_config = {
                'username': username,
                'password': password,
                'machine': machine,
            }
            with open('%s/config.json' % cuckoo_dir, 'w') as f:
                json.dump(cuckoo_config, f)
            user_keys = login_with_credentials(username,
                                               password,
                                               region,
                                               user_pool_id,
                                               app_client_id,
                                               identity_pool_id)
    except ClientError as e:
        if 'NotAuthorizedException' == e.__class__.__name__:
            attempts = 3
            while attempts > 0:
                print('Incorrect username or password. Please try again.')
                with open('%s/config.json' % cuckoo_dir, 'r') as f:
                    cuckoo_config = json.load(f)
                cuckoo_config['username'] = username = input('Username: ')
                cuckoo_config['password'] = password = getpass.getpass('Password: ')
                with open('%s/config.json' % cuckoo_dir, 'w') as f:
                    json.dump(cuckoo_config, f)
                try:
                    user_keys = login_with_credentials(username,
                                                       password,
                                                       region,
                                                       user_pool_id,
                                                       app_client_id,
                                                       identity_pool_id)
                    break
                except ClientError as e:
                    if 'NotAuthorizedException' == e.__class__.__name__:
                        attempts -= 1
                    else:
                        raise e
            print('Incorrect username or password. Please make sure you are using the correct login credentials, or reset your password.')
            sys.exit(0)
        else:
            raise e
    finally:
        user_keys['username'] = username
        user_keys['machine'] = machine

    return user_keys
