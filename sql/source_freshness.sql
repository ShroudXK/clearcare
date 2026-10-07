SELECT source_id, publisher, title, url, reviewed_on, review_interval_days,
       date_diff('day', reviewed_on, $as_of::DATE) AS days_since_review,
       CASE WHEN $as_of::DATE < reviewed_on THEN 'not_yet_reviewed'
            WHEN date_diff('day', reviewed_on, $as_of::DATE) > review_interval_days THEN 'needs_review'
            ELSE 'within_review_interval' END AS evidence_state
FROM sources ORDER BY source_id;
