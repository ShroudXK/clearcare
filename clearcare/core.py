"""Database loading, parameterized queries, and scenario-specific guide generation."""
from __future__ import annotations

import csv
import hashlib
import heapq
import html
import json
import os
import tempfile
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import duckdb

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data' / 'curated'
TABLES = ('sources','facilities','services','facility_services','resources','prep_steps',
          'step_applicability','step_sources','step_dependencies','plan_versions','network_observations')
SCENARIOS = ('campus_visit','community_visit','fracture_followup')
LABELS = {
    'campus_visit': ('A campus appointment', '校内就诊准备'),
    'community_visit': ('A community appointment', '校外就诊准备'),
    'fracture_followup': ('Preparing for fracture follow-up', '骨折初诊后的复诊准备'),
}
DOMAINS = {'mckinley.illinois.edu','www.mckinley.illinois.edu','carle.org','www.carle.org',
           'www.healthcare.gov','medlineplus.gov','www.cms.gov'}

@dataclass(frozen=True)
class Context:
    scenario: str = 'fracture_followup'
    needs_interpreter: bool = True
    has_insurance_card: bool = True
    has_prior_records: bool = True
    mckinley_referral: bool = False
    emergency: bool = False

    def __post_init__(self):
        if self.scenario not in SCENARIOS:
            raise ValueError(f'Unknown scenario: {self.scenario}')
        for name, value in asdict(self).items():
            if name != 'scenario' and type(value) is not bool:
                raise ValueError(f'{name} must be a boolean')

def sql(name: str) -> str:
    return (ROOT / 'sql' / name).read_text(encoding='utf-8')

def rows(con, statement, params=None):
    result = con.execute(statement, params or {})
    columns = [x[0] for x in result.description]
    return [dict(zip(columns, row)) for row in result.fetchall()]

def json_value(value):
    if isinstance(value, (date, Path)):
        return str(value)
    raise TypeError(f'Cannot serialize {type(value).__name__}')

def write_json(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2,
                                    default=json_value) + '\n', encoding='utf-8')

def input_hashes(data_dir=DATA):
    files = [data_dir / f'{t}.csv' for t in TABLES] + [data_dir / 'dataset.json']
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}

def validate_manifest(data_dir=DATA):
    expected = json.loads((data_dir / 'checksums.json').read_text(encoding='utf-8'))
    actual = input_hashes(data_dir)
    if expected != actual:
        changed = sorted(k for k in set(expected) | set(actual) if expected.get(k) != actual.get(k))
        raise ValueError('Curated input checksum mismatch: ' + ', '.join(changed) +
                         '. Review changes before updating data/curated/checksums.json.')
    return hashlib.sha256(json.dumps(actual, sort_keys=True).encode()).hexdigest()

def trusted_url(url):
    parsed = urlparse(url)
    return (parsed.scheme == 'https' and parsed.hostname in DOMAINS
            and parsed.username is None and parsed.password is None and parsed.port in (None,443))

def topological_order(steps, dependencies):
    """Keep editorial order where possible, but always put prerequisites first."""
    by_id = {s['step_id']: s for s in steps}
    outgoing = {key: [] for key in by_id}
    degree = {key: 0 for key in by_id}
    for child, parent in dependencies:
        if child in by_id and parent in by_id:
            outgoing[parent].append(child)
            degree[child] += 1
    ready = [(s['sort_order'], key) for key,s in by_id.items() if degree[key] == 0]
    heapq.heapify(ready)
    ordered = []
    while ready:
        _, key = heapq.heappop(ready)
        ordered.append(by_id[key])
        for child in sorted(outgoing[key]):
            degree[child] -= 1
            if degree[child] == 0:
                heapq.heappush(ready, (by_id[child]['sort_order'], child))
    if len(ordered) != len(steps):
        raise ValueError('Preparation step dependencies contain a cycle.')
    return ordered

def audit(con, as_of):
    checks = rows(con, sql('data_quality.sql'), {'as_of': as_of})
    bad_urls = 0
    for table, column in (('sources','url'), ('facilities','entry_url'), ('resources','url')):
        bad_urls += sum(not trusted_url(r[column]) for r in rows(con, f'SELECT {column} FROM {table}'))
    checks.append({'check_name':'unapproved_source_or_resource_urls','issues':bad_urls})
    topological_order(rows(con,'SELECT * FROM prep_steps'), con.execute(
        'SELECT step_id, depends_on_id FROM step_dependencies').fetchall())
    checks.append({'check_name':'dependency_cycles','issues':0})
    fresh = rows(con, sql('source_freshness.sql'), {'as_of':as_of})
    counts = {t: con.execute(f'SELECT count(*) FROM {t}').fetchone()[0] for t in TABLES}
    return {'as_of':as_of, 'row_counts':counts, 'checks':checks,
            'issue_count':sum(c['issues'] for c in checks), 'source_freshness':fresh,
            'note':'Review intervals are project maintenance choices, not guarantees of current accuracy.'}

def build_database(destination: Path, data_dir=DATA):
    """Build an isolated database; replace the previous build only after successful validation."""
    digest = validate_manifest(data_dir)
    meta = json.loads((data_dir / 'dataset.json').read_text(encoding='utf-8'))
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(prefix='.clearcare-', suffix='.duckdb', dir=destination.parent)
    os.close(handle)
    temp_path = Path(temp_name)
    temp_path.unlink()  # DuckDB creates its own file; an empty existing file is not a database.
    con = None
    try:
        con = duckdb.connect(str(temp_path))
        con.execute('BEGIN TRANSACTION')
        con.execute(sql('schema.sql'))
        for table in TABLES:
            # Table names come only from the fixed TABLES tuple; the CSV path is a bound value.
            columns = [r[1] for r in con.execute(f"PRAGMA table_info('{table}')").fetchall()]
            normalized = ', '.join(f'trim("{name}") AS "{name}"' for name in columns)
            con.execute(f'INSERT INTO {table} BY NAME SELECT {normalized} '
                        'FROM read_csv(?, header=true, all_varchar=true, nullstr=\'\')',
                        [str(data_dir / f'{table}.csv')])
        con.execute('INSERT INTO dataset_meta VALUES (?, ?, ?)',
                    [meta['version'], digest, meta['review_date']])
        report = audit(con, meta['review_date'])
        if report['issue_count']:
            raise ValueError(f'Data quality checks failed: {report["checks"]}')
        con.execute('COMMIT')
        con.close()
        con = None
        os.replace(temp_path, destination)
        return report
    except Exception:
        if con is not None:
            con.close()  # Closing an uncommitted connection rolls back the transaction.
        temp_path.unlink(missing_ok=True)
        Path(str(temp_path)+'.wal').unlink(missing_ok=True)
        raise

def network_status(con, *, facility_id, provider_key, plan_id, as_of, allow_synthetic=False):
    return rows(con, sql('network_status.sql'), dict(facility_id=facility_id,
                provider_key=provider_key, plan_id=plan_id, as_of=as_of,
                allow_synthetic=allow_synthetic))[0]

def generate_guide(con, context: Context, as_of: str):
    date.fromisoformat(as_of)
    base = {'context':asdict(context), 'as_of':as_of,
            'scope':'UIUC / Champaign–Urbana; navigation and preparation only',
            'translation':'Chinese text is a project translation, not an official translation.',
            'network_status':'unknown', 'coverage_confirmed':False}
    if context.emergency:
        return dict(base, mode='emergency', steps=[], resources=[],
                    emergency_message='For a medical emergency, call 911 or seek the nearest emergency department. Do not delay emergency care for these appointment or insurance steps.',
                    emergency_message_zh='医疗紧急情况请拨打 911 或寻求最近的急诊科帮助。不要为完成预约或保险步骤而延误急诊。',
                    emergency_source='https://www.healthcare.gov/using-marketplace-coverage/getting-emergency-care/')
    params = asdict(context)
    params.pop('emergency')
    params['as_of'] = as_of
    steps = rows(con, sql('guide_steps.sql'), params)
    for s in steps:
        s['sources'] = rows(con, 'SELECT s.* FROM sources s JOIN step_sources ss USING(source_id) '
                            'WHERE ss.step_id = ? ORDER BY s.source_id', [s['step_id']])
        if s['evidence_state'] != 'within_review_interval':
            s['body_en'] = 'This item needs source review for the selected date. Open the official source and confirm the current instructions before using it.'
            s['body_zh'] = '这条信息在所选日期需要重新核实。请打开官方来源，确认当前要求后再使用。'
    dependencies = con.execute('SELECT step_id, depends_on_id FROM step_dependencies').fetchall()
    steps = topological_order(steps, dependencies)
    resources = rows(con, '''SELECT r.*, s.reviewed_on,
        CASE WHEN $as_of::DATE < s.reviewed_on THEN 'not_yet_reviewed'
             WHEN date_diff('day',s.reviewed_on,$as_of::DATE) > s.review_interval_days
             THEN 'needs_review' ELSE 'within_review_interval' END AS evidence_state
        FROM resources r JOIN sources s USING(source_id)
        WHERE r.scenario IN ('all', $scenario) ORDER BY r.resource_id''',
        {'as_of':as_of, 'scenario':context.scenario})
    office = [
        "I'm a new patient arranging a visit. Do you accept new patients, and how should I book?",
        'Which clinician and location will I see? Which documents or prior records should I bring?',
    ]
    if context.scenario == 'fracture_followup':
        office.append('I was already treated for a fracture and am arranging follow-up. Do I need a referral, and how should my existing records be sent?')
    if context.needs_interpreter:
        office.append('Could you arrange a Mandarin interpreter? Please confirm how this will work for my appointment.')
    insurer = [
        'My exact plan and network are [plan/network]. Is [clinician] at [location] in this network?',
        'For the planned service [service], what coverage conditions, referral requirements, or prior authorization apply?',
        'What deductible or other cost sharing may apply? Can you provide a reference number for this conversation?',
    ]
    return dict(base, mode='preparation', steps=steps, resources=resources,
                office_questions=office, insurer_questions=insurer,
                script_note='Project-written question templates. They ask for confirmation and do not state provider or insurer requirements.')

def render_markdown(guide):
    if guide['mode'] == 'emergency':
        return '# ClearCare: emergency entry\n\n' + guide['emergency_message'] + '\n\n' + guide['emergency_message_zh'] + '\n\n[Official source](' + guide['emergency_source'] + ')\n'
    en, zh = LABELS[guide['context']['scenario']]
    lines = [f'# ClearCare: {en}', '', zh, '',
        f'**As of:** {guide["as_of"]} · **Scope:** {guide["scope"]}', '',
        '> Medical emergency: call 911 or seek the nearest emergency department. Do not delay care for insurance checks.', '',
        '**Insurance status: unknown. Coverage has not been confirmed.**', '',
        guide['translation'], '', '## Official entry points', '']
    for r in guide['resources']:
        phone = (' · ' + r['phone']) if r['phone'] else ''
        lines.append(f'- [{r["title_en"]} / {r["title_zh"]}]({r["url"]}){phone} · {r["evidence_state"]}')
    lines += ['', '## Preparation checklist', '']
    for s in guide['steps']:
        lines += [f'- [ ] **{s["title_en"]} / {s["title_zh"]}**',
                  f'  - {s["body_en"]}', f'  - {s["body_zh"]}',
                  f'  - Type: {s["kind"]} · Evidence: {s["evidence_state"]}']
        lines.append('  - Sources: ' + '; '.join(
            f'[{src["title"]}]({src["url"]}) ({src["locator"]}; reviewed {src["reviewed_on"]})' for src in s['sources']))
    lines += ['', '## Questions for the office', ''] + [f'- {q}' for q in guide['office_questions']]
    lines += ['', '## Questions for the insurer', ''] + [f'- {q}' for q in guide['insurer_questions']]
    lines += ['', guide['script_note'], '',
              'This guide organizes public information. It does not diagnose, book an appointment, determine clinical urgency, or guarantee coverage. No personal medical information is required.', '']
    return '\n'.join(lines)

CSS = '''
:root{--ink:#193943;--teal:#087c78;--bg:#f5f6f1;--muted:#566b70;--line:#dae4df}
*{box-sizing:border-box}body{margin:0;color:var(--ink);background:var(--bg);font:16px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
header,main,footer{max-width:1080px;margin:auto;padding:28px}header{padding-top:40px}.brand{font-size:18px;letter-spacing:.1em;color:var(--teal);font-weight:700}
h1{font-size:clamp(28px,4vw,44px);line-height:1.15;max-width:830px;margin:24px 0 12px}h2{font-size:23px;margin-top:28px}h3{font-size:18px;margin:0}p{margin:8px 0}
.muted,.zh{color:var(--muted)}.badge{display:inline-block;border:1px solid var(--line);border-radius:20px;padding:3px 12px;margin:6px 6px 0 0;font-size:13px;background:white}
.notice{background:#fff2e2;border-left:4px solid #ba7734;padding:14px 20px;border-radius:8px;margin:18px 0}.status{background:#e5efec;padding:16px 20px;border-radius:10px}
.layout{display:grid;grid-template-columns:minmax(0,2fr) minmax(250px,1fr);gap:24px}.card{background:white;border:1px solid var(--line);border-radius:12px;padding:20px;margin:14px 0}
.step-label{display:flex;gap:12px;align-items:flex-start}.step-label input{margin-top:7px;accent-color:var(--teal);height:18px;width:18px;flex-shrink:0}.step-label:has(input:checked){opacity:.55}
.source{font-size:12px;color:var(--muted);border-top:1px solid var(--line);padding-top:10px;margin-top:14px}.kind{font-size:12px;color:var(--teal);text-transform:uppercase;letter-spacing:.08em}
a{color:var(--teal);text-underline-offset:3px}ul{padding-left:23px}.script{font-size:15px}.warning{color:#8b4e18}button{background:var(--ink);color:white;border:0;border-radius:6px;padding:10px 18px;cursor:pointer;font:inherit}
footer{font-size:13px;border-top:1px solid var(--line);margin-top:22px}@media(max-width:760px){.layout{grid-template-columns:1fr}header,main,footer{padding:20px}}
@media print{button{display:none}.layout{display:block}.card{break-inside:avoid}body{background:white}header,main,footer{padding:10px}.source{font-size:10px}}
'''

def render_html(guide):
    esc = lambda x: html.escape(str(x), quote=True)
    if guide['mode'] == 'emergency':
        body = f'<h1>Emergency entry / 急诊入口</h1><div class="notice"><p>{esc(guide["emergency_message"])}</p><p lang="zh-Hans">{esc(guide["emergency_message_zh"])}</p></div><a href="{esc(guide["emergency_source"])}">Official emergency information</a>'
        return f'<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ClearCare · Emergency entry</title><style>{CSS}</style><main>{body}</main></html>'
    en, zh = LABELS[guide['context']['scenario']]
    cards=[]
    for s in guide['steps']:
        refs=''.join(f'<p><a href="{esc(src["url"])}">{esc(src["title"])}</a> · {esc(src["locator"])} · reviewed {esc(src["reviewed_on"])}</p>' for src in s['sources'])
        state = '' if s['evidence_state'] == 'within_review_interval' else ' warning'
        cards.append(f'''<article class="card"><div class="kind{state}">{esc(s['kind'])} · {esc(s['evidence_state'].replace('_',' '))}</div>
<label class="step-label"><input type="checkbox" aria-label="Mark {esc(s['title_en'])} complete"><span><h3>{esc(s['title_en'])}</h3><p class="zh" lang="zh-Hans">{esc(s['title_zh'])}</p></span></label>
<p>{esc(s['body_en'])}</p><p class="zh" lang="zh-Hans">{esc(s['body_zh'])}</p><div class="source">{refs}</div></article>''')
    resources=''.join(f'<li><a href="{esc(r["url"])}">{esc(r["title_en"])}</a><p lang="zh-Hans" class="zh">{esc(r["title_zh"])}</p><p>{esc(r["phone"] or "")}</p><small>{esc(r["evidence_state"].replace("_"," "))}</small></li>' for r in guide['resources'])
    office=''.join(f'<li>{esc(q)}</li>' for q in guide['office_questions'])
    insurer=''.join(f'<li>{esc(q)}</li>' for q in guide['insurer_questions'])
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ClearCare · {esc(en)}</title><style>{CSS}</style></head><body>
<header><div class="brand">CLEARCARE</div><h1>{esc(en)}</h1><p class="zh" lang="zh-Hans">{esc(zh)}</p><p class="muted">A practical guide for students learning to navigate healthcare in the U.S.</p>
<span class="badge">UIUC / Champaign–Urbana</span><span class="badge">As of {esc(guide['as_of'])}</span><span class="badge">Research prototype</span>
<div class="notice"><strong>Medical emergency?</strong> Call 911 or seek the nearest emergency department. Do not delay care for appointment or insurance steps.<p lang="zh-Hans">医疗紧急情况请拨打 911 或寻求最近的急诊科帮助。不要为预约或保险步骤延误急诊。</p></div>
<div class="status"><strong>Insurance status: unknown / 保险状态：未确认</strong><p>Confirm your exact plan, clinician, location, and planned service with the insurer and office. This guide does not guarantee coverage.</p></div></header>
<main><div class="layout"><section aria-label="Preparation checklist"><h2>Your preparation checklist</h2><p class="muted">Check off items as you go. These checkboxes are temporary and are not saved.</p>{''.join(cards)}</section>
<aside><h2>Official entry points</h2><div class="card"><ul>{resources}</ul><p class="source">Listed resources are starting points, not clinical recommendations. Confirm eligibility and current availability.</p></div>
<h2>Questions for the office</h2><div class="card script"><ul>{office}</ul></div><h2>Questions for the insurer</h2><div class="card script"><ul>{insurer}</ul><p class="source">{esc(guide['script_note'])}</p></div><button onclick="window.print()">Print / 打印</button></aside></div></main>
<footer><p>{esc(guide['translation'])}</p><p>This guide organizes public information. It does not diagnose, determine clinical urgency, book appointments, or guarantee coverage. No personal medical information is required. Source review dates record this project's desk review, not provider approval.</p><p>Use the linked official sources to confirm current instructions.</p></footer></body></html>'''

def save_guide(directory, stem, guide):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    write_json(directory / f'{stem}.json', guide)
    (directory / f'{stem}.md').write_text(render_markdown(guide), encoding='utf-8')
    (directory / f'{stem}.html').write_text(render_html(guide), encoding='utf-8')

def load_demo_fixtures(con):
    fixture = json.loads((ROOT/'data/fixtures/network_demo.json').read_text(encoding='utf-8'))
    for table, key in (('plan_versions','plans'), ('network_observations','observations')):
        for item in fixture[key]:
            fields=list(item)
            con.execute(f'INSERT INTO {table} ({", ".join(fields)}) VALUES ({", ".join("?" for _ in fields)})',
                        [item[k] for k in fields])

def export_query(con, path, statement, params=None):
    result = rows(con, statement, params)
    if result:
        with Path(path).open('w',newline='',encoding='utf-8') as f:
            writer=csv.DictWriter(f,fieldnames=list(result[0]),lineterminator='\n')
            writer.writeheader(); writer.writerows(result)
    return result
