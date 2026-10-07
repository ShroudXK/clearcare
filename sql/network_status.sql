-- Exact provider + facility + plan matching. Missing, old, future, or conflicting data stays unknown.
-- $allow_synthetic is False in all generated user guides.
WITH latest_per_source AS (
    SELECT o.*, s.reviewed_on, s.review_interval_days,
        dense_rank() OVER (
            PARTITION BY o.evidence_channel, o.is_synthetic
            ORDER BY o.observed_on DESC
        ) AS date_rank
    FROM network_observations o
    JOIN plan_versions p USING (plan_id)
    LEFT JOIN sources s USING (source_id)
    WHERE o.facility_id = $facility_id AND o.provider_key = $provider_key
      AND o.plan_id = $plan_id AND o.observed_on <= $as_of::DATE
      AND p.effective_from <= $as_of::DATE AND p.effective_to >= $as_of::DATE
      AND (NOT o.is_synthetic OR $allow_synthetic)
      AND (NOT p.is_synthetic OR $allow_synthetic)
), usable AS (
    SELECT * FROM latest_per_source
    WHERE date_rank = 1 AND valid_until >= $as_of::DATE
      AND date_diff('day', observed_on, $as_of::DATE) <= 30
      AND (is_synthetic OR (
          reviewed_on <= $as_of::DATE AND
          date_diff('day', reviewed_on, $as_of::DATE) <= review_interval_days
      ))
)
SELECT
    CASE
        WHEN count(*) = 0 THEN 'unknown'
        WHEN count(DISTINCT status) > 1 THEN 'conflicting'
        WHEN min(status) = 'in_network' THEN 'observed_in_network'
        WHEN min(status) = 'out_of_network' THEN 'observed_out_of_network'
        ELSE 'unknown'
    END AS network_status,
    count(*) AS usable_observations,
    coalesce(bool_or(is_synthetic), FALSE) AS contains_synthetic,
    FALSE AS coverage_confirmed
FROM usable;
