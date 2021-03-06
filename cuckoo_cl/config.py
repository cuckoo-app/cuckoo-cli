import os

attr = {
    'dev': {
        'region': 'us-east-2',
        'user_pool_id': 'us-east-2_aPXAs9pyz',
        'app_client_id': '6r05fcpba2apehoe4cgbifq90q',
        'identity_pool_id': 'us-east-2:983be965-2081-4cf4-b4d7-a45348cf5d07',
        'bucket_name': 'cuckoo-cl-app-api-dev-stdoutbucket-rr2n3gotouzy',
    },
    'prod': {
        'region': 'us-east-2',
        'user_pool_id': 'us-east-2_csyYyvFlI',
        'app_client_id': '6pe74n1oo9gevkllhrq7ec5vb8',
        'identity_pool_id': 'us-east-2:f1015767-c8e6-4140-82c2-c22febc2814f',
        'bucket_name': 'cuckoo-cl-app-api-prod-stdoutbucket-535m0jfb4jd',
    }
}

dummy_access_key = 'AKIAIOSFODNN7EXAMPLE'
dummy_secret_key = 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY'

cuckoo_dir = '%s/.cuckoo_cl' % os.path.expanduser('~')
user_config_fn = '%s/config' % cuckoo_dir
user_tokens_fn = '%s/tokens' % cuckoo_dir

stage = 'dev'
