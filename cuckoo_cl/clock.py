import uuid

try:
    from . import aws_resources
    from . import datetime_utils
    from . import email_notifications
    from . import auth
    from . import config
except:
    import aws_resources
    import datetime_utils
    import email_notifications
    import auth
    import config


class Clock(object):
    """Clock class for tracking within scripts and notebooks"""

    stage = config.stage
    region = config.attr[stage]['region']
    user_pool_id = config.attr[stage]['user_pool_id']
    app_client_id = config.attr[stage]['app_client_id']
    identity_pool_id = config.attr[stage]['identity_pool_id']
    bucket_name = config.attr[stage]['bucket_name']

    aws_credentials = auth.login(
        region=region,
        user_pool_id=user_pool_id,
        app_client_id=app_client_id,
        identity_pool_id=identity_pool_id,
        bucket_name=bucket_name,
    )
    aws_access_keys = aws_credentials['aws_access_keys']

    def __init__(self):
        self.id = str(uuid.uuid4())
        self.start_date = datetime_utils.get_start_date()
        self.date_modified, self.runtime, self.runtime_s = datetime_utils.get_current_times(self.start_date)

    def __enter__(self):
        return self

    def __exit__(self, type, value, trace_back):
        return True

    def update_now(self):
        self.date_modified, self.runtime, self.runtime_s = datetime_utils.get_current_times(self.start_date)

    def send_email(self, subject, text):
        self.update_now()
        if self.runtime_s < 60:
            print('Job exited in less than a minute -- no need to track!')
        else:
            ses_client = aws_resources.ses_client(
                self.aws_access_keys
            )

            body_text = (
                "%s\r\n"
                "Cuckoo CL"
            ) % (text)

            # The HTML body of the email.
            body_html = """
                <html>
                <head></head>
                <body>
                  <p>%s</p>
                  <p>Cuckoo CL</p>
                </body>
                </html>
                        """ % (text)

            email_notifications.send_email(ses_client,
                                           subject,
                                           body_text,
                                           body_html,
                                           recipient='bbrzycki@berkeley.edu')
