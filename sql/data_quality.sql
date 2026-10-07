-- Constraints catch duplicate keys and broken references at load time; these check content completeness.
SELECT 'steps_without_sources' AS check_name, count(*) AS issues
FROM prep_steps p LEFT JOIN step_sources s USING (step_id) WHERE s.source_id IS NULL
UNION ALL
SELECT 'steps_without_applicability', count(*)
FROM prep_steps p LEFT JOIN step_applicability a USING (step_id) WHERE a.scenario IS NULL
UNION ALL
SELECT 'blank_bilingual_content', count(*) FROM prep_steps
WHERE trim(title_en) = '' OR trim(title_zh) = '' OR trim(body_en) = '' OR trim(body_zh) = ''
UNION ALL
SELECT 'future_source_reviews', count(*) FROM sources WHERE reviewed_on > $as_of::DATE
UNION ALL
SELECT 'invalid_review_intervals', count(*) FROM sources WHERE review_interval_days <= 0
UNION ALL
SELECT 'synthetic_in_production',
    (SELECT count(*) FROM plan_versions WHERE is_synthetic) +
    (SELECT count(*) FROM network_observations WHERE is_synthetic)
UNION ALL
SELECT 'observations_without_provider_identity', count(*) FROM network_observations
WHERE trim(provider_key) = '';
