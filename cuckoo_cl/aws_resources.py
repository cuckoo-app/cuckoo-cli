import boto3


def ses_client(aws_access_keys,
               region="us-east-1"):

    ses_client = boto3.client('ses',
                              region_name=region,
                              **aws_access_keys)
    return ses_client


def dynamodb_resource(aws_access_keys,
                      region="us-east-2"):
    return boto3.resource('dynamodb',
                          region_name=region,
                          **aws_access_keys)


def s3_resource(aws_access_keys,
                region="us-east-2"):
    return boto3.resource('s3',
                          region_name=region,
                          **aws_access_keys)
