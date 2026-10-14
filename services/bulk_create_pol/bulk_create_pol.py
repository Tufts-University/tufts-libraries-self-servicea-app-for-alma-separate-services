"""Bulk physical PO-line creation using Alma's JSON API."""
import csv
import io
import json
import os
import re
import zipfile
from decimal import Decimal, InvalidOperation
from urllib.parse import quote
import requests
from dotenv import load_dotenv
load_dotenv()

class BulkCreatePOL:
    DEFAULTS = dict(material_type='BOOK', item_policy='Default', reporting_code='print', currency='USD', type='PRINTED_BOOK_OT')
    ALIASES = {'1st_reporting_code': 'reporting_code', '2nd_reporting_code': 'secondary_reporting_code', 'mmsid': 'mms_id', 'vendor_account_code': 'vendor_account'}

    def __init__(self, file_stream=None, environment='sandbox', form_data=None, filename='input.csv', set_id=None):
        self.file_stream, self.filename, self.set_id = file_stream, filename, set_id
        self.environment = (environment or 'sandbox').lower()
        if self.environment not in ('sandbox', 'prod'):
            raise ValueError('environment must be sandbox or prod')
        self.api_key = os.getenv(f'{self.environment}_acq_api_key') or os.getenv(f'{self.environment}_bib_api_key')
        if not self.api_key:
            raise RuntimeError(f'No Alma API key configured for {self.environment}')
        bib_url = os.getenv('bib_url', 'https://api-na.hosted.exlibrisgroup.com/almaws/v1/bibs/')
        self.base_url = (os.getenv(f'{self.environment}_alma_api_url') or bib_url.split('/bibs')[0]).rstrip('/')
        self.headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
        self.invariants = self.ingest_invariants_table(form_data or {})
        self.items, self.results = [], []
        self.successCount = self.errorCount = 0

    @classmethod
    def normalize(cls, values):
        result = {}
        for key, value in values.items():
            key = re.sub(r'[^a-z0-9]+', '_', str(key).strip().lower()).strip('_')
            if value is not None and str(value).strip():
                result[cls.ALIASES.get(key, key)] = str(value).strip()
        return result

    def ingest_invariants_table(self, form_data_json):
        values = json.loads(form_data_json) if isinstance(form_data_json, str) else dict(form_data_json)
        return {**self.DEFAULTS, **self.normalize(values)}

    def ingest_spreadsheet(self):
        """Store per-item JSON-compatible dictionaries in self.items."""
        self.file_stream.seek(0)
        if self.filename.lower().endswith('.xlsx'):
            from openpyxl import load_workbook
            workbook = load_workbook(self.file_stream, read_only=True, data_only=True)
            try:
                rows = iter(workbook.active.values)
                headers = next(rows, ())
                records = [dict(zip(headers, row)) for row in rows if any(v is not None for v in row)]
            finally:
                workbook.close()
        else:
            content = self.file_stream.read()
            if isinstance(content, bytes):
                content = content.decode('utf-8-sig')
            records = list(csv.DictReader(io.StringIO(content)))
        self.items = [{**self.invariants, **self.normalize(row)} for row in records]
        if not self.items:
            raise ValueError('Spreadsheet contains no items')
        return self.items

    ingest_csv = ingest_spreadsheet

    def _get(self, path, **params):
        response = requests.get(f'{self.base_url}/{path}', headers=self.headers, params={'apikey': self.api_key, **params}, timeout=30)
        if not response.ok:
            raise RuntimeError(f'Alma GET HTTP {response.status_code}: ' + response.text.replace(self.api_key, '[REDACTED]'))
        return response.json()

    def retrieve_managed_set(self):
        if not self.set_id:
            raise ValueError('Managed set ID is required')
        path = 'conf/sets/' + quote(str(self.set_id), safe='')
        content = self._get(path).get('content', {})
        content = content.get('value') if isinstance(content, dict) else content
        if content not in ('BIB', 'PHYSICAL_TITLES'):
            raise ValueError('Select a bibliographic or physical title set, not an item or holdings set')
        self.items = []
        offset = 0
        while True:
            page = self._get(path + '/members', limit=100, offset=offset)
            members = page.get('member', [])
            if not members:
                break
            for member in members:
                self.items.append({**self.invariants, 'mms_id': str(member['id']), 'title': member.get('description', ''), 'price': ''})
            offset += len(members)
            if offset >= int(page.get('total_record_count', offset + 1)):
                break
        return self.items

    def build_pol(self, item):
        """Map one copy and one fund to rest_po_line.xsd POST fields."""
        for field in ('mms_id', 'library', 'location', 'vendor', 'vendor_account', 'fund', 'price'):
            if not item.get(field):
                raise ValueError('Missing ' + field + ('; managed-set per-item pricing is not implemented' if field == 'price' and self.set_id else ''))
        if not item['mms_id'].isdigit():
            raise ValueError('MMS ID must contain digits only; format spreadsheet IDs as text')
        try:
            price = Decimal(item['price'])
        except InvalidOperation:
            raise ValueError('Price must be a non-negative number')
        if not price.is_finite() or price < 0:
            raise ValueError('Price must be a finite non-negative number')
        amount = {'sum': str(price), 'currency': {'value': item['currency']}}
        material = 'BOOK' if item['material_type'].lower() == 'book' else item['material_type']
        payload = {
            'owner': {'value': item['library']}, 'type': {'value': item['type']},
            'vendor': {'value': item['vendor']}, 'vendor_account': item['vendor_account'],
            'material_type': {'value': material}, 'resource_metadata': {'mms_id': {'value': item['mms_id']}},
            'price': amount, 'fund_distributions': {'fund_distribution': [{'fund_code': {'value': item['fund']}, 'amount': dict(amount)}]},
            'reporting_code': item['reporting_code'],
            'locations': {'location': [{'quantity': 1, 'library': {'value': item['library']}, 'shelving_location': item['location'],
                'copies': {'copy': [{'item_policy': {'value': item['item_policy']}}]}}]}}
        if item.get('title'):
            payload['resource_metadata']['title'] = item['title']
        if item.get('secondary_reporting_code'):
            payload['secondary_reporting_code'] = item['secondary_reporting_code']
        if item.get('interested_user'):
            payload['interested_users'] = {'interested_user': [{'primary_id': item['interested_user']}]}
        return payload

    def create_pol(self, item=None):
        """POST each item once and continue after individual failures; never retry POSTs."""
        for values in ([item] if item is not None else self.items):
            result = dict(mms_id=values.get('mms_id', ''), title=values.get('title', ''), price=values.get('price', ''), http_status=None, pol_number='', error='')
            try:
                if values.get('mms_id') and not result['title']:
                    result['title'] = self._get('bibs/' + quote(values['mms_id'], safe='')).get('title', '')
                    values = {**values, 'title': result['title']}
                payload = self.build_pol(values)
                result['request'] = payload
                response = requests.post(self.base_url + '/acq/po-lines', json=payload, headers=self.headers, params={'apikey': self.api_key}, timeout=60)
                result['http_status'] = response.status_code
                result['response'] = response.text.replace(self.api_key, '[REDACTED]')
                if not response.ok:
                    raise RuntimeError(result['response'])
                try:
                    body = response.json()
                except ValueError:
                    body = {}
                result['pol_number'] = body.get('number', '')
                self.successCount += 1
            except (ValueError, KeyError, RuntimeError, requests.RequestException) as exc:
                result['error'] = ('Connection failed; creation outcome may be unknown. Check Alma before retrying.' if isinstance(exc, requests.RequestException) else str(exc).replace(self.api_key, '[REDACTED]'))
                self.errorCount += 1
            self.results.append(result)
        return self.results

    def process_zip_bytes(self, ingest_method='spreadsheet'):
        if ingest_method == 'managed_set':
            self.retrieve_managed_set()
        elif ingest_method == 'spreadsheet':
            self.ingest_spreadsheet()
        else:
            raise ValueError('Unknown ingest method')
        self.create_pol()
        report = io.StringIO(newline='')
        fields = ['mms_id', 'title', 'price', 'http_status', 'pol_number', 'error']
        writer = csv.DictWriter(report, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        for row in self.results:
            writer.writerow({key: "'" + value if isinstance(value, str) and value.startswith(('=', '+', '-', '@')) else value for key, value in row.items() if key in fields})
        output = io.BytesIO()
        with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('results.csv', report.getvalue())
            archive.writestr('requests_and_responses.json', json.dumps(self.results, indent=2))
            archive.writestr('summary.txt', f'Items: {len(self.items)}\nCreated: {self.successCount}\nErrors/skipped: {self.errorCount}\n')
        return output.getvalue()
