#!/usr/bin/env python3
from datetime import date, datetime, timezone

from bson import ObjectId


def to_iso(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        dt_value = value
        if dt_value.tzinfo is None:
            dt_value = dt_value.replace(tzinfo=timezone.utc)
        return dt_value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def oid_to_str(oid):
    if oid is None:
        return None
    if isinstance(oid, ObjectId):
        return str(oid)
    return str(oid)


def sanitize_doc(doc):
    if isinstance(doc, dict):
        return {key: sanitize_doc(value) for key, value in doc.items()}
    if isinstance(doc, list):
        return [sanitize_doc(item) for item in doc]
    if isinstance(doc, tuple):
        return [sanitize_doc(item) for item in doc]
    if isinstance(doc, ObjectId):
        return oid_to_str(doc)
    if isinstance(doc, (datetime, date)):
        return to_iso(doc)
    return doc
