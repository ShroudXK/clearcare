"""Record accepted input bytes after source/content review, not instead of review."""
import argparse
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from clearcare.core import DATA, input_hashes, write_json

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--review-confirmed',action='store_true',help='Acknowledge that source and content changes were inspected')
args=p.parse_args()
if not args.review_confirmed:
    p.error('Inspect the source and content changes before using --review-confirmed.')
write_json(DATA/'checksums.json',input_hashes())
print('Recorded input checksums. Run tests and inspect regenerated examples next.')
