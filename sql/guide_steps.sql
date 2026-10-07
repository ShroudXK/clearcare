-- EXISTS avoids duplicating a step that is tagged with both all and a specific scenario.
WITH selected AS (
    SELECT p.*
    FROM prep_steps p
    WHERE EXISTS (
        SELECT 1 FROM step_applicability a
        WHERE a.step_id = p.step_id AND a.scenario IN ('all', $scenario)
    )
    AND CASE p.condition_key
        WHEN 'always' THEN TRUE
        WHEN 'needs_interpreter' THEN $needs_interpreter
        WHEN 'no_insurance_card' THEN NOT $has_insurance_card
        WHEN 'has_prior_records' THEN $has_prior_records
        WHEN 'no_prior_records' THEN NOT $has_prior_records
        WHEN 'mckinley_referral' THEN $mckinley_referral
        ELSE FALSE
    END
), dated_evidence AS (
    SELECT ss.step_id, s.source_id,
        CASE
            WHEN $as_of::DATE < s.reviewed_on THEN 'not_yet_reviewed'
            WHEN date_diff('day', s.reviewed_on, $as_of::DATE) > s.review_interval_days THEN 'needs_review'
            ELSE 'within_review_interval'
        END AS evidence_state
    FROM step_sources ss JOIN sources s USING (source_id)
)
SELECT p.*,
    CASE
        WHEN count(e.source_id) = 0 THEN 'missing_evidence'
        WHEN count(*) FILTER (WHERE evidence_state = 'not_yet_reviewed') > 0 THEN 'not_yet_reviewed'
        WHEN count(*) FILTER (WHERE evidence_state = 'needs_review') > 0 THEN 'needs_review'
        ELSE 'within_review_interval'
    END AS evidence_state
FROM selected p LEFT JOIN dated_evidence e USING (step_id)
GROUP BY ALL
ORDER BY sort_order, step_id;
