from typing import Any

import psycopg
import pytest


def test_database_is_real_postgresql(db: psycopg.Connection[Any]) -> None:
    version = db.execute("SELECT version()").fetchone()
    assert version is not None and "PostgreSQL" in version[0]


def test_all_application_tables_enforce_rls(db: psycopg.Connection[Any]) -> None:
    rows = db.execute(
        """
        SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity
        FROM pg_class AS c
        JOIN pg_namespace AS n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind = 'r'
        """
    ).fetchall()
    assert len(rows) >= 15, "Migration did not create the domain model"
    assert all(enabled and forced for _, enabled, forced in rows), rows


def test_anonymous_cannot_read_application_tables(
    db: psycopg.Connection[Any],
) -> None:
    exposed = db.execute(
        """
        SELECT table_name FROM information_schema.role_table_grants
        WHERE grantee = 'anon' AND table_schema = 'public'
          AND privilege_type = 'SELECT'
        """
    ).fetchall()
    assert exposed == []


def test_private_schema_is_not_accessible_to_clients(
    db: psycopg.Connection[Any],
) -> None:
    for role in ("anon", "authenticated"):
        row = db.execute(
            "SELECT has_schema_privilege(%s, 'private', 'USAGE')", (role,)
        ).fetchone()
        assert row == (False,)


def test_no_publicly_executable_security_definers(
    db: psycopg.Connection[Any],
) -> None:
    exposed = db.execute(
        """
        SELECT n.nspname, p.proname
        FROM pg_proc AS p
        JOIN pg_namespace AS n ON n.oid = p.pronamespace
        CROSS JOIN LATERAL aclexplode(
          coalesce(p.proacl, acldefault('f', p.proowner))
        ) AS a
        WHERE n.nspname IN ('public', 'private') AND p.prosecdef
          AND a.grantee = 0 AND a.privilege_type = 'EXECUTE'
        """
    ).fetchall()
    assert exposed == []


def test_all_security_definers_pin_search_path(
    db: psycopg.Connection[Any],
) -> None:
    rows = db.execute(
        """
        SELECT p.proname, p.proconfig
        FROM pg_proc AS p JOIN pg_namespace AS n ON n.oid = p.pronamespace
        WHERE n.nspname IN ('public', 'private') AND p.prosecdef
        """
    ).fetchall()
    assert rows, "Expected explicit authorization helpers"
    assert all(
        config
        and any(
            setting in {'search_path=""', "search_path=pg_catalog, pg_temp"}
            for setting in config
        )
        for _, config in rows
    ), rows


def test_anonymous_private_access_fails(db: psycopg.Connection[Any]) -> None:
    with pytest.raises(psycopg.errors.InsufficientPrivilege), db.transaction():
        db.execute("SET LOCAL ROLE anon")
        db.execute("SELECT * FROM private.sessions")


USER_A = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
USER_B = "01ARZ3NDEKTSV4RRFFQ69G5FAW"
PROBLEM = "01ARZ3NDEKTSV4RRFFQ69G5FAX"
VERSION = "01ARZ3NDEKTSV4RRFFQ69G5FAY"
RUBRIC_A = "01ARZ3NDEKTSV4RRFFQ69G5FAZ"
RUBRIC_B = "01ARZ3NDEKTSV4RRFFQ69G5FB0"
SUBMISSION = "01ARZ3NDEKTSV4RRFFQ69G5FB1"
DIGEST = "a" * 64


def seed_users(db: psycopg.Connection[Any]) -> None:
    db.execute(
        "INSERT INTO auth.users(id) VALUES (%s), (%s)",
        (
            "11111111-1111-1111-1111-111111111111",
            "22222222-2222-2222-2222-222222222222",
        ),
    )
    db.execute(
        "INSERT INTO public.users(id, auth_user_id, display_name) VALUES (%s, %s, 'A'), (%s, %s, 'B')",  # noqa: E501
        (
            USER_A,
            "11111111-1111-1111-1111-111111111111",
            USER_B,
            "22222222-2222-2222-2222-222222222222",
        ),
    )


def seed_problem(db: psycopg.Connection[Any]) -> None:
    db.execute("INSERT INTO public.problems(id) VALUES (%s)", (PROBLEM,))
    db.execute(
        """INSERT INTO public.problem_versions
        (id, problem_id, version, title, statement_en, official_solution,
         explanation_en, difficulty, genre, input_format, normalized_hash,
         state, frozen_at)
        VALUES (%s, %s, 1, 'Design', 'Requirements', '{}'::jsonb,
                'Explanation', 'easy', 'oltp', 'mixed', %s, 'draft', NULL)""",
        (VERSION, PROBLEM, DIGEST),
    )
    db.execute(
        """INSERT INTO public.rubric_items
        (id, problem_version_id, ordinal, description_en, weight,
         is_critical, evaluator_spec)
        VALUES (%s, %s, 0, 'Critical entity', 3, true, '{}'::jsonb),
               (%s, %s, 1, 'Constraint', 1, false, '{}'::jsonb)""",
        (RUBRIC_A, VERSION, RUBRIC_B, VERSION),
    )
    db.execute(
        "UPDATE public.problem_versions SET state = 'approved', frozen_at = now() WHERE id = %s",  # noqa: E501
        (VERSION,),
    )


def publish_problem(db: psycopg.Connection[Any]) -> None:
    db.execute(
        "UPDATE public.problem_versions SET state = 'published' WHERE id = %s",
        (VERSION,),
    )
    db.execute(
        """INSERT INTO public.publication_calendar
        (publication_date, problem_id, problem_version_id, published_at)
        VALUES (DATE '2026-01-01', %s, %s,
                DATE '2026-01-01'::timestamp AT TIME ZONE 'Asia/Tokyo' + interval '4 hours')""",  # noqa: E501
        (PROBLEM, VERSION),
    )


def seed_submission(db: psycopg.Connection[Any]) -> None:
    publish_problem(db)
    db.execute(
        """INSERT INTO public.submissions
        (id, user_id, problem_id, problem_version_id, idempotency_key,
         request_digest, canonical_schema, assessment_snapshot, engine_version)
        VALUES (%s, %s, %s, %s, %s, %s, '{}'::jsonb, '{}'::jsonb, 'test')""",
        (
            SUBMISSION,
            USER_A,
            PROBLEM,
            VERSION,
            "33333333-3333-3333-3333-333333333333",
            DIGEST,
        ),
    )


def test_rls_isolates_two_users(db: psycopg.Connection[Any]) -> None:
    seed_users(db)
    db.execute("SET LOCAL ROLE authenticated")
    db.execute(
        "SELECT set_config('request.jwt.claim.sub', %s, true)",
        ("11111111-1111-1111-1111-111111111111",),
    )
    assert db.execute("SELECT id FROM public.users").fetchall() == [(USER_A,)]
    assert db.execute(
        "UPDATE public.users SET display_name = 'Mine' WHERE id = %s RETURNING id",
        (USER_A,),
    ).fetchone() == (USER_A,)
    assert (
        db.execute(
            "UPDATE public.users SET display_name = 'Nope' WHERE id = %s RETURNING id",
            (USER_B,),
        ).fetchone()
        is None
    )
    with pytest.raises(psycopg.errors.InsufficientPrivilege), db.transaction():
        db.execute(
            "UPDATE public.users SET auth_user_id = %s WHERE id = %s",
            ("33333333-3333-3333-3333-333333333333", USER_A),
        )


def test_server_draft_requires_current_premium(db: psycopg.Connection[Any]) -> None:
    seed_users(db)
    seed_problem(db)
    grant_learning_access(db)
    db.execute("SET LOCAL ROLE authenticated")
    db.execute(
        "SELECT set_config('request.jwt.claim.sub', %s, true)",
        ("11111111-1111-1111-1111-111111111111",),
    )
    with pytest.raises(psycopg.errors.InsufficientPrivilege), db.transaction():
        db.execute(
            "INSERT INTO public.workspaces(user_id, problem_id, canonical_schema) VALUES (%s, %s, '{}'::jsonb)",  # noqa: E501
            (USER_A, PROBLEM),
        )
    db.execute("RESET ROLE")
    db.execute(
        "INSERT INTO public.entitlements(id, user_id, kind, source, valid_from) VALUES (%s, %s, 'premium', 'admin', now())",  # noqa: E501
        ("01ARZ3NDEKTSV4RRFFQ69G5FB2", USER_A),
    )
    db.execute("SET LOCAL ROLE authenticated")
    db.execute(
        "SELECT set_config('request.jwt.claim.sub', %s, true)",
        ("11111111-1111-1111-1111-111111111111",),
    )
    db.execute(
        "INSERT INTO public.workspaces(user_id, problem_id, canonical_schema) VALUES (%s, %s, '{}'::jsonb)",  # noqa: E501
        (USER_A, PROBLEM),
    )
    assert db.execute("SELECT count(*) FROM public.workspaces").fetchone() == (1,)


def test_server_draft_read_requires_current_premium(
    db: psycopg.Connection[Any],
) -> None:
    seed_users(db)
    seed_problem(db)
    grant_learning_access(db)
    db.execute(
        "INSERT INTO public.entitlements(id, user_id, kind, source, valid_from) VALUES (%s, %s, 'premium', 'admin', now())",  # noqa: E501
        ("01ARZ3NDEKTSV4RRFFQ69G5FB2", USER_A),
    )
    db.execute("SET LOCAL ROLE authenticated")
    db.execute(
        "SELECT set_config('request.jwt.claim.sub', %s, true)",
        ("11111111-1111-1111-1111-111111111111",),
    )
    db.execute(
        "INSERT INTO public.workspaces(user_id, problem_id, canonical_schema) VALUES (%s, %s, '{}'::jsonb)",  # noqa: E501
        (USER_A, PROBLEM),
    )
    assert db.execute("SELECT problem_id FROM public.workspaces").fetchall() == [
        (PROBLEM,)
    ]
    db.execute("RESET ROLE")
    db.execute(
        "UPDATE public.entitlements SET revoked_at = now() WHERE user_id = %s",
        (USER_A,),
    )
    db.execute("SET LOCAL ROLE authenticated")
    assert db.execute("SELECT count(*) FROM public.workspaces").fetchone() == (0,)


def test_workspace_update_boundary_protects_identity_and_timestamp(
    db: psycopg.Connection[Any],
) -> None:
    seed_users(db)
    seed_problem(db)
    grant_learning_access(db)
    db.execute(
        "INSERT INTO public.entitlements(id, user_id, kind, source, valid_from) VALUES (%s, %s, 'premium', 'admin', now())",  # noqa: E501
        ("01ARZ3NDEKTSV4RRFFQ69G5FB3", USER_A),
    )
    db.execute("SET LOCAL ROLE authenticated")
    db.execute(
        "SELECT set_config('request.jwt.claim.sub', %s, true)",
        ("11111111-1111-1111-1111-111111111111",),
    )
    db.execute(
        "INSERT INTO public.workspaces(user_id, problem_id, canonical_schema) VALUES (%s, %s, '{}'::jsonb)",  # noqa: E501
        (USER_A, PROBLEM),
    )
    before = db.execute("SELECT revision, updated_at FROM public.workspaces").fetchone()
    assert before is not None
    db.execute(
        "UPDATE public.workspaces SET canonical_schema = '{\"tables\": []}'::jsonb, revision = revision + 1 WHERE user_id = %s AND problem_id = %s",  # noqa: E501
        (USER_A, PROBLEM),
    )
    after = db.execute("SELECT revision, updated_at FROM public.workspaces").fetchone()
    assert after is not None
    assert after[0] == before[0] + 1
    assert after[1] > before[1]
    for column in ("canonical_schema", "editor_sources", "layout", "revision"):
        assert db.execute(
            "SELECT has_column_privilege('authenticated', 'public.workspaces', %s, 'UPDATE')",  # noqa: E501
            (column,),
        ).fetchone() == (True,)
    for column in ("user_id", "problem_id", "updated_at"):
        assert db.execute(
            "SELECT has_column_privilege('authenticated', 'public.workspaces', %s, 'UPDATE')",  # noqa: E501
            (column,),
        ).fetchone() == (False,)
        with pytest.raises(psycopg.errors.InsufficientPrivilege), db.transaction():
            db.execute(
                f"UPDATE public.workspaces SET {column} = %s WHERE user_id = %s AND problem_id = %s",  # noqa: E501
                (
                    USER_B
                    if column == "user_id"
                    else PROBLEM
                    if column == "problem_id"
                    else before[1],
                    USER_A,
                    PROBLEM,
                ),
            )
    db.execute("RESET ROLE")
    db.execute("SET LOCAL ROLE service_role")
    with pytest.raises(psycopg.errors.RaiseException), db.transaction():
        db.execute(
            "UPDATE public.workspaces SET user_id = %s, revision = revision + 1 WHERE user_id = %s AND problem_id = %s",  # noqa: E501
            (USER_B, USER_A, PROBLEM),
        )
    with pytest.raises(psycopg.errors.RaiseException), db.transaction():
        db.execute(
            "UPDATE public.workspaces SET problem_id = %s, revision = revision + 1 WHERE user_id = %s AND problem_id = %s",  # noqa: E501
            (USER_B, USER_A, PROBLEM),
        )
    with pytest.raises(psycopg.errors.RaiseException), db.transaction():
        db.execute(
            "UPDATE public.workspaces SET updated_at = now() + interval '1 day', revision = revision + 1 WHERE user_id = %s AND problem_id = %s",  # noqa: E501
            (USER_A, PROBLEM),
        )


def test_frozen_content_and_submissions_are_immutable(
    db: psycopg.Connection[Any],
) -> None:
    seed_users(db)
    seed_problem(db)
    seed_submission(db)
    with pytest.raises(psycopg.errors.RaiseException), db.transaction():
        db.execute(
            "UPDATE public.problem_versions SET title = 'Changed' WHERE id = %s",
            (VERSION,),
        )
    with pytest.raises(psycopg.errors.RaiseException), db.transaction():
        db.execute(
            "UPDATE public.submissions SET engine_version = 'changed' WHERE id = %s",
            (SUBMISSION,),
        )


def test_result_requires_complete_exact_aggregate_and_pass_rule(
    db: psycopg.Connection[Any],
) -> None:
    seed_users(db)
    seed_problem(db)
    seed_submission(db)
    db.execute("SET CONSTRAINTS ALL DEFERRED")
    db.execute(
        "INSERT INTO public.submission_results(submission_id, user_id, problem_version_id, satisfied_weight, total_weight, passed, has_contradiction, confidence, jev_version, static_output, jev_output) VALUES (%s, %s, %s, 3, 4, true, false, 80, 'stub-v1', '{}'::jsonb, '{}'::jsonb)",  # noqa: E501
        (SUBMISSION, USER_A, VERSION),
    )
    db.execute(
        "INSERT INTO public.requirement_results(submission_id, rubric_item_id, decision, source, confidence, impact) VALUES (%s, %s, 'satisfied', 'static', NULL, 'high'), (%s, %s, 'not_met', 'jev', 80, 'low')",  # noqa: E501
        (SUBMISSION, RUBRIC_A, SUBMISSION, RUBRIC_B),
    )
    db.execute("SET CONSTRAINTS ALL IMMEDIATE")
    assert db.execute(
        "SELECT satisfied_weight, total_weight, passed FROM public.submission_results"
    ).fetchone() == (3, 4, True)


def test_result_rejects_incomplete_or_fabricated_aggregate(
    db: psycopg.Connection[Any],
) -> None:
    seed_users(db)
    seed_problem(db)
    seed_submission(db)
    with pytest.raises(psycopg.errors.RaiseException), db.transaction():
        db.execute(
            "INSERT INTO public.submission_results(submission_id, user_id, problem_version_id, satisfied_weight, total_weight, passed, has_contradiction, confidence, jev_version, static_output, jev_output) VALUES (%s, %s, %s, 4, 4, true, false, 80, 'stub-v1', '{}'::jsonb, '{}'::jsonb)",  # noqa: E501
            (SUBMISSION, USER_A, VERSION),
        )
        db.execute(
            "INSERT INTO public.requirement_results(submission_id, rubric_item_id, decision, source, confidence, impact) VALUES (%s, %s, 'satisfied', 'static', NULL, 'high')",  # noqa: E501
            (SUBMISSION, RUBRIC_A),
        )
        db.execute("SET CONSTRAINTS ALL IMMEDIATE")


def test_post_requires_owned_exact_full_result(db: psycopg.Connection[Any]) -> None:
    seed_users(db)
    seed_problem(db)
    seed_submission(db)
    db.execute(
        "INSERT INTO public.submission_results(submission_id, user_id, problem_version_id, satisfied_weight, total_weight, passed, has_contradiction, confidence, jev_version, static_output, jev_output) VALUES (%s, %s, %s, 4, 4, true, false, 100, 'stub-v1', '{}'::jsonb, '{}'::jsonb)",  # noqa: E501
        (SUBMISSION, USER_A, VERSION),
    )
    db.execute(
        "INSERT INTO public.requirement_results(submission_id, rubric_item_id, decision, source, confidence, impact) VALUES (%s, %s, 'satisfied', 'static', NULL, 'high'), (%s, %s, 'satisfied', 'jev', 100, 'low')",  # noqa: E501
        (SUBMISSION, RUBRIC_A, SUBMISSION, RUBRIC_B),
    )
    with pytest.raises(psycopg.errors.RaiseException), db.transaction():
        db.execute(
            "INSERT INTO public.posts(id, submission_id, author_user_id, explanation, schema_snapshot) VALUES (%s, %s, %s, 'stolen', '{}'::jsonb)",  # noqa: E501
            ("01ARZ3NDEKTSV4RRFFQ69G5FB3", SUBMISSION, USER_B),
        )
    db.execute(
        "INSERT INTO public.posts(id, submission_id, author_user_id, explanation, schema_snapshot) VALUES (%s, %s, %s, 'mine', '{}'::jsonb)",  # noqa: E501
        ("01ARZ3NDEKTSV4RRFFQ69G5FB4", SUBMISSION, USER_A),
    )


def grant_learning_access(db: psycopg.Connection[Any]) -> None:
    db.execute(
        "INSERT INTO public.age_declarations(user_id, is_at_least_16) VALUES (%s, true)",  # noqa: E501
        (USER_A,),
    )
    db.execute(
        "INSERT INTO public.provider_identities(user_id, issuer, subject, verified_at) VALUES (%s, 'google', 'subject-a', now())",  # noqa: E501
        (USER_A,),
    )
    db.execute(
        "INSERT INTO private.identity_allowlist(id, issuer, subject, bound_at) VALUES (%s, 'google', 'subject-a', now())",  # noqa: E501
        ("01ARZ3NDEKTSV4RRFFQ69G5FB5",),
    )


def test_learning_content_requires_allowlist_age_and_current_policy(
    db: psycopg.Connection[Any],
) -> None:
    seed_users(db)
    seed_problem(db)
    publish_problem(db)
    db.execute("SET LOCAL ROLE authenticated")
    db.execute(
        "SELECT set_config('request.jwt.claim.sub', %s, true)",
        ("11111111-1111-1111-1111-111111111111",),
    )
    assert db.execute("SELECT count(*) FROM public.problems").fetchone() == (0,)
    db.execute("RESET ROLE")
    grant_learning_access(db)
    db.execute("SET LOCAL ROLE authenticated")
    assert db.execute("SELECT count(*) FROM public.problems").fetchone() == (1,)
    db.execute("RESET ROLE")
    policy_id = "01ARZ3NDEKTSV4RRFFQ69G5FB6"
    db.execute(
        "INSERT INTO public.policy_versions(id, kind, version, content_digest, content_en, required_from) VALUES (%s, 'terms', 1, %s, 'Terms v1', now())",  # noqa: E501
        (policy_id, DIGEST),
    )
    db.execute("SET LOCAL ROLE authenticated")
    assert db.execute("SELECT count(*) FROM public.problems").fetchone() == (0,)
    db.execute("RESET ROLE")
    db.execute(
        "INSERT INTO public.policy_acknowledgements(user_id, policy_version_id) VALUES (%s, %s)",  # noqa: E501
        (USER_A, policy_id),
    )
    db.execute("SET LOCAL ROLE authenticated")
    assert db.execute("SELECT count(*) FROM public.problems").fetchone() == (1,)


def test_frozen_version_allows_only_publication_state_transition(
    db: psycopg.Connection[Any],
) -> None:
    seed_problem(db)
    db.execute(
        "UPDATE public.problem_versions SET state = 'published' WHERE id = %s",
        (VERSION,),
    )
    with pytest.raises(psycopg.errors.RaiseException), db.transaction():
        db.execute(
            "UPDATE public.problem_versions SET explanation_en = 'changed' WHERE id = %s",  # noqa: E501
            (VERSION,),
        )


def test_account_deletion_mode_removes_cascaded_immutable_history(
    db: psycopg.Connection[Any],
) -> None:
    seed_users(db)
    seed_problem(db)
    seed_submission(db)
    db.execute("SET LOCAL app.account_deletion = 'on'")
    db.execute("DELETE FROM public.users WHERE id = %s", (USER_A,))
    assert db.execute(
        "SELECT count(*) FROM public.submissions WHERE user_id = %s", (USER_A,)
    ).fetchone() == (0,)


def test_frozen_rubric_rejects_new_items(db: psycopg.Connection[Any]) -> None:
    seed_problem(db)
    with pytest.raises(psycopg.errors.RaiseException), db.transaction():
        db.execute(
            """INSERT INTO public.rubric_items
            (id, problem_version_id, ordinal, description_en, weight, evaluator_spec)
            VALUES (%s, %s, 3, 'late', 1, '{}'::jsonb)""",
            ("01ARZ3NDEKTSV4RRFFQ69G5FB7", VERSION),
        )


def test_submission_problem_must_match_version(db: psycopg.Connection[Any]) -> None:
    seed_users(db)
    seed_problem(db)
    publish_problem(db)
    other_problem = "01ARZ3NDEKTSV4RRFFQ69G5FB8"
    db.execute("INSERT INTO public.problems(id) VALUES (%s)", (other_problem,))
    with pytest.raises(psycopg.errors.RaiseException), db.transaction():
        db.execute(
            """INSERT INTO public.submissions
            (id, user_id, problem_id, problem_version_id, idempotency_key,
             request_digest, canonical_schema, assessment_snapshot, engine_version)
            VALUES (%s, %s, %s, %s, %s, %s, '{}'::jsonb, '{}'::jsonb, 'test')""",
            (
                "01ARZ3NDEKTSV4RRFFQ69G5FB9",
                USER_A,
                other_problem,
                VERSION,
                "44444444-4444-4444-4444-444444444444",
                DIGEST,
            ),
        )


def test_workspace_revision_must_increment_once(db: psycopg.Connection[Any]) -> None:
    seed_users(db)
    seed_problem(db)
    db.execute(
        "INSERT INTO public.workspaces(user_id, problem_id, canonical_schema) VALUES (%s, %s, '{}'::jsonb)",  # noqa: E501
        (USER_A, PROBLEM),
    )
    with pytest.raises(psycopg.errors.RaiseException), db.transaction():
        db.execute(
            "UPDATE public.workspaces SET revision = 3 WHERE user_id = %s AND problem_id = %s",  # noqa: E501
            (USER_A, PROBLEM),
        )
    db.execute(
        "UPDATE public.workspaces SET revision = revision + 1 WHERE user_id = %s AND problem_id = %s",  # noqa: E501
        (USER_A, PROBLEM),
    )
    assert db.execute("SELECT revision FROM public.workspaces").fetchone() == (2,)


def seed_full_result(db: psycopg.Connection[Any]) -> None:
    db.execute(
        "INSERT INTO public.submission_results(submission_id, user_id, problem_version_id, satisfied_weight, total_weight, passed, has_contradiction, confidence, jev_version, static_output, jev_output) VALUES (%s, %s, %s, 4, 4, true, false, 100, 'stub-v1', '{}'::jsonb, '{}'::jsonb)",  # noqa: E501
        (SUBMISSION, USER_A, VERSION),
    )
    db.execute(
        "INSERT INTO public.requirement_results(submission_id, rubric_item_id, decision, source, confidence, impact) VALUES (%s, %s, 'satisfied', 'static', NULL, 'high'), (%s, %s, 'satisfied', 'jev', 100, 'low')",  # noqa: E501
        (SUBMISSION, RUBRIC_A, SUBMISSION, RUBRIC_B),
    )


def grant_user_b_learning_access(db: psycopg.Connection[Any]) -> None:
    db.execute(
        "INSERT INTO public.age_declarations(user_id, is_at_least_16) VALUES (%s, true)",  # noqa: E501
        (USER_B,),
    )
    db.execute(
        "INSERT INTO public.provider_identities(user_id, issuer, subject, verified_at) VALUES (%s, 'github', 'subject-b', now())",  # noqa: E501
        (USER_B,),
    )
    db.execute(
        "INSERT INTO private.identity_allowlist(id, issuer, subject, bound_at) VALUES (%s, 'github', 'subject-b', now())",  # noqa: E501
        ("01ARZ3NDEKTSV4RRFFQ69G5FBA",),
    )


def test_rls_isolates_private_learning_records_between_eligible_users(
    db: psycopg.Connection[Any],
) -> None:
    seed_users(db)
    grant_learning_access(db)
    grant_user_b_learning_access(db)
    seed_problem(db)
    seed_submission(db)
    seed_full_result(db)
    db.execute(
        "INSERT INTO public.feedback_versions(id, submission_id, user_id, version, content_en, model_version) VALUES (%s, %s, %s, 1, 'feedback', 'stub')",  # noqa: E501
        ("01ARZ3NDEKTSV4RRFFQ69G5FBB", SUBMISSION, USER_A),
    )
    db.execute(
        "INSERT INTO public.workspaces(user_id, problem_id, canonical_schema) VALUES (%s, %s, '{}'::jsonb)",  # noqa: E501
        (USER_A, PROBLEM),
    )
    db.execute("SET LOCAL ROLE authenticated")
    db.execute(
        "SELECT set_config('request.jwt.claim.sub', %s, true)",
        ("22222222-2222-2222-2222-222222222222",),
    )
    for table in (
        "submissions",
        "submission_results",
        "requirement_results",
        "feedback_versions",
        "workspaces",
    ):
        assert db.execute(f"SELECT count(*) FROM public.{table}").fetchone() == (0,)


def test_authenticated_role_cannot_write_authority_tables(
    db: psycopg.Connection[Any],
) -> None:
    seed_users(db)
    grant_learning_access(db)
    seed_problem(db)
    publish_problem(db)
    db.execute("SET LOCAL ROLE authenticated")
    db.execute(
        "SELECT set_config('request.jwt.claim.sub', %s, true)",
        ("11111111-1111-1111-1111-111111111111",),
    )
    statements = (
        "INSERT INTO public.role_grants(user_id, role, reason) VALUES ('01ARZ3NDEKTSV4RRFFQ69G5FAV', 'owner', 'self')",  # noqa: E501
        "INSERT INTO public.submission_results(submission_id, user_id, problem_version_id, satisfied_weight, total_weight, passed, has_contradiction, confidence, jev_version, static_output, jev_output) VALUES ('01ARZ3NDEKTSV4RRFFQ69G5FB1', '01ARZ3NDEKTSV4RRFFQ69G5FAV', '01ARZ3NDEKTSV4RRFFQ69G5FAY', 1, 1, true, false, 100, 'x', '{}'::jsonb, '{}'::jsonb)",  # noqa: E501
        "INSERT INTO public.publication_calendar(publication_date, problem_id, problem_version_id, published_at) VALUES (DATE '2026-02-01', '01ARZ3NDEKTSV4RRFFQ69G5FAX', '01ARZ3NDEKTSV4RRFFQ69G5FAY', now())",  # noqa: E501
    )
    for statement in statements:
        with pytest.raises(psycopg.errors.InsufficientPrivilege), db.transaction():
            db.execute(statement)


def test_submission_idempotency_key_rejects_second_resource(
    db: psycopg.Connection[Any],
) -> None:
    seed_users(db)
    seed_problem(db)
    seed_submission(db)
    with pytest.raises(psycopg.errors.UniqueViolation), db.transaction():
        db.execute(
            """INSERT INTO public.submissions
            (id, user_id, problem_id, problem_version_id, idempotency_key,
             request_digest, canonical_schema, assessment_snapshot, engine_version)
            SELECT %s, user_id, problem_id, problem_version_id, idempotency_key,
                   request_digest, canonical_schema, assessment_snapshot, engine_version
            FROM public.submissions WHERE id = %s""",
            ("01ARZ3NDEKTSV4RRFFQ69G5FBC", SUBMISSION),
        )


def test_publication_requires_exact_0400_jst_boundary(
    db: psycopg.Connection[Any],
) -> None:
    seed_problem(db)
    with pytest.raises(psycopg.errors.CheckViolation), db.transaction():
        db.execute(
            """INSERT INTO public.publication_calendar
            (publication_date, problem_id, problem_version_id, published_at)
            VALUES (DATE '2026-01-01', %s, %s,
                    DATE '2026-01-01'::timestamp AT TIME ZONE 'Asia/Tokyo'
                    + interval '4 hours 1 minute')""",
            (PROBLEM, VERSION),
        )


def test_dashboard_query_has_usable_indexes(db: psycopg.Connection[Any]) -> None:
    seed_users(db)
    seed_problem(db)
    seed_submission(db)
    seed_full_result(db)
    db.execute("SET LOCAL enable_seqscan = off")
    plan = "\n".join(
        row[0]
        for row in db.execute(
            """EXPLAIN (COSTS OFF)
            SELECT DISTINCT s.problem_id
            FROM public.submissions AS s
            JOIN public.submission_results AS r ON r.submission_id = s.id
            WHERE s.user_id = %s AND r.passed""",
            (USER_A,),
        ).fetchall()
    )
    assert "Index" in plan


def test_account_deletion_cascades_full_private_history(
    db: psycopg.Connection[Any],
) -> None:
    seed_users(db)
    seed_problem(db)
    seed_submission(db)
    seed_full_result(db)
    db.execute(
        "INSERT INTO public.feedback_versions(id, submission_id, user_id, version, content_en, model_version) VALUES (%s, %s, %s, 1, 'feedback', 'stub')",  # noqa: E501
        ("01ARZ3NDEKTSV4RRFFQ69G5FBD", SUBMISSION, USER_A),
    )
    db.execute(
        "INSERT INTO public.posts(id, submission_id, author_user_id, explanation, schema_snapshot) VALUES (%s, %s, %s, 'mine', '{}'::jsonb)",  # noqa: E501
        ("01ARZ3NDEKTSV4RRFFQ69G5FBE", SUBMISSION, USER_A),
    )
    reward_id = "01ARZ3NDEKTSV4RRFFQ69G5FBF"
    db.execute(
        "INSERT INTO private.ad_reward_attempts(id, user_id, state) VALUES (%s, %s, 'pending')",  # noqa: E501
        (reward_id, USER_A),
    )
    db.execute(
        "INSERT INTO private.feedback_requests(id, user_id, problem_id, submission_id, reward_attempt_id, operation_key) VALUES (%s, %s, %s, %s, %s, %s)",  # noqa: E501
        (
            "01ARZ3NDEKTSV4RRFFQ69G5FBG",
            USER_A,
            PROBLEM,
            SUBMISSION,
            reward_id,
            "55555555-5555-5555-5555-555555555555",
        ),
    )
    db.execute("SET LOCAL app.account_deletion = 'on'")
    db.execute("DELETE FROM public.users WHERE id = %s", (USER_A,))
    for qualified in (
        "public.submissions",
        "public.submission_results",
        "public.requirement_results",
        "public.feedback_versions",
        "public.posts",
        "private.feedback_requests",
        "private.ad_reward_attempts",
    ):
        assert db.execute(f"SELECT count(*) FROM {qualified}").fetchone() == (0,)


def test_post_snapshot_must_equal_graded_submission(
    db: psycopg.Connection[Any],
) -> None:
    seed_users(db)
    seed_problem(db)
    seed_submission(db)
    seed_full_result(db)
    with pytest.raises(psycopg.errors.RaiseException), db.transaction():
        db.execute(
            "INSERT INTO public.posts(id, submission_id, author_user_id, explanation, schema_snapshot) VALUES (%s, %s, %s, 'different', '{\"tables\": []}'::jsonb)",  # noqa: E501
            ("01ARZ3NDEKTSV4RRFFQ69G5FBH", SUBMISSION, USER_A),
        )


def test_only_latest_effective_policy_per_kind_is_required(
    db: psycopg.Connection[Any],
) -> None:
    seed_users(db)
    grant_learning_access(db)
    first = "01ARZ3NDEKTSV4RRFFQ69G5FBJ"
    latest = "01ARZ3NDEKTSV4RRFFQ69G5FBK"
    db.execute(
        "INSERT INTO public.policy_versions(id, kind, version, content_digest, content_en, required_from) VALUES (%s, 'terms', 1, %s, 'Terms v1', now() - interval '2 days'), (%s, 'terms', 2, %s, 'Terms v2', now() - interval '1 day')",  # noqa: E501
        (first, DIGEST, latest, "b" * 64),
    )
    db.execute(
        "INSERT INTO public.policy_acknowledgements(user_id, policy_version_id) VALUES (%s, %s)",  # noqa: E501
        (USER_A, latest),
    )
    db.execute("SET LOCAL ROLE authenticated")
    db.execute(
        "SELECT set_config('request.jwt.claim.sub', %s, true)",
        ("11111111-1111-1111-1111-111111111111",),
    )
    assert db.execute("SELECT public.can_learn()").fetchone() == (True,)


def test_jev_requirement_confidence_is_mandatory(
    db: psycopg.Connection[Any],
) -> None:
    seed_users(db)
    seed_problem(db)
    seed_submission(db)
    with pytest.raises(psycopg.errors.CheckViolation), db.transaction():
        db.execute(
            "INSERT INTO public.submission_results(submission_id, user_id, problem_version_id, satisfied_weight, total_weight, passed, has_contradiction, confidence, jev_version, static_output, jev_output) VALUES (%s, %s, %s, 4, 4, true, false, 100, 'stub-v1', '{}'::jsonb, '{}'::jsonb)",  # noqa: E501
            (SUBMISSION, USER_A, VERSION),
        )
        db.execute(
            "INSERT INTO public.requirement_results(submission_id, rubric_item_id, decision, source, confidence, impact) VALUES (%s, %s, 'satisfied', 'jev', NULL, 'high')",  # noqa: E501
            (SUBMISSION, RUBRIC_A),
        )


def test_publication_update_revalidates_version(
    db: psycopg.Connection[Any],
) -> None:
    seed_problem(db)
    publish_problem(db)
    draft_version = "01ARZ3NDEKTSV4RRFFQ69G5FBM"
    db.execute(
        """INSERT INTO public.problem_versions
        (id, problem_id, version, title, statement_en, official_solution,
         explanation_en, difficulty, genre, input_format, normalized_hash)
        VALUES (%s, %s, 2, 'Draft', 'Draft', '{}'::jsonb, 'Draft',
                'easy', 'oltp', 'mixed', %s)""",
        (draft_version, PROBLEM, "c" * 64),
    )
    with pytest.raises(psycopg.errors.RaiseException), db.transaction():
        db.execute(
            "UPDATE public.publication_calendar SET problem_version_id = %s WHERE problem_id = %s",  # noqa: E501
            (draft_version, PROBLEM),
        )


def test_rubric_mutation_lock_blocks_concurrent_freeze(database_uri: str) -> None:
    problem = "01ARZ3NDEKTSV4RRFFQ69G5FBN"
    version = "01ARZ3NDEKTSV4RRFFQ69G5FBP"
    rubric = "01ARZ3NDEKTSV4RRFFQ69G5FBQ"
    with psycopg.connect(database_uri) as setup:
        setup.execute("INSERT INTO public.problems(id) VALUES (%s)", (problem,))
        setup.execute(
            """INSERT INTO public.problem_versions
            (id, problem_id, version, title, statement_en, official_solution,
             explanation_en, difficulty, genre, input_format, normalized_hash)
            VALUES (%s, %s, 1, 'Draft', 'Draft', '{}'::jsonb, 'Draft',
                    'easy', 'oltp', 'mixed', %s)""",
            (version, problem, "d" * 64),
        )
        setup.execute(
            "INSERT INTO public.rubric_items(id, problem_version_id, ordinal, description_en, weight, evaluator_spec) VALUES (%s, %s, 0, 'item', 1, '{}'::jsonb)",  # noqa: E501
            (rubric, version),
        )
    with (
        psycopg.connect(database_uri) as writer,
        psycopg.connect(database_uri) as freezer,
    ):
        writer.execute(
            "UPDATE public.rubric_items SET description_en = 'editing' WHERE id = %s",
            (rubric,),
        )
        freezer.execute("SET LOCAL lock_timeout = '100ms'")
        with pytest.raises(psycopg.errors.LockNotAvailable):
            freezer.execute(
                "UPDATE public.problem_versions SET state = 'approved', frozen_at = now() WHERE id = %s",  # noqa: E501
                (version,),
            )
        freezer.rollback()
        writer.rollback()
    with psycopg.connect(database_uri) as cleanup:
        cleanup.execute("DELETE FROM public.rubric_items WHERE id = %s", (rubric,))
        cleanup.execute("DELETE FROM public.problem_versions WHERE id = %s", (version,))
        cleanup.execute("DELETE FROM public.problems WHERE id = %s", (problem,))


def test_idempotency_unique_key_serializes_concurrent_submissions(
    database_uri: str,
) -> None:
    with psycopg.connect(database_uri) as setup:
        seed_users(setup)
        seed_problem(setup)
        publish_problem(setup)
    insert_sql = """INSERT INTO public.submissions
        (id, user_id, problem_id, problem_version_id, idempotency_key,
         request_digest, canonical_schema, assessment_snapshot, engine_version)
        VALUES (%s, %s, %s, %s, %s, %s, '{}'::jsonb, '{}'::jsonb, 'test')"""
    key = "66666666-6666-6666-6666-666666666666"
    with (
        psycopg.connect(database_uri) as first,
        psycopg.connect(database_uri) as second,
    ):
        first.execute(
            insert_sql,
            (SUBMISSION, USER_A, PROBLEM, VERSION, key, DIGEST),
        )
        second.execute("SET LOCAL lock_timeout = '100ms'")
        with pytest.raises(psycopg.errors.LockNotAvailable):
            second.execute(
                insert_sql,
                ("01ARZ3NDEKTSV4RRFFQ69G5FBR", USER_A, PROBLEM, VERSION, key, DIGEST),
            )
        second.rollback()
        first.commit()
        with pytest.raises(psycopg.errors.UniqueViolation):
            second.execute(
                insert_sql,
                ("01ARZ3NDEKTSV4RRFFQ69G5FBR", USER_A, PROBLEM, VERSION, key, DIGEST),
            )
        second.rollback()
