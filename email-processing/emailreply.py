# Read environmental variables at import time
import os
import smtplib
import ssl
import logging
from email.message import EmailMessage
from email.utils import make_msgid, formatdate
import mimetypes

# SMTP variables - used in "send_reply" function
smtp_server: str = os.environ.get('SMTP_SERVER')
smtp_port: int = int(os.environ.get('SMTP_PORT', 587))
sender_email: str = os.environ.get('SMTP_SENDER_EMAIL')
sender_password: str = os.environ.get('SMTP_SENDER_PASSWORD')


logger = logging.root


def compose_reply(original_message: EmailMessage,
                  reply_text: str,
                  from_email: str,
                  to_email: str,
                  attach_filepath1: str | None,
                  attach_filepath2: str | None) -> EmailMessage:
     # Create a new EmailMessage object for the reply
    reply = EmailMessage()

    # Set the subject
    original_subject = original_message.get_header('Subject')
    if original_subject.lower().startswith('re:'):
        reply['Subject'] = original_subject
    else:
        reply['Subject'] = f"Re: {original_subject}"

    # Set the sender and recipient
    reply['From'] = from_email
    reply['To'] = to_email

    # Set other headers
    reply['In-Reply-To'] = original_message.get_message_id()
    reply['References'] = original_message.get_message_id()
    reply['Message-ID'] = make_msgid()
    reply['Date'] = formatdate(localtime=True)

    # Set the content
    # original_text = original_message.text
    reply_content = f"{reply_text}\n\nOn {original_message.get_date()}, {original_message.get_header('From')} wrote:\n\n{'original_text'}"
    reply.set_content(reply_content)

    # - attachment 1
    if attach_filepath1:
        # Open and read the file in binary mode
        with open(attach_filepath1, 'rb') as f:
            file_data = f.read()

        mime_type, _ = mimetypes.guess_type(attach_filepath1)
        if mime_type is None:
            mime_type = 'application/octet-stream'
        logger.debug("mime_type: " + mime_type)

        # Add the attachment to the message
        reply.add_attachment(file_data,
                             maintype=mime_type.split('/')[0],
                             subtype=mime_type.split('/')[1],
                             filename=os.path.basename(attach_filepath1))

    # - attachment 2
    if attach_filepath2:
        # Open and read the file in binary mode
        with open(attach_filepath2, 'rb') as f:
            file_data = f.read()

        mime_type, _ = mimetypes.guess_type(attach_filepath2)
        if mime_type is None:
            mime_type = 'application/octet-stream'
        logger.debug("mime_type: " + mime_type)

        # Add the attachment to the message
        reply.add_attachment(file_data,
                             maintype=mime_type.split('/')[0],
                             subtype=mime_type.split('/')[1],
                             filename=os.path.basename(attach_filepath2))
    return reply


def send_reply(original_message, reply_text, afile1, afile2):
    "Configured for Zohomail.eu"
    global smtp_server, smtp_port, sender_email, sender_password
    send_to = original_message.get_header('From')
    reply = compose_reply(original_message, reply_text,
                          from_email=sender_email,
                          to_email=send_to,
                          attach_filepath1=afile1,
                          attach_filepath2=afile2)
    try:
        server = smtplib.SMTP_SSL(smtp_server, smtp_port)
        server.ehlo()  # Can be omitted
        server.set_debuglevel(False)
        # server.starttls(context=context)  # Secure the connection
        server.ehlo()  # Can be omitted
        # server.esmtp_features['auth'] = 'LOGIN PLAIN'
        # print(sender_email, sender_password)
        server.login(sender_email, sender_password)

        # Send your email here
        receiver_email = send_to
        logger.debug(f"Sending email to {receiver_email} " +
                     str(server.sendmail(sender_email, receiver_email, reply.as_string())))
    except Exception as e:
        logger.error(f"Error during email sending with server {smtp_server}:{smtp_port}")
        raise e
    finally:
        server.quit()
