#!/usr/bin/env python3
import os
import errno
import argparse

try:
    from . import config
    from . import auth
    from . import track
except:
    import config
    import auth
    import track


if __name__ == '__main__':
    stage = config.stage
    region = config.attr[stage]['region']
    user_pool_id = config.attr[stage]['user_pool_id']
    app_client_id = config.attr[stage]['app_client_id']
    identity_pool_id = config.attr[stage]['identity_pool_id']
    bucket_name = config.attr[stage]['bucket_name']

    try:
        os.makedirs(config.cuckoo_dir)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise

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
    # Send email at job completion
    parser.add_argument('-e',
                        '--email',
                        action='store_true',
                        help='Send email at job exit')
    # Save job info to database at checkpoints
    parser.add_argument('-d',
                        '--db',
                        action='store_true',
                        help='Save job info to database')
    # Verbose
    parser.add_argument('-v',
                        '--verbose',
                        action='store_true',
                        help='Print payloads and all info')

    args = parser.parse_args()

    if args.command and args.pid:
        parser.error('Please specify only one command or process to track.')
    elif args.command is None and args.pid is None:
        pass
    elif args.command:
        # Grab all aws credentials; either from file or interactively
        aws_credentials = auth.login()
        joined_command = ' '.join(args.command)
        print("Tracking command '%s'" % joined_command)
        track.track_new(joined_command,
                        aws_credentials,
                        store_stdout=False,
                        save_filename=None,
                        store_db=args.db,
                        send_email=args.email,
                        verbose=args.verbose)
    elif args.pid:
        # Grab all aws credentials; either from file or interactively
        aws_credentials = auth.login()
        print('Tracking existing process PID at: %s' % args.pid[0])
        track.track_existing(args.pid[0],
                             aws_credentials,
                             store_db=args.db,
                             send_email=args.email,
                             verbose=args.verbose)
    else:
        parser.error('Something went wrong!')
