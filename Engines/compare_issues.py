#!/usr/bin/env python3
from collections import Counter

ISSUE_MISSING_EFFECTIVE_VALUE = "missing_effective_value"
ISSUE_BROKEN_REFERENCE_UNRESOLVED = "broken_reference_unresolved"
ISSUE_BROKEN_REFERENCE_SYNTAX = "broken_reference_syntax"
ISSUE_BROKEN_REFERENCE_CYCLE_OR_DEPTH = "broken_reference_cycle_or_depth"


def build_issue(code, message, severity="warning"):
    return {
        "code": code,
        "severity": severity,
        "message": message,
    }


def classify_reference_error(message):
    lowered = message.lower()
    if "invalid reference syntax" in lowered:
        return ISSUE_BROKEN_REFERENCE_SYNTAX
    if "cycle" in lowered or "max depth" in lowered:
        return ISSUE_BROKEN_REFERENCE_CYCLE_OR_DEPTH
    return ISSUE_BROKEN_REFERENCE_UNRESOLVED


def has_broken_reference(issues):
    return any(issue["code"].startswith("broken_reference_") for issue in issues)


def build_issue_summary(rows):
    by_code = Counter()
    affected_configs = 0
    for row in rows:
        row_issues = row.get("issues", [])
        if row_issues:
            affected_configs += 1
        for issue in row_issues:
            by_code[issue["code"]] += 1
    return {
        "totalIssues": sum(by_code.values()),
        "affectedConfigs": affected_configs,
        "byCode": [{"code": code, "count": count} for code, count in sorted(by_code.items())],
    }
