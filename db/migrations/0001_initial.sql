BEGIN;

CREATE SCHEMA IF NOT EXISTS private;
REVOKE ALL ON SCHEMA private FROM public, anon, authenticated;
GRANT USAGE ON SCHEMA private TO service_role;

CREATE DOMAIN public.ulid AS text
CHECK (value ~ '^[0-7][0-9A-HJKMNP-TV-Z]{25}$');

CREATE TYPE public.app_role AS ENUM ('learner', 'moderator', 'admin', 'owner');
CREATE TYPE public.difficulty AS ENUM ('easy', 'mid', 'hard');
CREATE TYPE public.content_state AS ENUM ('draft', 'validated', 'approved', 'published', 'retired');
CREATE TYPE public.job_state AS ENUM ('pending', 'leased', 'succeeded', 'failed');
CREATE TYPE public.moderation_state AS ENUM ('held', 'approved', 'rejected');
CREATE TYPE public.decision_state AS ENUM ('satisfied', 'not_met');

CREATE TABLE public.users (
    id public.ulid PRIMARY KEY,
    auth_user_id uuid NOT NULL UNIQUE REFERENCES auth.users (id) ON DELETE CASCADE,
    display_name text NOT NULL CHECK (char_length(display_name) BETWEEN 1 AND 64),
    locale text NOT NULL DEFAULT 'en' CHECK (locale IN ('en', 'ja', 'zh-CN', 'ko', 'es', 'pt-BR')),
    theme text NOT NULL DEFAULT 'system' CHECK (theme IN ('system', 'light', 'dark')),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE public.provider_identities (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id public.ulid NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
    issuer text NOT NULL CHECK (issuer IN ('google', 'github')),
    subject text NOT NULL CHECK (subject <> ''),
    verified_at timestamptz NOT NULL,
    UNIQUE (issuer, subject), UNIQUE (user_id, issuer)
);
CREATE TABLE public.age_declarations (
    user_id public.ulid PRIMARY KEY REFERENCES public.users (id) ON DELETE CASCADE,
    is_at_least_16 boolean NOT NULL CHECK (is_at_least_16),
    declared_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE public.policy_versions (
    id public.ulid PRIMARY KEY,
    kind text NOT NULL CHECK (kind IN ('terms', 'privacy', 'community')),
    version integer NOT NULL CHECK (version > 0),
    content_digest text NOT NULL CHECK (content_digest ~ '^[0-9a-f]{64}$'),
    content_en text NOT NULL CHECK (content_en <> ''),
    required_from timestamptz NOT NULL,
    UNIQUE (kind, version)
);
CREATE TABLE public.policy_acknowledgements (
    user_id public.ulid NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
    policy_version_id public.ulid NOT NULL REFERENCES public.policy_versions (
        id
    ) ON DELETE RESTRICT,
    acknowledged_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, policy_version_id)
);
CREATE TABLE public.role_grants (
    user_id public.ulid NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
    role public.app_role NOT NULL,
    granted_by public.ulid REFERENCES public.users (id) ON DELETE SET NULL,
    reason text NOT NULL CHECK (char_length(reason) BETWEEN 1 AND 500),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, role)
);
CREATE TABLE public.entitlements (
    id public.ulid PRIMARY KEY,
    user_id public.ulid NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
    kind text NOT NULL CHECK (kind IN ('premium')),
    source text NOT NULL CHECK (source IN ('admin', 'sandbox_billing')),
    valid_from timestamptz NOT NULL,
    valid_until timestamptz,
    revoked_at timestamptz,
    CHECK (valid_until IS NULL OR valid_until > valid_from)
);
CREATE INDEX entitlements_active_idx ON public.entitlements (
    user_id, kind, valid_from, valid_until
);

CREATE TABLE public.problems (
    id public.ulid PRIMARY KEY,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE public.problem_versions (
    id public.ulid PRIMARY KEY,
    problem_id public.ulid NOT NULL REFERENCES public.problems (id) ON DELETE RESTRICT,
    version integer NOT NULL CHECK (version > 0),
    title text NOT NULL CHECK (char_length(title) BETWEEN 1 AND 200),
    statement_en text NOT NULL CHECK (statement_en <> ''),
    official_solution jsonb NOT NULL CHECK (jsonb_typeof(official_solution) = 'object'),
    explanation_en text NOT NULL CHECK (explanation_en <> ''),
    difficulty public.difficulty NOT NULL,
    genre text NOT NULL CHECK (genre <> ''),
    input_format text NOT NULL CHECK (input_format IN ('gui', 'mermaid', 'ddl', 'dbml', 'mixed')),
    tags text [] NOT NULL DEFAULT '{}',
    normalized_hash text NOT NULL CHECK (normalized_hash ~ '^[0-9a-f]{64}$'),
    state public.content_state NOT NULL DEFAULT 'draft',
    frozen_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (problem_id, version), UNIQUE (id, problem_id), UNIQUE (normalized_hash),
    CHECK ((state IN ('approved', 'published', 'retired')) = (frozen_at IS NOT NULL))
);
CREATE INDEX problem_versions_library_idx ON public.problem_versions (
    difficulty, genre, state, created_at DESC
);
CREATE INDEX problem_versions_tags_idx ON public.problem_versions USING gin (tags);
CREATE INDEX problem_versions_search_idx ON public.problem_versions USING gin (
    to_tsvector('english', title || ' ' || statement_en)
);
CREATE TABLE public.rubric_items (
    id public.ulid PRIMARY KEY,
    problem_version_id public.ulid NOT NULL REFERENCES public.problem_versions (
        id
    ) ON DELETE RESTRICT,
    ordinal integer NOT NULL CHECK (ordinal >= 0 AND ordinal < 2000),
    description_en text NOT NULL CHECK (description_en <> ''),
    weight integer NOT NULL CHECK (weight BETWEEN 1 AND 1000000),
    is_critical boolean NOT NULL DEFAULT FALSE,
    is_implicit boolean NOT NULL DEFAULT FALSE,
    textual_derivation text,
    evaluator_spec jsonb NOT NULL CHECK (jsonb_typeof(evaluator_spec) = 'object'),
    UNIQUE (problem_version_id, ordinal),
    CHECK (NOT (is_critical AND is_implicit)),
    CHECK (NOT is_implicit OR nullif(btrim(textual_derivation), '') IS NOT NULL)
);
CREATE TABLE public.publication_calendar (
    publication_date date PRIMARY KEY,
    problem_id public.ulid NOT NULL UNIQUE REFERENCES public.problems (id) ON DELETE RESTRICT,
    problem_version_id public.ulid NOT NULL UNIQUE REFERENCES public.problem_versions (
        id
    ) ON DELETE RESTRICT,
    published_at timestamptz NOT NULL,
    CHECK (
        published_at = publication_date::timestamp AT TIME ZONE 'Asia/Tokyo' + interval '4 hours'
    ),
    FOREIGN KEY (problem_version_id, problem_id)
    REFERENCES public.problem_versions (id, problem_id) ON DELETE RESTRICT
);

CREATE TABLE public.workspaces (
    user_id public.ulid NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
    problem_id public.ulid NOT NULL REFERENCES public.problems (id) ON DELETE CASCADE,
    canonical_schema jsonb NOT NULL CHECK (jsonb_typeof(canonical_schema) = 'object'),
    editor_sources jsonb NOT NULL DEFAULT '{}' CHECK (jsonb_typeof(editor_sources) = 'object'),
    layout jsonb NOT NULL DEFAULT '{}' CHECK (jsonb_typeof(layout) = 'object'),
    revision bigint NOT NULL DEFAULT 1 CHECK (revision > 0),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, problem_id)
);
CREATE TABLE public.submissions (
    id public.ulid PRIMARY KEY,
    user_id public.ulid NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
    problem_id public.ulid NOT NULL REFERENCES public.problems (id) ON DELETE RESTRICT,
    problem_version_id public.ulid NOT NULL REFERENCES public.problem_versions (
        id
    ) ON DELETE RESTRICT,
    idempotency_key uuid NOT NULL,
    request_digest text NOT NULL CHECK (request_digest ~ '^[0-9a-f]{64}$'),
    canonical_schema jsonb NOT NULL CHECK (jsonb_typeof(canonical_schema) = 'object'),
    assessment_snapshot jsonb NOT NULL CHECK (jsonb_typeof(assessment_snapshot) = 'object'),
    engine_version text NOT NULL CHECK (engine_version <> ''),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, idempotency_key), UNIQUE (id, user_id),
    UNIQUE (id, problem_id), UNIQUE (id, problem_version_id),
    FOREIGN KEY (problem_version_id, problem_id)
    REFERENCES public.problem_versions (id, problem_id) ON DELETE RESTRICT
);
CREATE INDEX submissions_dashboard_idx ON public.submissions (user_id, problem_id, created_at DESC);
CREATE TABLE public.submission_results (
    submission_id public.ulid PRIMARY KEY REFERENCES public.submissions (id) ON DELETE CASCADE,
    user_id public.ulid NOT NULL,
    problem_version_id public.ulid NOT NULL,
    satisfied_weight bigint NOT NULL CHECK (satisfied_weight >= 0),
    total_weight bigint NOT NULL CHECK (total_weight > 0 AND satisfied_weight <= total_weight),
    passed boolean NOT NULL,
    has_contradiction boolean NOT NULL,
    confidence numeric(5, 2) NOT NULL CHECK (confidence BETWEEN 0 AND 100),
    jev_version text NOT NULL CHECK (jev_version <> ''),
    static_output jsonb NOT NULL CHECK (jsonb_typeof(static_output) = 'object'),
    jev_output jsonb NOT NULL CHECK (jsonb_typeof(jev_output) = 'object'),
    finalized_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (submission_id, user_id) REFERENCES public.submissions (
        id, user_id
    ) ON DELETE CASCADE,
    FOREIGN KEY (submission_id, problem_version_id) REFERENCES public.submissions (
        id, problem_version_id
    ) ON DELETE CASCADE
);
CREATE INDEX submission_results_passed_idx ON public.submission_results (
    user_id, passed, finalized_at DESC
);
CREATE TABLE public.requirement_results (
    submission_id public.ulid NOT NULL REFERENCES public.submission_results (
        submission_id
    ) ON DELETE CASCADE,
    rubric_item_id public.ulid NOT NULL REFERENCES public.rubric_items (id) ON DELETE RESTRICT,
    decision public.decision_state NOT NULL,
    source text NOT NULL CHECK (source IN ('static', 'jev')),
    confidence numeric(5, 2) CHECK (
        (source = 'static' AND confidence IS NULL)
        OR (source = 'jev' AND confidence IS NOT NULL AND confidence BETWEEN 0 AND 100)
    ),
    impact text NOT NULL CHECK (impact <> ''),
    PRIMARY KEY (submission_id, rubric_item_id)
);

CREATE TABLE public.feedback_versions (
    id public.ulid PRIMARY KEY,
    submission_id public.ulid NOT NULL REFERENCES public.submissions (id) ON DELETE CASCADE,
    user_id public.ulid NOT NULL,
    version integer NOT NULL CHECK (version > 0),
    content_en text NOT NULL CHECK (content_en <> ''),
    model_version text NOT NULL CHECK (model_version <> ''),
    created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (submission_id, user_id) REFERENCES public.submissions (
        id, user_id
    ) ON DELETE CASCADE,
    UNIQUE (submission_id, version)
);
CREATE TABLE public.translation_cache (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    content_kind text NOT NULL,
    content_id public.ulid NOT NULL,
    content_version integer NOT NULL CHECK (content_version > 0),
    locale text NOT NULL CHECK (locale IN ('ja', 'zh-CN', 'ko', 'es', 'pt-BR')),
    owner_user_id public.ulid REFERENCES public.users (id) ON DELETE CASCADE,
    source_digest text NOT NULL CHECK (source_digest ~ '^[0-9a-f]{64}$'),
    translated_text text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE NULLS NOT DISTINCT (content_kind, content_id, content_version, locale, owner_user_id)
);
CREATE TABLE public.posts (
    id public.ulid PRIMARY KEY,
    submission_id public.ulid NOT NULL UNIQUE REFERENCES public.submission_results (
        submission_id
    ) ON DELETE CASCADE,
    author_user_id public.ulid NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
    explanation text NOT NULL CHECK (char_length(explanation) BETWEEN 1 AND 10000),
    schema_snapshot jsonb NOT NULL CHECK (jsonb_typeof(schema_snapshot) = 'object'),
    moderation_state public.moderation_state NOT NULL DEFAULT 'held',
    published_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK ((moderation_state = 'approved') = (published_at IS NOT NULL))
);
CREATE TABLE public.moderation_decisions (
    id public.ulid PRIMARY KEY,
    post_id public.ulid NOT NULL REFERENCES public.posts (id) ON DELETE CASCADE,
    state public.moderation_state NOT NULL,
    jev_version text NOT NULL,
    evidence jsonb NOT NULL CHECK (jsonb_typeof(evidence) = 'object'),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE public.reports (
    id public.ulid PRIMARY KEY,
    reporter_user_id public.ulid NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
    category text NOT NULL CHECK (
        category IN ('problem', 'official_answer', 'grading', 'translation', 'other')
    ),
    target_id public.ulid NOT NULL,
    description text NOT NULL CHECK (char_length(description) BETWEEN 1 AND 5000),
    state text NOT NULL DEFAULT 'open' CHECK (state IN ('open', 'valid', 'invalid', 'resolved')),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE public.notices (
    id public.ulid PRIMARY KEY,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE public.notice_versions (
    id public.ulid PRIMARY KEY,
    notice_id public.ulid NOT NULL REFERENCES public.notices (id) ON DELETE CASCADE,
    version integer NOT NULL CHECK (version > 0),
    title_en text NOT NULL,
    body_en text NOT NULL,
    target_digest text NOT NULL CHECK (target_digest ~ '^[0-9a-f]{64}$'),
    state public.content_state NOT NULL DEFAULT 'draft',
    published_at timestamptz,
    UNIQUE (notice_id, version),
    CHECK ((state = 'published') = (published_at IS NOT NULL))
);
CREATE TABLE public.notice_reads (
    user_id public.ulid NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
    notice_version_id public.ulid NOT NULL REFERENCES public.notice_versions (id) ON DELETE CASCADE,
    read_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, notice_version_id)
);
CREATE TABLE public.admin_approvals (
    id public.ulid PRIMARY KEY,
    actor_user_id public.ulid REFERENCES public.users (id) ON DELETE SET NULL,
    action text NOT NULL CHECK (action IN ('correction', 'notice')),
    target_id public.ulid NOT NULL,
    target_digest text NOT NULL CHECK (target_digest ~ '^[0-9a-f]{64}$'),
    reason text NOT NULL CHECK (reason <> ''),
    approved_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (action, target_id, target_digest)
);

CREATE TABLE private.identity_allowlist (
    id public.ulid PRIMARY KEY,
    issuer text NOT NULL CHECK (issuer IN ('google', 'github')),
    subject text,
    verified_email_hash text,
    bound_at timestamptz,
    disabled_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (subject IS NOT NULL OR verified_email_hash IS NOT NULL),
    CHECK (subject IS NULL OR subject <> ''),
    CHECK (verified_email_hash IS NULL OR verified_email_hash ~ '^[0-9a-f]{64}$'),
    CHECK (bound_at IS NULL OR subject IS NOT NULL)
);
CREATE UNIQUE INDEX identity_allowlist_subject_idx
ON private.identity_allowlist (issuer, subject) WHERE subject IS NOT NULL;
CREATE UNIQUE INDEX identity_allowlist_email_idx
ON private.identity_allowlist (issuer, verified_email_hash)
WHERE verified_email_hash IS NOT NULL;
CREATE TABLE private.sessions (
    id public.ulid PRIMARY KEY,
    user_id public.ulid NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
    token_hash text NOT NULL UNIQUE,
    expires_at timestamptz NOT NULL,
    revoked_at timestamptz,
    mfa_authenticated_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE private.oauth_attempts (
    state_hash text PRIMARY KEY,
    provider text NOT NULL CHECK (provider IN ('google', 'github')),
    pkce_verifier_ciphertext bytea NOT NULL,
    redirect_uri text NOT NULL,
    expires_at timestamptz NOT NULL,
    consumed_at timestamptz
);
CREATE TABLE private.idempotency_records (
    user_id public.ulid NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
    operation text NOT NULL,
    key uuid NOT NULL,
    request_digest text NOT NULL,
    response_status integer,
    response_body jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, operation, key)
);
CREATE TABLE private.ad_reward_attempts (
    id public.ulid PRIMARY KEY,
    user_id public.ulid NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
    provider_attempt_id text UNIQUE,
    state text NOT NULL CHECK (
        state IN ('pending', 'verified', 'consumed', 'failed', 'no_fill', 'blocked')
    ),
    verified_at timestamptz,
    consumed_at timestamptz,
    CHECK (consumed_at IS NULL OR verified_at IS NOT NULL),
    UNIQUE (id, user_id)
);
CREATE TABLE private.feedback_requests (
    id public.ulid PRIMARY KEY,
    user_id public.ulid NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
    problem_id public.ulid NOT NULL REFERENCES public.problems (id) ON DELETE CASCADE,
    submission_id public.ulid NOT NULL,
    reward_attempt_id public.ulid UNIQUE,
    operation_key uuid NOT NULL,
    state public.job_state NOT NULL DEFAULT 'pending',
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, operation_key),
    FOREIGN KEY (submission_id, user_id)
    REFERENCES public.submissions (id, user_id) ON DELETE CASCADE,
    FOREIGN KEY (submission_id, problem_id)
    REFERENCES public.submissions (id, problem_id) ON DELETE CASCADE,
    FOREIGN KEY (reward_attempt_id, user_id)
    REFERENCES private.ad_reward_attempts (id, user_id) ON DELETE RESTRICT
);
CREATE TABLE private.billing_events (
    provider text NOT NULL CHECK (provider = 'sandbox'),
    provider_event_id text NOT NULL,
    payload_digest text NOT NULL,
    received_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (provider, provider_event_id)
);
CREATE TABLE private.jobs (
    id public.ulid PRIMARY KEY,
    owner_user_id public.ulid REFERENCES public.users (id) ON DELETE CASCADE,
    kind text NOT NULL,
    state public.job_state NOT NULL DEFAULT 'pending',
    payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    available_at timestamptz NOT NULL DEFAULT now(),
    leased_until timestamptz,
    attempts integer NOT NULL DEFAULT 0 CHECK (attempts BETWEEN 0 AND 20),
    last_error_code text
);
CREATE INDEX jobs_poll_idx ON private.jobs (state, available_at) WHERE state IN (
    'pending', 'leased'
);
CREATE TABLE private.outbox (
    id public.ulid PRIMARY KEY,
    topic text NOT NULL,
    deduplication_key text NOT NULL UNIQUE,
    payload jsonb NOT NULL,
    delivered_at timestamptz,
    attempts integer NOT NULL DEFAULT 0 CHECK (attempts BETWEEN 0 AND 20),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE private.admin_audit (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    actor_user_id public.ulid REFERENCES public.users (id) ON DELETE SET NULL,
    action text NOT NULL,
    target_kind text NOT NULL,
    target_id text NOT NULL,
    reason text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE private.deletion_ledger (
    auth_subject_hash text PRIMARY KEY,
    deleted_at timestamptz NOT NULL,
    expires_at timestamptz NOT NULL,
    CHECK (expires_at > deleted_at)
);
CREATE TABLE private.publication_events (
    publication_date date PRIMARY KEY REFERENCES public.publication_calendar (
        publication_date
    ) ON DELETE RESTRICT,
    owner_email_outbox_id public.ulid UNIQUE REFERENCES private.outbox (id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE OR REPLACE FUNCTION public.current_user_id() RETURNS public.ulid
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, pg_temp
AS $$ SELECT u.id FROM public.users AS u WHERE u.auth_user_id = auth.uid() $$;
REVOKE ALL ON FUNCTION public.current_user_id() FROM public;
GRANT EXECUTE ON FUNCTION public.current_user_id() TO authenticated, service_role;
CREATE OR REPLACE FUNCTION public.has_active_premium() RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, pg_temp
AS $$ SELECT EXISTS (SELECT 1 FROM public.entitlements AS e WHERE e.user_id = public.current_user_id() AND e.kind = 'premium' AND e.valid_from <= now() AND (e.valid_until IS NULL OR e.valid_until > now()) AND e.revoked_at IS NULL) $$;
REVOKE ALL ON FUNCTION public.has_active_premium() FROM public;
GRANT EXECUTE ON FUNCTION public.has_active_premium() TO authenticated, service_role;
CREATE OR REPLACE FUNCTION public.can_learn() RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, pg_temp
AS $$
 SELECT EXISTS (
   SELECT 1 FROM public.users u
   JOIN public.age_declarations a ON a.user_id = u.id AND a.is_at_least_16
   JOIN public.provider_identities pi ON pi.user_id = u.id
      AND pi.verified_at IS NOT NULL
   JOIN private.identity_allowlist al ON al.issuer = pi.issuer
      AND al.subject = pi.subject AND al.disabled_at IS NULL
   WHERE u.auth_user_id = auth.uid()
 ) AND NOT EXISTS (
   SELECT 1 FROM (
     SELECT DISTINCT ON (pv.kind) pv.id
     FROM public.policy_versions pv
     WHERE pv.required_from <= now()
     ORDER BY pv.kind, pv.version DESC, pv.required_from DESC
   ) latest
   WHERE NOT EXISTS (
     SELECT 1 FROM public.policy_acknowledgements pa
     WHERE pa.user_id = public.current_user_id()
       AND pa.policy_version_id = latest.id
   )
 )
$$;
REVOKE ALL ON FUNCTION public.can_learn() FROM public;
GRANT EXECUTE ON FUNCTION public.can_learn() TO authenticated, service_role;

CREATE OR REPLACE FUNCTION private.reject_mutation() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog, pg_temp AS $$
BEGIN
 IF TG_OP = 'DELETE' AND current_setting('app.account_deletion', true) = 'on' THEN RETURN OLD; END IF;
 RAISE EXCEPTION 'immutable record';
END $$;
CREATE OR REPLACE FUNCTION private.protect_problem_version() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog, pg_temp AS $$
BEGIN
 IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'frozen problem version is immutable'; END IF;
 IF to_jsonb(NEW) - 'state' IS DISTINCT FROM to_jsonb(OLD) - 'state' OR
    NOT ((OLD.state = 'approved' AND NEW.state IN ('published','retired')) OR
         (OLD.state = 'published' AND NEW.state = 'retired')) THEN
   RAISE EXCEPTION 'frozen problem version is immutable';
 END IF;
 RETURN NEW;
END $$;
CREATE OR REPLACE FUNCTION private.protect_post() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog, pg_temp AS $$
BEGIN
 IF TG_OP = 'DELETE' THEN
   IF current_setting('app.account_deletion', true) = 'on' THEN RETURN OLD; END IF;
   RAISE EXCEPTION 'post is immutable';
 END IF;
 IF to_jsonb(NEW) - ARRAY['moderation_state','published_at'] IS DISTINCT FROM
    to_jsonb(OLD) - ARRAY['moderation_state','published_at'] OR
    NOT ((OLD.moderation_state = 'held' AND NEW.moderation_state IN ('approved','rejected')) OR
         (OLD.moderation_state = 'approved' AND NEW.moderation_state = 'rejected')) THEN
   RAISE EXCEPTION 'post content is immutable';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER problem_version_immutable BEFORE UPDATE OR DELETE ON public.problem_versions FOR EACH ROW WHEN (
    old.frozen_at IS NOT NULL
) EXECUTE FUNCTION private.protect_problem_version();
CREATE OR REPLACE FUNCTION private.validate_problem_freeze() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog, pg_temp AS $$
BEGIN
 IF TG_OP = 'INSERT' AND NEW.frozen_at IS NOT NULL THEN
   RAISE EXCEPTION 'problem versions must be inserted unfrozen';
 END IF;
 IF TG_OP = 'UPDATE' AND OLD.frozen_at IS NULL AND NEW.frozen_at IS NOT NULL AND NOT EXISTS (
   SELECT 1 FROM public.rubric_items ri WHERE ri.problem_version_id = NEW.id
 ) THEN RAISE EXCEPTION 'a frozen problem version requires rubric items'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER problem_freeze_valid BEFORE INSERT OR UPDATE ON public.problem_versions
FOR EACH ROW EXECUTE FUNCTION private.validate_problem_freeze();
CREATE OR REPLACE FUNCTION private.protect_rubric() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog, pg_temp AS $$
DECLARE version_id public.ulid; frozen_at_value timestamptz;
BEGIN
 IF TG_OP = 'UPDATE' AND OLD.problem_version_id <> NEW.problem_version_id THEN
   RAISE EXCEPTION 'rubric items cannot move between versions';
 END IF;
 version_id := CASE WHEN TG_OP = 'DELETE' THEN OLD.problem_version_id ELSE NEW.problem_version_id END;
 SELECT pv.frozen_at INTO frozen_at_value FROM public.problem_versions pv
 WHERE pv.id = version_id FOR UPDATE;
 IF frozen_at_value IS NOT NULL THEN RAISE EXCEPTION 'frozen rubric is immutable'; END IF;
 RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
END $$;
CREATE TRIGGER rubric_immutable BEFORE INSERT OR UPDATE OR DELETE ON public.rubric_items FOR EACH ROW EXECUTE FUNCTION private.protect_rubric();
CREATE TRIGGER submission_immutable BEFORE UPDATE OR DELETE ON public.submissions FOR EACH ROW EXECUTE FUNCTION private.reject_mutation();
CREATE TRIGGER result_immutable BEFORE UPDATE OR DELETE ON public.submission_results FOR EACH ROW EXECUTE FUNCTION private.reject_mutation();
CREATE TRIGGER requirement_result_immutable BEFORE UPDATE OR DELETE ON public.requirement_results FOR EACH ROW EXECUTE FUNCTION private.reject_mutation();
CREATE TRIGGER post_immutable BEFORE UPDATE OR DELETE ON public.posts FOR EACH ROW EXECUTE FUNCTION private.protect_post();

CREATE OR REPLACE FUNCTION private.protect_workspace_update() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog, pg_temp AS $$
BEGIN
 IF NEW.user_id IS DISTINCT FROM OLD.user_id OR NEW.problem_id IS DISTINCT FROM OLD.problem_id THEN
   RAISE EXCEPTION 'workspace identity is immutable';
 END IF;
 IF NEW.updated_at IS DISTINCT FROM OLD.updated_at THEN
   RAISE EXCEPTION 'workspace updated_at is server managed';
 END IF;
 IF NEW.revision <> OLD.revision + 1 THEN
   RAISE EXCEPTION 'workspace revision must increment by one';
 END IF;
 NEW.updated_at := clock_timestamp();
 RETURN NEW;
END $$;
CREATE TRIGGER workspace_update_guard BEFORE UPDATE ON public.workspaces
FOR EACH ROW EXECUTE FUNCTION private.protect_workspace_update();

CREATE OR REPLACE FUNCTION private.validate_submission() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog, pg_temp AS $$
DECLARE eligible boolean;
BEGIN
 SELECT pv.frozen_at IS NOT NULL AND pv.state IN ('published','retired')
   AND EXISTS (SELECT 1 FROM public.publication_calendar pc
               WHERE pc.problem_id = pv.problem_id AND pc.published_at <= now())
 INTO eligible FROM public.problem_versions pv
 WHERE pv.id = NEW.problem_version_id AND pv.problem_id = NEW.problem_id FOR SHARE;
 IF eligible IS DISTINCT FROM true THEN RAISE EXCEPTION 'submission version is not published and frozen'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER submission_eligible BEFORE INSERT ON public.submissions
FOR EACH ROW EXECUTE FUNCTION private.validate_submission();

CREATE OR REPLACE FUNCTION private.validate_result() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog, pg_temp AS $$
DECLARE expected_total bigint; expected_satisfied bigint; missing_count integer; critical_missing integer;
BEGIN
 SELECT sum(r.weight), sum(r.weight) FILTER (WHERE rr.decision = 'satisfied'), count(*) FILTER (WHERE rr.rubric_item_id IS NULL), count(*) FILTER (WHERE r.is_critical AND rr.decision <> 'satisfied')
 INTO expected_total, expected_satisfied, missing_count, critical_missing
 FROM public.rubric_items r LEFT JOIN public.requirement_results rr ON rr.rubric_item_id = r.id AND rr.submission_id = NEW.submission_id
 WHERE r.problem_version_id = NEW.problem_version_id;
 IF expected_total IS NULL OR missing_count <> 0 OR expected_total <> NEW.total_weight OR coalesce(expected_satisfied, 0) <> NEW.satisfied_weight OR NEW.passed <> (critical_missing = 0 AND NOT NEW.has_contradiction) THEN RAISE EXCEPTION 'invalid assessment aggregate'; END IF;
 RETURN NEW;
END $$;
CREATE CONSTRAINT TRIGGER result_complete AFTER INSERT ON public.submission_results DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION private.validate_result();
CREATE OR REPLACE FUNCTION private.validate_requirement_result() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog, pg_temp AS $$
BEGIN IF NOT EXISTS (SELECT 1 FROM public.submission_results sr JOIN public.rubric_items ri ON ri.problem_version_id = sr.problem_version_id WHERE sr.submission_id = NEW.submission_id AND ri.id = NEW.rubric_item_id) THEN RAISE EXCEPTION 'rubric item does not belong to submitted version'; END IF; RETURN NEW; END $$;
CREATE CONSTRAINT TRIGGER requirement_belongs AFTER INSERT ON public.requirement_results DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION private.validate_requirement_result();
CREATE OR REPLACE FUNCTION private.validate_post() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog, pg_temp AS $$
BEGIN IF NOT EXISTS (SELECT 1 FROM public.submission_results sr JOIN public.submissions s ON s.id = sr.submission_id WHERE sr.submission_id = NEW.submission_id AND s.user_id = NEW.author_user_id AND sr.satisfied_weight = sr.total_weight AND NEW.schema_snapshot = s.canonical_schema) THEN RAISE EXCEPTION 'only owned exact-full results may be posted'; END IF; RETURN NEW; END $$;
CREATE TRIGGER post_exact_full BEFORE INSERT ON public.posts FOR EACH ROW EXECUTE FUNCTION private.validate_post();
CREATE OR REPLACE FUNCTION private.validate_publication() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog, pg_temp AS $$
BEGIN
 IF TG_OP = 'UPDATE' AND (NEW.publication_date <> OLD.publication_date OR NEW.problem_id <> OLD.problem_id OR NEW.published_at <> OLD.published_at) THEN RAISE EXCEPTION 'publication identity is immutable'; END IF;
 IF NOT EXISTS (SELECT 1 FROM public.problem_versions pv WHERE pv.id = NEW.problem_version_id AND pv.problem_id = NEW.problem_id AND pv.state IN ('approved','published') AND pv.frozen_at IS NOT NULL) THEN RAISE EXCEPTION 'version is not publication eligible'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER publication_valid BEFORE INSERT OR UPDATE ON public.publication_calendar FOR EACH ROW EXECUTE FUNCTION private.validate_publication();

DO $$ DECLARE t text; BEGIN
 FOR t IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t); EXECUTE format('ALTER TABLE public.%I FORCE ROW LEVEL SECURITY', t); EXECUTE format('REVOKE ALL ON public.%I FROM PUBLIC, anon, authenticated', t); END LOOP;
END $$;
GRANT SELECT, UPDATE (display_name, locale, theme, updated_at) ON public.users TO authenticated;
CREATE POLICY users_self_select ON public.users FOR SELECT TO authenticated USING (
    auth_user_id = auth.uid()
);
CREATE POLICY users_self_update ON public.users FOR UPDATE TO authenticated USING (
    auth_user_id = auth.uid()
) WITH CHECK (auth_user_id = auth.uid());
GRANT SELECT ON public.problems,
public.problem_versions,
public.rubric_items,
public.publication_calendar,
public.policy_versions,
public.notice_versions TO authenticated;
CREATE POLICY problems_member_read ON public.problems FOR SELECT TO authenticated USING (
    public.can_learn() AND EXISTS (
        SELECT 1
        FROM public.publication_calendar AS pc
        WHERE
            pc.problem_id = problems.id
            AND pc.published_at <= now()
    )
);
CREATE POLICY problem_versions_member_read ON public.problem_versions FOR SELECT TO authenticated USING (
    state IN ('published', 'retired') AND public.can_learn() AND EXISTS (
        SELECT 1
        FROM public.publication_calendar AS pc
        WHERE
            pc.problem_id = problem_versions.problem_id
            AND pc.published_at <= now()
            AND (state = 'retired' OR pc.problem_version_id = problem_versions.id)
    )
);
CREATE POLICY rubric_member_read ON public.rubric_items FOR SELECT TO authenticated USING (
    EXISTS (
        SELECT 1
        FROM public.problem_versions AS pv
        WHERE
            pv.id = rubric_items.problem_version_id
            AND pv.state IN ('published', 'retired')
            AND EXISTS (
                SELECT 1
                FROM public.publication_calendar AS pc
                WHERE
                    pc.problem_id = pv.problem_id
                    AND pc.published_at <= now()
                    AND (pv.state = 'retired' OR pc.problem_version_id = pv.id)
            )
    ) AND public.can_learn()
);
CREATE POLICY publication_member_read ON public.publication_calendar FOR SELECT TO authenticated USING (
    public.can_learn()
);
CREATE POLICY policy_versions_member_read ON public.policy_versions FOR SELECT TO authenticated USING (
    public.current_user_id() IS NOT NULL
);
CREATE POLICY notice_versions_member_read ON public.notice_versions FOR SELECT TO authenticated USING (
    state = 'published' AND public.can_learn()
);
GRANT SELECT ON public.submissions,
public.submission_results,
public.requirement_results,
public.feedback_versions,
public.posts,
public.notice_reads,
public.reports,
public.workspaces,
public.entitlements TO authenticated;
CREATE POLICY submissions_owner_read ON public.submissions FOR SELECT TO authenticated USING (
    user_id = public.current_user_id() AND public.can_learn()
);
CREATE POLICY results_owner_read ON public.submission_results FOR SELECT TO authenticated USING (
    user_id = public.current_user_id() AND public.can_learn()
);
CREATE POLICY requirement_results_owner_read ON public.requirement_results FOR SELECT TO authenticated USING (
    EXISTS (
        SELECT 1 FROM public.submission_results AS sr
        WHERE
            sr.submission_id = requirement_results.submission_id
            AND sr.user_id = public.current_user_id()
            AND public.can_learn()
    )
);
CREATE POLICY feedback_owner_read ON public.feedback_versions FOR SELECT TO authenticated USING (
    user_id = public.current_user_id() AND public.can_learn()
);
CREATE POLICY entitlements_owner_read ON public.entitlements FOR SELECT TO authenticated USING (
    user_id = public.current_user_id() AND public.can_learn()
);
CREATE POLICY workspaces_owner_read ON public.workspaces FOR SELECT TO authenticated USING (
    user_id = public.current_user_id() AND public.has_active_premium() AND public.can_learn()
);
CREATE POLICY reports_owner_read ON public.reports FOR SELECT TO authenticated USING (
    reporter_user_id = public.current_user_id() AND public.can_learn()
);
CREATE POLICY notice_reads_owner_read ON public.notice_reads FOR SELECT TO authenticated USING (
    user_id = public.current_user_id() AND public.can_learn()
);
CREATE POLICY posts_member_read ON public.posts FOR SELECT TO authenticated USING (
    moderation_state = 'approved' AND public.can_learn()
);

GRANT INSERT (user_id, problem_id, canonical_schema, editor_sources, layout)
ON public.workspaces TO authenticated;
GRANT UPDATE (canonical_schema, editor_sources, layout, revision)
ON public.workspaces TO authenticated;
CREATE POLICY workspaces_premium_insert ON public.workspaces FOR INSERT TO authenticated WITH CHECK (
    user_id = public.current_user_id() AND public.has_active_premium() AND public.can_learn()
);
CREATE POLICY workspaces_premium_update ON public.workspaces FOR UPDATE TO authenticated USING (
    user_id = public.current_user_id() AND public.has_active_premium()
) WITH CHECK (
    user_id = public.current_user_id() AND public.has_active_premium() AND public.can_learn()
);
GRANT SELECT, INSERT ON public.notice_reads TO authenticated;
CREATE POLICY notice_reads_owner_insert ON public.notice_reads FOR INSERT TO authenticated WITH CHECK (
    user_id = public.current_user_id()
);

GRANT ALL ON ALL TABLES IN SCHEMA public, private TO service_role;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public, private TO service_role;
COMMIT;
