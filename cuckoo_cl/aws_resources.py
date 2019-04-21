import boto3

try:
    from . import config
except:
    import config


def ses_client(aws_access_keys,
               region='us-east-1'):

    ses_client = boto3.client('ses',
                              region_name=region,
                              **aws_access_keys)
    return ses_client


def dynamodb_resource(aws_access_keys,
                      region='us-east-2'):
    return boto3.resource('dynamodb',
                          region_name=region,
                          **aws_access_keys)


def s3_resource(aws_access_keys,
                region='us-east-2'):
    return boto3.resource('s3',
                          region_name=region,
                          **aws_access_keys)


def idp_client(region='us-east-2'):
    idp_client = boto3.client('cognito-idp',
                              region_name=region,
                              aws_access_key_id=config.dummy_access_key,
                              aws_secret_access_key=config.dummy_secret_key)
    return idp_client


def identity_client(region='us-east-2'):
    identity_client = boto3.client('cognito-identity',
                                   region_name=region,
                                   aws_access_key_id=config.dummy_access_key,
                                   aws_secret_access_key=config.dummy_secret_key)
    return identity_client
