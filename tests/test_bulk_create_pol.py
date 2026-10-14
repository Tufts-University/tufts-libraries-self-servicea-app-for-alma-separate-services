"""Mocked Alma integration tests: no live orders or email."""
import io
import json
import zipfile
from unittest.mock import Mock
import pytest
from services.bulk_create_pol.bulk_create_pol import BulkCreatePOL

@pytest.fixture
def proc(monkeypatch):
    monkeypatch.setenv('sandbox_acq_api_key', 'test-secret')
    return BulkCreatePOL(form_data=dict(library='TISCH', location='STACKS', vendor='VENDOR', vendor_account='ACCOUNT', fund='FUND'))

def test_spreadsheet_payload_and_continue(proc, monkeypatch):
    proc.file_stream = io.BytesIO(b'MMS ID,Title,Price,Interested User,2nd Reporting Code\n991234567890123456,A title,12.34,user1,extra\n991234567890123457,B title,15,,\n991234567890123458,C title,NaN,,\n')
    responses = [Mock(ok=True, status_code=200, text='{"number":"POL-1"}', json=lambda: {'number': 'POL-1'}), Mock(ok=False, status_code=400, text='Bad fund')]
    post = Mock(side_effect=responses)
    monkeypatch.setattr('services.bulk_create_pol.bulk_create_pol.requests.post', post)
    data = proc.process_zip_bytes()
    assert len(proc.items) == 3
    assert proc.successCount == 1 and proc.errorCount == 2 and post.call_count == 2
    payload = post.call_args_list[0].kwargs['json']
    assert payload['resource_metadata']['mms_id']['value'] == '991234567890123456'
    assert payload['price']['sum'] == '12.34'
    assert payload['fund_distributions']['fund_distribution'][0]['amount'] == payload['price']
    assert payload['locations']['location'][0]['copies']['copy'][0]['item_policy']['value'] == 'Default'
    assert payload['interested_users']['interested_user'][0]['primary_id'] == 'user1'
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        results = json.loads(archive.read('requests_and_responses.json'))
        assert results[1]['http_status'] == 400
        assert results[2]['http_status'] is None
        assert 'test-secret' not in archive.read('requests_and_responses.json').decode()

def test_xlsx_keeps_text_ids(proc):
    from openpyxl import Workbook
    book = Workbook()
    book.active.append(['MMS ID', 'Price', 'Library'])
    book.active.append(['991234567890123456', 2.5, 'MUSIC'])
    proc.file_stream = io.BytesIO()
    book.save(proc.file_stream)
    proc.filename = 'orders.xlsx'
    assert proc.ingest_spreadsheet()[0]['mms_id'] == '991234567890123456'
    assert proc.items[0]['library'] == 'MUSIC'

def test_managed_set_pagination_and_price_placeholder(proc, monkeypatch):
    proc.set_id = '123'
    proc._get = Mock(side_effect=[{'content': {'value': 'BIB'}}, {'member': [{'id': '991', 'description': 'A'}], 'total_record_count': 2}, {'member': [{'id': '992', 'description': 'B'}], 'total_record_count': 2}])
    post = Mock()
    monkeypatch.setattr('services.bulk_create_pol.bulk_create_pol.requests.post', post)
    proc.process_zip_bytes('managed_set')
    assert len(proc.items) == 2 and proc.errorCount == 2
    assert proc._get.call_args.kwargs['offset'] == 1
    assert 'pricing is not implemented' in proc.results[0]['error']
    post.assert_not_called()

def test_ui_and_queue(monkeypatch, tmp_path):
    from services.bulk_create_pol.service_app import create_app
    from services.bulk_create_pol import routes
    monkeypatch.setattr(routes, 'UPLOAD_FOLDER', str(tmp_path))
    queue = Mock()
    monkeypatch.setattr(routes, 'get_queue', lambda: queue)
    client = create_app().test_client()
    with client.session_transaction() as session:
        session['user'] = 'tester'
    assert b'Per-item prices' in client.get('/bulk_create_pol/').data
    result = client.post('/bulk_create_pol/upload', data=dict(ingest_method='managed_set', set_id='123', email='test@example.com', environment='prod', library='TISCH', location='STACKS', vendor='V', vendor_account='A', fund='F'))
    assert result.status_code == 200
    kwargs = queue.enqueue.call_args.kwargs['kwargs']
    assert kwargs['environment'] == 'prod' and kwargs['input_path'] is None
    assert kwargs['form_data']['fund'] == 'F'

def test_job_saves_and_delivers(proc, monkeypatch, tmp_path):
    from services.bulk_create_pol import tasks
    monkeypatch.setattr(tasks, 'RESULTS_DIR', str(tmp_path))
    monkeypatch.setattr(tasks, 'BulkCreatePOL', lambda *a, **kw: proc)
    proc.process_zip_bytes = Mock(return_value=b'result')
    mail = Mock()
    monkeypatch.setattr(tasks, '_send_email', mail)
    path = tmp_path / 'input.csv'
    path.write_bytes(b'input')
    result = tasks.run_bulk_create_pol_job('123', str(path), 'user@example.com', True)
    assert not path.exists()
    assert (tmp_path / result['result_file']).read_bytes() == b'result'
    assert mail.call_args.kwargs['attachment_bytes'] == b'result'
