import os
import sys
import json
import getpass
import warrant
from botocore.exceptions import ClientError, NoCredentialsError
from jose.exceptions import JWTError
import aws_resources
import config


CUCKOO_DIR = config.cuckoo_dir
USER_CONFIG_FN = config.user_config_fn
USER_TOKENS_FN = config.user_tokens_fn
STAGE = config.stage


def get_user_config():
    '''
    Get username config if file exists, else return None.
    '''
    try:
        with open(USER_CONFIG_FN, 'r') as f:
            cuckoo_config = json.load(f)
            return cuckoo_config
    except FileNotFoundError:
        return None
    except KeyError:
        return None


def set_user_config(cuckoo_config):
    # cuckoo_config = {
    #     'username': username,
    #     'machine': machine,
    # }
    with open(USER_CONFIG_FN, 'w') as f:
        json.dump(cuckoo_config, f)


def get_json(filename):
    '''
    Get stored json if file exists, else return None.
    '''
    try:
        with open(filename, 'r') as f:
            json_dict = json.load(f)
            return json_dict
    except FileNotFoundError:
        return None
    except KeyError:
        return None


def save_json(json_dict, filename):
    with open(filename, 'w') as f:
        json.dump(json_dict, f)


def get_user_tokens(cognito_session):
    '''
    On success, returns tokens.
    '''
    cognito_session.check_token()
    return {
        'id_token': cognito_session.id_token,
        'refresh_token': cognito_session.refresh_token,
        'access_token': cognito_session.access_token,
    }


# def get_user_tokens(username,
#                     password,
#                     user_pool_id=config.attr[STAGE]['user_pool_id'],
#                     app_client_id=config.attr[STAGE]['app_client_id']):
#     '''
#     On success, returns tokens, otherwise return None.
#     '''
#     idp_client = aws_resources.idp_client()
#     aws = AWSSRP(username=username,
#                  password=password,
#                  pool_id=user_pool_id,
#                  client_id=app_client_id,
#                  client=idp_client)
#     try:
#         user_tokens = aws.authenticate_user()
#         return user_tokens
#     except ClientError as e:
#         if e.__class__.__name__ in ['NotAuthorizedException',
#                                     'UserNotFoundException']:
#             return None
#         else:
#             raise e


def get_all_aws_credentials(user_tokens,
                            region,
                            user_pool_id=config.attr[STAGE]['user_pool_id'],
                            identity_pool_id=config.attr[STAGE]['identity_pool_id']):
    """
    Get account keys from login credentials

    user_tokens come from get_user_tokens method
    """
    identity_client = aws_resources.identity_client()
    # access_token = user_tokens['AuthenticationResult']['AccessToken']
    # id_token = user_tokens['AuthenticationResult']['IdToken']
    # refresh_token = user_tokens['AuthenticationResult']['RefreshToken']
    # id_token = user_tokens['id_token']
    # refresh_token = user_tokens['refresh_token']
    # access_token = user_tokens['access_token']

    identity_id = identity_client.get_id(IdentityPoolId=identity_pool_id,
        Logins={'cognito-idp.%s.amazonaws.com/%s' % (region, user_pool_id): user_tokens['id_token']})['IdentityId']
    credentials = identity_client.get_credentials_for_identity(IdentityId=identity_id,
        Logins={'cognito-idp.%s.amazonaws.com/%s' % (region, user_pool_id): user_tokens['id_token']})

    access_key_id = credentials['Credentials']['AccessKeyId']
    secret_key = credentials['Credentials']['SecretKey']
    session_token = credentials['Credentials']['SessionToken']

    aws_access_keys = {
        'aws_access_key_id': access_key_id,
        'aws_secret_access_key': secret_key,
        'aws_session_token': session_token,
    }

    return {
        'user_tokens': user_tokens,
        'identity_id': identity_id,
        'aws_access_keys': aws_access_keys,
    }


def login(region=config.attr[STAGE]['region'],
          user_pool_id=config.attr[STAGE]['user_pool_id'],
          app_client_id=config.attr[STAGE]['app_client_id'],
          identity_pool_id=config.attr[STAGE]['identity_pool_id'],
          bucket_name=config.attr[STAGE]['bucket_name']):
    """Handle login from user input and returns account keys"""
    user_config = get_json(USER_CONFIG_FN)
    user_tokens = get_json(USER_TOKENS_FN)
    if user_tokens:
        try:
            username = user_config['username']
            machine = user_config['machine']

            cognito_session = warrant.Cognito(user_pool_id,
                                              app_client_id,
                                              user_pool_region=region,
                                              username=username,
                                              id_token=user_tokens['id_token'],
                                              refresh_token=user_tokens['refresh_token'],
                                              access_token=user_tokens['access_token'])
            user_tokens = get_user_tokens(cognito_session)
            aws_credentials = get_all_aws_credentials(user_tokens,
                                                      region,
                                                      user_pool_id,
                                                      identity_pool_id)
            aws_credentials['username'] = username
            aws_credentials['machine'] = machine
            aws_credentials['bucket_name'] = bucket_name
            return aws_credentials
        except ClientError as e:
            # Login failed; either incorrect tokens or
            # incorrectly formatted token file
            if e.__class__.__name__ in ['NotAuthorizedException',
                                        'UserNotFoundException']:
                pass
            else:
                raise e
        except NoCredentialsError:
            # Credentials not located or not accessible
            pass
        except (KeyError, TypeError):
            # If username or machine are not defined in config
            pass
        except JWTError:
            # If tokens are corrupted, have user log in again
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
        try:
            cognito_session = warrant.Cognito(user_pool_id,
                                              app_client_id,
                                              user_pool_region=region,
                                              username=username,
                                              access_key=config.dummy_access_key,
                                              secret_key=config.dummy_secret_key)
            cognito_session.authenticate(password=password)
            user_tokens = get_user_tokens(cognito_session)
            save_json(user_tokens, USER_TOKENS_FN)

            if user_config:
                machine = input('Enter a custom label for this machine [%s]: ' % user_config['machine'])
                if machine == '':
                    machine = user_config['machine']
            else:
                machine = input('Enter a custom label for this machine: ')
                while machine == '':
                    machine = input('Please enter a valid machine label: ')
            cuckoo_config = {
                'username': username,
                'machine': machine,
            }
            save_json(cuckoo_config, USER_CONFIG_FN)
            aws_credentials = get_all_aws_credentials(user_tokens,
                                                      region,
                                                      user_pool_id,
                                                      identity_pool_id)
            aws_credentials['username'] = username
            aws_credentials['machine'] = machine
            aws_credentials['bucket_name'] = bucket_name
            print('Successful login!')
            return aws_credentials

        except ClientError as e:
            # Bad login
            if e.__class__.__name__ in ['NotAuthorizedException',
                                        'UserNotFoundException']:
                attempt += 1
            else:
                raise e
    print('Login attempt failed 3 times. Please make sure you have the '
          + 'correct username and password!')
    sys.exit(1)
