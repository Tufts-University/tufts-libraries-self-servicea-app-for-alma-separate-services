"""RQ entry point for bulk PO-line creation and completion delivery."""
import os
import shutil
import smtplib
import subprocess
from email.message import EmailMessage
from contextlib import nullcontext
from .bulk_create_pol import BulkCreatePOL

def _send_email(to_addr, subject, body, attachment_bytes=None, attachment_name='results.zip'):
    message = EmailMessage()
    message['From'] = os.getenv('SMTP_FROM', 'noreply-library@tufts.edu')
    message['To'], message['Subject'] = to_addr, subject
    message.set_content(body)
    if attachment_bytes is not None:
        message.add_attachment(attachment_bytes, maintype='application', subtype='zip', filename=attachment_name)
    sendmail = shutil.which('sendmail')
    if sendmail:
        subprocess.run([sendmail, '-t', '-oi'], input=message.as_bytes(), capture_output=True, check=True, timeout=30)
    else:
        with smtplib.SMTP(os.getenv('SMTP_HOST', 'localhost'), int(os.getenv('SMTP_PORT', '25')), timeout=30) as smtp:
            smtp.send_message(message)

RESULTS_DIR = os.getenv('BULK_CREATE_POL_RESULTS_DIR', '/tmp/bulk_create_pol_results')
PUBLIC_BASE_URL = os.getenv('PUBLIC_BASE_URL', 'https://tufts-libraries-alma-self-service-app.library.tufts.edu').rstrip('/')


def run_bulk_create_pol_job(job_id, input_path, email, email_as_attachment=False,
                            environment='sandbox', ingest_method='spreadsheet',
                            form_data=None, set_id=None, filename='input.csv'):
    os.makedirs(RESULTS_DIR, exist_ok=True)
    try:
        with (open(input_path, 'rb') if input_path else nullcontext(None)) as stream:
            processor = BulkCreatePOL(stream, environment=environment, form_data=form_data,
                                      filename=filename, set_id=set_id)
            result = processor.process_zip_bytes(ingest_method)
        out_name = f'{job_id}__bulk_create_pol.zip'
        out_path = os.path.join(RESULTS_DIR, out_name)
        with open(out_path, 'wb') as output:
            output.write(result)
    except Exception:
        _send_email(email, 'Bulk Create POL: job failed',
                    f'Job {job_id} failed. Contact the administrator for details. Check Alma before resubmitting if any orders were created.')
        raise
    finally:
        if input_path and os.path.isfile(input_path):
            os.remove(input_path)
    # Delivery failure must not be mistaken for an order-creation failure.
    body = (f'Job {job_id} completed in {environment}.\nCreated: {processor.successCount}\n'
            f'Errors/skipped: {processor.errorCount}\n\n'
            f'Download: {PUBLIC_BASE_URL}/bulk_create_pol/results/{out_name}\n')
    _send_email(email, 'Bulk Create POL: job complete', body,
                attachment_bytes=result if email_as_attachment else None,
                attachment_name='bulk_create_pol.zip')
    return {'result_file': out_name, 'created': processor.successCount, 'errors': processor.errorCount}
