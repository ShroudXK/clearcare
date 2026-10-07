-- Parent tables come first. The Python builder loads a new database in a transaction.
CREATE TABLE sources (
    source_id VARCHAR PRIMARY KEY,
    publisher VARCHAR NOT NULL,
    title VARCHAR NOT NULL,
    url VARCHAR NOT NULL CHECK (starts_with(url, 'https://')),
    format VARCHAR NOT NULL CHECK (format IN ('html', 'pdf')),
    locator VARCHAR NOT NULL,
    review_interval_days INTEGER NOT NULL CHECK (review_interval_days > 0),
    publication_note VARCHAR,
    anchors VARCHAR NOT NULL,
    reviewed_on DATE NOT NULL,
    review_method VARCHAR NOT NULL
);

CREATE TABLE facilities (
    facility_id VARCHAR PRIMARY KEY,
    name VARCHAR NOT NULL,
    care_type VARCHAR NOT NULL CHECK (care_type IN ('campus','walk_in','emergency')),
    city VARCHAR NOT NULL,
    address VARCHAR,
    phone VARCHAR,
    entry_url VARCHAR NOT NULL,
    source_id VARCHAR NOT NULL REFERENCES sources(source_id),
    scope_note VARCHAR NOT NULL
);
CREATE TABLE services (
    service_id VARCHAR PRIMARY KEY,
    name_en VARCHAR NOT NULL,
    name_zh VARCHAR NOT NULL
);
CREATE TABLE facility_services (
    facility_id VARCHAR REFERENCES facilities(facility_id),
    service_id VARCHAR REFERENCES services(service_id),
    source_id VARCHAR NOT NULL REFERENCES sources(source_id),
    scope_note VARCHAR NOT NULL,
    PRIMARY KEY (facility_id, service_id)
);
CREATE TABLE resources (
    resource_id VARCHAR PRIMARY KEY,
    scenario VARCHAR NOT NULL CHECK (scenario IN ('all','campus_visit','community_visit','fracture_followup')),
    title_en VARCHAR NOT NULL,
    title_zh VARCHAR NOT NULL,
    url VARCHAR NOT NULL,
    phone VARCHAR,
    source_id VARCHAR NOT NULL REFERENCES sources(source_id)
);
CREATE TABLE prep_steps (
    step_id VARCHAR PRIMARY KEY,
    sort_order INTEGER NOT NULL CHECK (sort_order >= 0),
    kind VARCHAR NOT NULL CHECK (kind IN ('education','action','question')),
    title_en VARCHAR NOT NULL,
    title_zh VARCHAR NOT NULL,
    body_en VARCHAR NOT NULL,
    body_zh VARCHAR NOT NULL,
    condition_key VARCHAR NOT NULL CHECK (condition_key IN (
        'always','needs_interpreter','no_insurance_card','has_prior_records',
        'no_prior_records','mckinley_referral'
    ))
);
CREATE TABLE step_applicability (
    step_id VARCHAR REFERENCES prep_steps(step_id),
    scenario VARCHAR CHECK (scenario IN ('all','campus_visit','community_visit','fracture_followup')),
    PRIMARY KEY (step_id, scenario)
);
CREATE TABLE step_sources (
    step_id VARCHAR REFERENCES prep_steps(step_id),
    source_id VARCHAR REFERENCES sources(source_id),
    PRIMARY KEY (step_id, source_id)
);
CREATE TABLE step_dependencies (
    step_id VARCHAR REFERENCES prep_steps(step_id),
    depends_on_id VARCHAR REFERENCES prep_steps(step_id),
    PRIMARY KEY (step_id, depends_on_id),
    CHECK (step_id <> depends_on_id)
);
-- These two production tables are deliberately empty until plan-specific evidence exists.
CREATE TABLE plan_versions (
    plan_id VARCHAR PRIMARY KEY,
    plan_name VARCHAR NOT NULL,
    network_name VARCHAR NOT NULL,
    effective_from DATE NOT NULL,
    effective_to DATE NOT NULL,
    is_synthetic BOOLEAN NOT NULL,
    CHECK (effective_to >= effective_from)
);
CREATE TABLE network_observations (
    observation_id VARCHAR PRIMARY KEY,
    facility_id VARCHAR NOT NULL REFERENCES facilities(facility_id),
    provider_key VARCHAR NOT NULL,
    plan_id VARCHAR NOT NULL REFERENCES plan_versions(plan_id),
    source_id VARCHAR REFERENCES sources(source_id),
    evidence_channel VARCHAR NOT NULL,
    status VARCHAR NOT NULL CHECK (status IN ('in_network','out_of_network','unknown')),
    observed_on DATE NOT NULL,
    valid_until DATE NOT NULL,
    is_synthetic BOOLEAN NOT NULL,
    CHECK (valid_until >= observed_on),
    CHECK ((is_synthetic AND source_id IS NULL) OR
           (NOT is_synthetic AND source_id IS NOT NULL AND evidence_channel = source_id))
);
CREATE TABLE dataset_meta (
    dataset_version VARCHAR NOT NULL,
    input_sha256 VARCHAR NOT NULL,
    source_review_date DATE NOT NULL
);
