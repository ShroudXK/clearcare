"""Optional live source checks. Fetching never approves or edits curated guidance."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import unicodedata
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

from pypdf import PdfReader

from .core import DATA, trusted_url, write_json

MAX_BYTES = 20 * 1024 * 1024

class TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hidden = 0
        self.parts = []
    def handle_starttag(self, tag, attrs):
        if tag in ('script','style','noscript'):
            self.hidden += 1
    def handle_endtag(self, tag):
        if tag in ('script','style','noscript') and self.hidden:
            self.hidden -= 1
    def handle_data(self, text):
        if not self.hidden:
            self.parts.append(text)

def normalize(text):
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', text).replace('\u00ad','')).strip().casefold()

def extract_text(body, source_format):
    if source_format == 'pdf':
        if not body.startswith(b'%PDF'):
            raise ValueError('Expected a PDF, but the response is not a PDF.')
        reader = PdfReader(io.BytesIO(body))
        return '\n'.join(page.extract_text() or '' for page in reader.pages)
    parser = TextParser()
    parser.feed(body.decode('utf-8', errors='replace'))
    return ' '.join(parser.parts)

class TrustedRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not trusted_url(newurl):
            raise ValueError('Redirect outside the approved HTTPS source domains.')
        return super().redirect_request(req, fp, code, msg, headers, newurl)

def fetch_source(source, raw_dir, baseline=None):
    record = {'source_id':source['source_id'], 'url':source['url'],
              'checked_at_utc':datetime.now(timezone.utc).isoformat(),
              'human_review_updated':False}
    try:
        if not trusted_url(source['url']):
            raise ValueError('URL is outside the approved HTTPS source domains.')
        opener = urllib.request.build_opener(TrustedRedirect())
        request = urllib.request.Request(source['url'], headers={'User-Agent':'ClearCare/1.0 academic source verification'})
        with opener.open(request, timeout=20) as response:
            if not trusted_url(response.geturl()):
                raise ValueError('Response URL is outside the approved source domains.')
            body = response.read(MAX_BYTES + 1)
            if len(body) > MAX_BYTES:
                raise ValueError('Response exceeds the 20 MB source limit.')
            record.update(http_status=response.status, final_url=response.geturl(),
                          content_type=response.headers.get('Content-Type',''))
        digest = hashlib.sha256(body).hexdigest()
        suffix = 'pdf' if source['format'] == 'pdf' else 'html'
        raw_path = Path(raw_dir) / f'{source["source_id"]}-{digest[:12]}.{suffix}'
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_bytes(body)
        text = extract_text(body, source['format'])
        normalized = normalize(text)
        anchors = source['anchors'].split('|')
        matches = {a:normalize(a) in normalized for a in anchors}
        old_hash = (baseline or {}).get('raw_sha256')
        if not all(matches.values()):
            state = 'anchor_mismatch_needs_review'
        elif old_hash and old_hash != digest:
            state = 'bytes_changed_needs_review'
        else:
            state = 'retrieved_anchors_match'
        record.update(status=state, raw_sha256=digest, bytes=len(body),
                      extracted_characters=len(text), anchor_matches=matches,
                      baseline_hash_matches=(old_hash == digest) if old_hash else None,
                      note='Anchors and hashes are retrieval checks; they do not establish semantic accuracy.')
    except urllib.error.HTTPError as exc:
        record.update(status='fetch_failed_needs_review', http_status=exc.code,
                      error=f'HTTP {exc.code}: {exc.reason}')
    except Exception as exc:
        record.update(status='fetch_failed_needs_review', error=f'{type(exc).__name__}: {exc}')
    return record

def check_sources(output, data_dir=DATA, baseline_path=None):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    with (data_dir/'sources.csv').open(encoding='utf-8',newline='') as f:
        sources=list(csv.DictReader(f))
    baseline={}
    if baseline_path and Path(baseline_path).exists():
        baseline={r['source_id']:r for r in json.loads(Path(baseline_path).read_text(encoding='utf-8'))['sources']}
    with ThreadPoolExecutor(max_workers=4) as pool:
        records=list(pool.map(lambda s:fetch_source(s, output/'raw', baseline.get(s['source_id'])), sources))
    report={'mode':'live_retrieval_check', 'sources':records,
            'curation_modified':False,
            'note':'Changes and errors require review. HTTP success and matching anchors do not confirm all claims.'}
    write_json(output/'source_check.json',report)
    return report
