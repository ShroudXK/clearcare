"""Behavioral evaluation with explicit expectations; no human usability results are invented."""
from __future__ import annotations

from .core import Context, generate_guide, load_demo_fixtures, network_status, rows, sql

def evaluate(con):
    results=[]
    def record(name, expected, actual):
        results.append({'case':name,'expected':expected,'actual':actual,'passed':expected==actual})
    def guide(**kwargs):
        return generate_guide(con, Context(**kwargs), '2026-10-07')
    def ids(g):
        return [s['step_id'] for s in g['steps']]
    campus=guide(scenario='campus_visit')
    community=guide(scenario='community_visit')
    followup=guide(scenario='fracture_followup')
    record('Campus: fee distinction included',True,'fee_difference' in ids(campus))
    record('Campus: official booking included',True,'book_mck' in ids(campus))
    record('Community: no campus fee assumption',False,'fee_difference' in ids(community))
    record('Community: network questions included',True,'network_check' in ids(community))
    record('Follow-up: no clinical timetable assigned',True,'does not set a treatment timetable' in next(s['body_en'] for s in followup['steps'] if s['step_id']=='follow_instructions'))
    record('Interpreter requested',True,'interpreter' in ids(followup))
    record('No interpreter requested',False,'interpreter' in ids(guide(needs_interpreter=False)))
    record('Missing insurance card',True,'missing_card' in ids(guide(has_insurance_card=False)))
    record('Insurance card present',False,'missing_card' in ids(followup))
    record('Prior records available',True,'records_ready' in ids(followup))
    record('Prior records unavailable',True,'records_missing' in ids(guide(has_prior_records=False)))
    record('Record paths mutually exclusive',False,'records_ready' in ids(guide(has_prior_records=False)))
    record('McKinley referral condition true',True,'mck_referral_help' in ids(guide(mckinley_referral=True)))
    record('McKinley referral condition false',False,'mck_referral_help' in ids(followup))
    order=ids(followup)
    record('Plan identity before network questions',True,order.index('plan_identity') < order.index('network_check'))
    record('No duplicated preparation steps',len(order),len(set(order)))
    emergency=guide(emergency=True)
    record('Emergency skips preparation workflow',0,len(emergency['steps']))
    record('Emergency skips insurance questions',False,'insurer_questions' in emergency)
    record('Coverage is never confirmed',False,followup['coverage_confirmed'])
    future=generate_guide(con,Context(),'2027-11-01')
    record('Expired sources replace asserted instructions',True,all('needs source review' in s['body_en'] for s in future['steps']))
    before=generate_guide(con,Context(),'2026-10-06')
    record('No evidence before the review date',True,all(s['evidence_state']=='not_yet_reviewed' for s in before['steps']))
    params=dict(facility_id='mckinley',provider_key='DEMO_CLINICIAN',plan_id='DEMO_PLAN',as_of='2026-10-07')
    record('No network observation stays unknown','unknown',network_status(con,**params)['network_status'])
    con.execute('BEGIN TRANSACTION')
    try:
        load_demo_fixtures(con)
        record('Synthetic observations excluded by default','unknown',network_status(con,**params)['network_status'])
        demo=network_status(con,**params,allow_synthetic=True)
        record('Latest demo observation selected','observed_in_network',demo['network_status'])
        record('Demo result explicitly labeled synthetic',True,demo['contains_synthetic'])
        record('Observed network does not prove coverage',False,demo['coverage_confirmed'])
        record('Expired demo observations stay unknown','unknown',network_status(con,**{**params,'as_of':'2026-11-10'},allow_synthetic=True)['network_status'])
        record('Provider mismatch stays unknown','unknown',network_status(con,**{**params,'provider_key':'OTHER'},allow_synthetic=True)['network_status'])
        record('Facility mismatch stays unknown','unknown',network_status(con,**{**params,'facility_id':'carle_er'},allow_synthetic=True)['network_status'])
        # A separate fictional evidence channel; it is never attributed to an official source.
        con.execute("INSERT INTO network_observations VALUES ('conflict','mckinley','DEMO_CLINICIAN','DEMO_PLAN',NULL,'demo_secondary','out_of_network','2026-10-02','2026-10-31',TRUE)")
        record('Disagreeing sources flagged','conflicting',network_status(con,**params,allow_synthetic=True)['network_status'])
    finally:
        con.execute('ROLLBACK')
    return {'as_of':'2026-10-07','evaluation_type':'Predefined software and data-handling scenarios; not clinical or human-subject validation.',
            'total':len(results),'passed':sum(r['passed'] for r in results),
            'failed':sum(not r['passed'] for r in results),'cases':results}
