"""Compare fixed-date pipeline results with published outputs."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def main():
    checked=0
    for path in sorted((ROOT/'examples').glob('*')):
        if path.suffix not in ('.json','.md','.html'):
            continue
        generated=ROOT/'build/guides'/path.name
        if not generated.exists():
            raise SystemExit(f'Missing {generated}. Run the fixed-date pipeline first.')
        if path.read_bytes() != generated.read_bytes():
            raise SystemExit(f'Published example differs from generated result: {path.name}')
        checked+=1
    if checked != 12:
        raise SystemExit(f'Expected 12 guide files, found {checked}.')
    for name in ('evaluation.json','data_quality.json'):
        published=json.loads((ROOT/'docs/results'/name).read_text(encoding='utf-8'))
        generated=json.loads((ROOT/'build'/name).read_text(encoding='utf-8'))
        if published != generated:
            raise SystemExit(f'Published report differs: {name}')
    print(f'Published examples match: {checked} guide files and 2 reports.')

if __name__=='__main__':
    main()
