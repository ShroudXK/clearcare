-- A service listing is evidence of advertised services, not real-time availability.
SELECT f.facility_id, f.name, f.city, f.care_type,
       s.name_en AS service, fs.scope_note, src.url, src.reviewed_on,
       CASE WHEN $as_of::DATE < src.reviewed_on THEN 'not_yet_reviewed'
            WHEN date_diff('day', src.reviewed_on, $as_of::DATE) > src.review_interval_days
            THEN 'needs_review' ELSE 'within_review_interval' END AS evidence_state
FROM facilities f
JOIN facility_services fs USING (facility_id)
JOIN services s USING (service_id)
JOIN sources src ON fs.source_id = src.source_id
WHERE s.service_id = $service_id
ORDER BY f.name;
