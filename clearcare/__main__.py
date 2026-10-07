"""Run with python -m clearcare; no web service or API credentials are required."""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

import duckdb

from .core import (DATA, ROOT, SCENARIOS, Context, audit, build_database, export_query,
                   generate_guide, save_guide, sql, write_json)
from .evaluate import evaluate
from .sources import check_sources

def parser():
    p=argparse.ArgumentParser(description='ClearCare: reproducible healthcare navigation workflow')
    sub=p.add_subparsers(dest='command',required=True)
    pipe=sub.add_parser('pipeline',help='Build, audit, evaluate, and export all three demo scenarios')
    pipe.add_argument('--output',type=Path,default=Path('build'))
    pipe.add_argument('--as-of',default='2026-10-07',help='Fixed snapshot date by default; not a live coverage check')
    build=sub.add_parser('build',help='Build a validated DuckDB database from the reviewed snapshot')
    build.add_argument('--database',type=Path,default=Path('build/clearcare.duckdb'))
    guide=sub.add_parser('guide',help='Generate one guide from an existing database')
    guide.add_argument('--database',type=Path,default=Path('build/clearcare.duckdb'))
    guide.add_argument('--output',type=Path,default=Path('build/guides'))
    guide.add_argument('--scenario',choices=SCENARIOS,default='fracture_followup')
    guide.add_argument('--as-of',default=date.today().isoformat())
    guide.add_argument('--needs-interpreter',action='store_true')
    guide.add_argument('--no-insurance-card',action='store_true')
    guide.add_argument('--no-prior-records',action='store_true')
    guide.add_argument('--mckinley-referral',action='store_true')
    guide.add_argument('--emergency',action='store_true')
    refresh=sub.add_parser('check-sources',help='Fetch live sources without changing reviewed content')
    refresh.add_argument('--output',type=Path,default=Path('build/source_check'))
    refresh.add_argument('--baseline',type=Path,default=DATA/'retrieval_baseline.json')
    return p

def main(argv=None):
    args=parser().parse_args(argv)
    try:
        if args.command == 'check-sources':
            report=check_sources(args.output,baseline_path=args.baseline)
            flagged=sum(r['status'] != 'retrieved_anchors_match' for r in report['sources'])
            print(f'Checked {len(report["sources"])} sources; {flagged} need review. Curated data was not changed.')
            return 0 if flagged == 0 else 2
        if hasattr(args,'as_of'):
            date.fromisoformat(args.as_of)
        if args.command == 'build':
            result=build_database(args.database)
            print(f'Built {args.database}; {result["issue_count"]} data quality issues.')
            return 0
        if args.command == 'guide':
            if not args.database.is_file():
                raise ValueError('Database not found. Run python -m clearcare build first.')
            context=Context(args.scenario,args.needs_interpreter,not args.no_insurance_card,
                            not args.no_prior_records,args.mckinley_referral,args.emergency)
            with duckdb.connect(str(args.database),read_only=True) as con:
                save_guide(args.output,'emergency' if args.emergency else args.scenario,
                           generate_guide(con,context,args.as_of))
            print(f'Guide written to {args.output}. Coverage remains unconfirmed.')
            return 0
        args.output.mkdir(parents=True,exist_ok=True)
        database=args.output/'clearcare.duckdb'
        build_database(database)
        with duckdb.connect(str(database)) as con:
            report=audit(con,args.as_of)
            write_json(args.output/'data_quality.json',report)
            evaluation=evaluate(con)
            write_json(args.output/'evaluation.json',evaluation)
            export_query(con,args.output/'source_freshness.csv',sql('source_freshness.sql'),{'as_of':args.as_of})
            export_query(con,args.output/'advertised_imaging_services.csv',sql('facility_services.sql'),
                         {'as_of':args.as_of,'service_id':'radiology'})
            for scenario in SCENARIOS:
                save_guide(args.output/'guides',scenario,generate_guide(con,Context(scenario=scenario),args.as_of))
            save_guide(args.output/'guides','emergency',generate_guide(con,Context(emergency=True),args.as_of))
        write_json(args.output/'run_manifest.json',{
            'dataset':'1.0.0','as_of':args.as_of,'python':sys.version.split()[0],
            'duckdb':duckdb.__version__,'network_used':False,'data_quality_issues':report['issue_count'],
            'evaluation_passed':evaluation['passed'],'evaluation_total':evaluation['total'],
            'note':'Deterministic snapshot replay. Live source acquisition is a separate opt-in step.'})
        print(f'Pipeline complete: {evaluation["passed"]}/{evaluation["total"]} scenarios passed; '
              f'{report["issue_count"]} data quality issues. Outputs: {args.output}')
        return 0 if evaluation['failed']==0 and report['issue_count']==0 else 1
    except (ValueError, OSError, duckdb.Error) as exc:
        print(f'ClearCare: {exc}',file=sys.stderr)
        return 1

if __name__ == '__main__':
    raise SystemExit(main())
