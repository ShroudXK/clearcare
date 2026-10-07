"""Copy inspected fixed-date results into version-controlled examples and reports."""
import argparse
import json
import shutil
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--review-confirmed',action='store_true')
args=p.parse_args()
if not args.review_confirmed:
    p.error('Inspect the fixed-date build before using --review-confirmed.')
manifest=json.loads((ROOT/'build/run_manifest.json').read_text(encoding='utf-8'))
if manifest['as_of'] != '2026-10-07' or manifest['data_quality_issues'] != 0 or manifest['evaluation_passed'] != manifest['evaluation_total']:
    raise SystemExit('Publish only a successful, inspected 2026-10-07 snapshot run.')
paths=list((ROOT/'build/guides').glob('*'))
if len(paths) != 12:
    raise SystemExit('Expected four guides in three formats. Run the fixed-date pipeline first.')
for path in paths:
    shutil.copy2(path,ROOT/'examples'/path.name)
(ROOT/'docs/results').mkdir(exist_ok=True)
for name in ('evaluation.json','data_quality.json'):
    shutil.copy2(ROOT/'build'/name,ROOT/'docs/results'/name)
print('Copied inspected examples and reports; regenerate docs/evaluation.md if the cases changed.')
