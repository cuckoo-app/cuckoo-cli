#!/usr/bin/env python3
import argparse

import config
import auth
import track


if __name__ == '__main__':
    stage = 'dev'
    region = config.attr[stage]['region']
    user_pool_id = config.attr[stage]['user_pool_id']
    app_client_id = config.attr[stage]['app_client_id']
    identity_pool_id = config.attr[stage]['identity_pool_id']
    bucket_name = config.attr[stage]['bucket_name']

    # Log in if user config isn't saved
    aws_credentials = auth.interactive_login(
        region=region,
        user_pool_id=user_pool_id,
        app_client_id=app_client_id,
        identity_pool_id=identity_pool_id,
        bucket_name=bucket_name,
    )

    import pprint
    pprint.pprint(aws_credentials)

    parser = argparse.ArgumentParser(
        description='Track completion of your jobs!'
    )
    parser.add_argument(
        '-c',
        '--command',
        nargs='+',
        help='Full command to track',
    )
    # May potentially support multiple processes
    parser.add_argument(
        '-p',
        '--pid',
        nargs=1,
        type=int,
        help='PID of existing job to track',
    )

    args = parser.parse_args()

    if args.command and args.pid:
        parser.error('Please specify only one command or process to track.')
    elif args.command is None and args.pid is None:
        pass
    elif args.command:
        joined_command = ' '.join(args.command)
        print(joined_command)
        track.track_new(joined_command,
                        aws_credentials,
                        store_stdout=False,
                        save_filename=None,
                        store_db=False,
                        send_email=True)
    elif args.pid:
        print(args.pid)
        track.track_existing(args.pid[0], aws_credentials)
    else:
        parser.error('Something went wrong!')
