from Engines.compare_issues import (
    ISSUE_BROKEN_REFERENCE_CYCLE_OR_DEPTH,
    ISSUE_BROKEN_REFERENCE_SYNTAX,
    ISSUE_BROKEN_REFERENCE_UNRESOLVED,
    ISSUE_MISSING_EFFECTIVE_VALUE,
    build_issue,
    build_issue_summary,
    classify_reference_error,
    has_broken_reference,
)


def test_classify_reference_error_types():
    assert (
        classify_reference_error("Invalid reference syntax: ${bad-token}")
        == ISSUE_BROKEN_REFERENCE_SYNTAX
    )
    assert (
        classify_reference_error("Secret reference cycle detected: A -> B")
        == ISSUE_BROKEN_REFERENCE_CYCLE_OR_DEPTH
    )
    assert (
        classify_reference_error(
            "Secret reference max depth exceeded (8) while resolving "
            "project.cfg.KEY"
        )
        == ISSUE_BROKEN_REFERENCE_CYCLE_OR_DEPTH
    )
    assert (
        classify_reference_error("Unresolved reference: ${app.dev.DB_URL}")
        == ISSUE_BROKEN_REFERENCE_UNRESOLVED
    )


def test_has_broken_reference_checks_issue_codes():
    assert not has_broken_reference(
        [build_issue(ISSUE_MISSING_EFFECTIVE_VALUE, "Missing value")]
    )
    assert has_broken_reference(
        [
            build_issue(
                ISSUE_BROKEN_REFERENCE_UNRESOLVED, "Unresolved reference"
            )
        ]
    )


def test_build_issue_summary_counts_codes_and_affected_configs():
    rows = [
        {
            "configSlug": "dev",
            "issues": [build_issue(ISSUE_MISSING_EFFECTIVE_VALUE, "Missing")],
        },
        {
            "configSlug": "prd",
            "issues": [
                build_issue(ISSUE_BROKEN_REFERENCE_UNRESOLVED, "Unresolved"),
                build_issue(ISSUE_BROKEN_REFERENCE_SYNTAX, "Bad token"),
            ],
        },
        {"configSlug": "staging", "issues": []},
    ]

    summary = build_issue_summary(rows)

    assert summary["totalIssues"] == 3
    assert summary["affectedConfigs"] == 2
    assert summary["byCode"] == [
        {"code": ISSUE_BROKEN_REFERENCE_SYNTAX, "count": 1},
        {"code": ISSUE_BROKEN_REFERENCE_UNRESOLVED, "count": 1},
        {"code": ISSUE_MISSING_EFFECTIVE_VALUE, "count": 1},
    ]
