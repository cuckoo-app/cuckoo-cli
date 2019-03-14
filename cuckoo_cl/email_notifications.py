import sys
import boto3
from botocore.client import ClientError


# Placeholder until we get official cuckoo email
SENDER = 'Cuckoo CL <bbrzycki@berkeley.edu>'

# The character encoding for the email.
CHARSET = "UTF-8"

# CONFIGURATION_SET = "ConfigSet"


def send_email(ses_client,
               subject,
               body_text,
               body_html,
               recipient='bbrzycki@berkeley.edu'):
    # Try to send the email.
    try:
        # Provide the contents of the email.
        response = ses_client.send_email(
            Destination={
                'ToAddresses': [
                    recipient,
                ],
            },
            Message={
                'Body': {
                    'Html': {
                        'Charset': CHARSET,
                        'Data': body_html,
                    },
                    'Text': {
                        'Charset': CHARSET,
                        'Data': body_text,
                    },
                },
                'Subject': {
                    'Charset': CHARSET,
                    'Data': subject,
                },
            },
            Source=SENDER,
            # If you are not using a configuration set, comment or delete the
            # following line
            # ConfigurationSetName=CONFIGURATION_SET,
        )
    # Display an error if something goes wrong.
    except ClientError as e:
        print(e.response['Error']['Message'])
    else:
        print("Email sent! Message ID:"),
        print(response['MessageId'])


def send_completion_email(ses_client,
                          payload,
                          recipient='bbrzycki@berkeley.edu'):
    command = payload['command']
    job_status = payload['jobStatus']
    machine = payload['machine']
    date_modified = payload['dateModified']
    runtime = payload['runtime']

    if job_status == 'success':
        subject = 'Your job finished successfully!'

        summary = "Your job '%s' completed at %s (UTC) on machine '%s' with no errors." % (command, date_modified, machine)
        body = "The job's total runtime was %s (hh:mm:ss)." % (runtime)

        html_summary = "Your job <strong>%s</strong> completed at <strong>%s</strong> (UTC) on machine <strong>%s</strong> with no errors." % (command, date_modified, machine)
        html_body = "The job's total runtime was <strong>%s</strong> (hh:mm:ss)." % (runtime)
    elif job_status == 'error':
        subject = 'Your job exited with an error'

        summary = "Your job '%s' exited at %s (UTC) on machine '%s' with an error." % (command, date_modified, machine)
        body = "The job's total runtime was %s (hh:mm:ss)." % (runtime)

        html_summary = "Your job <strong>%s</strong> exited at <strong>%s</strong> (UTC) on machine <strong>%s</strong> with an error." % (command, date_modified, machine)
        html_body = "The job's total runtime was <strong>%s</strong> (hh:mm:ss)." % (runtime)
    elif job_status == 'finished':
        subject = 'Your job has finished!'

        summary = "Your job '%s' finished at %s (UTC) on machine '%s'." % (command, date_modified, machine)
        body = "The job's total runtime was %s (hh:mm:ss)." % (runtime)

        html_summary = "Your job <strong>%s</strong> finished at <strong>%s</strong> (UTC) on machine <strong>%s</strong>." % (command, date_modified, machine)
        html_body = "The job's total runtime was <strong>%s</strong> (hh:mm:ss)." % (runtime)
    else:
        sys.exit('Invalid status: %s' % job_status)

    # The email body for recipients with non-HTML email clients.
    body_text = (
        "%s\r\n"
        "%s\r\n"
        "Cuckoo CL"
    ) % (summary, body)

    # The HTML body of the email.
    body_html = """
        <html>
        <head></head>
        <body>
          <p>%s</p>
          <p>%s</p>
          <p>Cuckoo CL</p>
        </body>
        </html>
                """ % (html_summary, html_body)

    send_email(ses_client,
               subject,
               body_text,
               body_html,
               recipient)
