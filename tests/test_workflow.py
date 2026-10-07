"""Regression tests for data integrity, uncertainty handling, and reproducibility."""
import csv
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import duckdb

from clearcare.core import (DATA, Context, audit, build_database, generate_guide,
    input_hashes, load_demo_fixtures, network_status, render_html, render_markdown,
    topological_order, trusted_url, validate_manifest, write_json)
from clearcare.evaluate import evaluate
from clearcare.sources import extract_text, fetch_source, normalize

class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.directory=Path(self.temp.name)
        self.db=self.directory/'test.duckdb'
        build_database(self.db)
        self.con=duckdb.connect(str(self.db))
    def tearDown(self):
        self.con.close()
        self.temp.cleanup()
    def guide(self, **kwargs):
        return generate_guide(self.con,Context(**kwargs),'2026-10-07')
    def network(self, **kwargs):
        params=dict(facility_id='mckinley',provider_key='DEMO_CLINICIAN',plan_id='DEMO_PLAN',as_of='2026-10-07')
        return network_status(self.con,**{**params,**kwargs})

    def test_all_behavioral_cases(self):
        report=evaluate(self.con)
        self.assertEqual(report['total'],30)
        for case in report['cases']:
            with self.subTest(case=case['case']):
                self.assertTrue(case['passed'],case)
        self.assertEqual(self.con.execute('SELECT count(*) FROM network_observations').fetchone()[0],0)
        self.assertEqual(self.con.execute('SELECT count(*) FROM plan_versions').fetchone()[0],0)

    def test_primary_key_rejects_duplicate(self):
        with self.assertRaises(duckdb.ConstraintException):
            self.con.execute("INSERT INTO services VALUES ('radiology','Duplicate','重复')")

    def test_foreign_key_rejects_missing_facility(self):
        with self.assertRaises(duckdb.ConstraintException):
            self.con.execute("INSERT INTO facility_services VALUES ('missing','radiology','mck_fee','bad')")

    def test_checksum_rejects_unreviewed_change(self):
        dataset=self.directory/'changed'
        shutil.copytree(DATA,dataset)
        with (dataset/'prep_steps.csv').open('a',encoding='utf-8') as f:
            f.write('\n')
        with self.assertRaisesRegex(ValueError,'checksum mismatch'):
            validate_manifest(dataset)

    def test_failed_build_keeps_previous_database(self):
        self.con.close()
        before=hashlib.sha256(self.db.read_bytes()).hexdigest()
        dataset=self.directory/'bad'
        shutil.copytree(DATA,dataset)
        with (dataset/'services.csv').open('a',encoding='utf-8') as f:
            f.write('radiology,Duplicate,重复\n')
        write_json(dataset/'checksums.json',input_hashes(dataset))
        with self.assertRaises(duckdb.ConstraintException):
            build_database(self.db,dataset)
        self.assertEqual(before,hashlib.sha256(self.db.read_bytes()).hexdigest())
        self.con=duckdb.connect(str(self.db))

    def test_offline_replay_is_deterministic(self):
        first=render_markdown(self.guide())
        second=render_markdown(self.guide())
        self.assertEqual(first,second)
        other=self.directory/'other.duckdb'
        build_database(other)
        with duckdb.connect(str(other)) as con:
            self.assertEqual(first,render_markdown(generate_guide(con,Context(),'2026-10-07')))

    def test_no_patient_fields_or_real_network_rows(self):
        self.assertEqual(self.con.execute('SELECT count(*) FROM network_observations').fetchone()[0],0)
        self.assertNotIn('name',Context.__dataclass_fields__)
        self.assertNotIn('symptoms',Context.__dataclass_fields__)
        self.assertFalse(self.guide()['coverage_confirmed'])

    def test_source_and_dependency_coverage(self):
        report=audit(self.con,'2026-10-07')
        self.assertEqual(report['issue_count'],0)
        self.assertEqual(report['row_counts']['sources'],16)
        self.assertEqual(report['row_counts']['prep_steps'],22)

    def test_dependency_cycle_is_rejected(self):
        steps=[{'step_id':'a','sort_order':1},{'step_id':'b','sort_order':2}]
        with self.assertRaisesRegex(ValueError,'cycle'):
            topological_order(steps,[('a','b'),('b','a')])

    def test_conditional_paths_and_mandarin_script(self):
        guide=self.guide(needs_interpreter=False,has_prior_records=False)
        ids=[s['step_id'] for s in guide['steps']]
        self.assertNotIn('interpreter',ids)
        self.assertIn('records_missing',ids)
        self.assertNotIn('records_ready',ids)
        self.assertFalse(any('Mandarin' in q for q in guide['office_questions']))

    def test_stale_and_pre_review_content_is_withheld(self):
        for when in ('2027-11-01','2026-10-06'):
            guide=generate_guide(self.con,Context(),when)
            for step in guide['steps']:
                self.assertIn('needs source review',step['body_en'])
                self.assertNotEqual(step['evidence_state'],'within_review_interval')

    def test_html_escapes_content(self):
        guide=self.guide()
        guide['steps'][0]['body_en']='<script>alert("test")</script>'
        page=render_html(guide)
        self.assertIn('&lt;script&gt;',page)
        self.assertNotIn('<script>alert',page)
        self.assertIn('lang="zh-Hans"',page)

    def test_unknown_and_synthetic_default(self):
        self.assertEqual(self.network()['network_status'],'unknown')
        load_demo_fixtures(self.con)
        self.assertEqual(self.network()['network_status'],'unknown')
        self.assertTrue(self.network(allow_synthetic=True)['contains_synthetic'])
        self.assertFalse(self.network(allow_synthetic=True)['coverage_confirmed'])

    def test_parameter_binding_handles_injection_text(self):
        result=self.network(provider_key="'; DROP TABLE sources; --",allow_synthetic=True)
        self.assertEqual(result['network_status'],'unknown')
        self.assertEqual(self.con.execute('SELECT count(*) FROM sources').fetchone()[0],16)

    def test_future_observation_does_not_overwrite_current(self):
        load_demo_fixtures(self.con)
        self.con.execute("INSERT INTO network_observations VALUES ('future','mckinley','DEMO_CLINICIAN','DEMO_PLAN',NULL,'demo_primary','out_of_network','2026-10-20','2026-10-31',TRUE)")
        self.assertEqual(self.network(allow_synthetic=True)['network_status'],'observed_in_network')

    def test_latest_unknown_does_not_restore_older_positive(self):
        load_demo_fixtures(self.con)
        self.con.execute("INSERT INTO network_observations VALUES ('latest','mckinley','DEMO_CLINICIAN','DEMO_PLAN',NULL,'demo_primary','unknown','2026-10-03','2026-10-31',TRUE)")
        self.assertEqual(self.network(allow_synthetic=True)['network_status'],'unknown')

    def test_same_day_disagreement_is_not_arbitrarily_resolved(self):
        load_demo_fixtures(self.con)
        self.con.execute("INSERT INTO network_observations VALUES ('tie','mckinley','DEMO_CLINICIAN','DEMO_PLAN',NULL,'demo_primary','out_of_network','2026-10-01','2026-10-31',TRUE)")
        self.assertEqual(self.network(allow_synthetic=True)['network_status'],'conflicting')

    def test_empty_source_record_rejected_by_audit(self):
        self.con.execute("DELETE FROM step_sources WHERE step_id='care_types'")
        report=audit(self.con,'2026-10-07')
        self.assertGreater(report['issue_count'],0)

    def test_emergency_has_no_preparation_delay(self):
        page=render_html(self.guide(emergency=True))
        self.assertIn('911',page)
        self.assertNotIn('Preparation checklist',page)
        self.assertNotIn('Questions for the insurer',page)

class RetrievalTests(unittest.TestCase):
    def test_html_extraction_ignores_script(self):
        text=extract_text(b'<h1>Clinic</h1><script>secret()</script><p>Call us</p>','html')
        self.assertIn('Clinic',text)
        self.assertNotIn('secret',text)
    def test_normalization_handles_whitespace(self):
        self.assertEqual(normalize(' Photo\n   Identification '),'photo identification')
    def test_non_pdf_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'not a PDF'):
            extract_text(b'<html>blocked</html>','pdf')
    def test_unapproved_url_never_fetched(self):
        source={'source_id':'bad','url':'http://localhost/private','format':'html','anchors':'x'}
        with tempfile.TemporaryDirectory() as directory, patch('urllib.request.build_opener') as opener:
            result=fetch_source(source,Path(directory))
            self.assertEqual(result['status'],'fetch_failed_needs_review')
            opener.assert_not_called()
    def test_domain_prefix_does_not_count_as_trusted(self):
        self.assertFalse(trusted_url('https://www.cms.gov.evil.example/test'))
        self.assertFalse(trusted_url('https://user:pass@www.cms.gov/test'))
        self.assertTrue(trusted_url('https://www.cms.gov/test'))

if __name__ == '__main__':
    unittest.main()
