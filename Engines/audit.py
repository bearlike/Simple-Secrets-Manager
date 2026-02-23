#!/usr/bin/env python3
from datetime import datetime, timezone

from Api.serialization import sanitize_doc


class AuditEvents:
    def __init__(self, events_col):
        self._events = events_col
        self._events.create_index([("project_slug", 1), ("ts", -1)])
        self._events.create_index([("config_slug", 1), ("ts", -1)])
        # Keep legacy indexes for existing deployments.
        self._events.create_index([("project_id", 1), ("ts", -1)])
        self._events.create_index([("config_id", 1), ("ts", -1)])
        self._events.create_index([("token_id", 1), ("ts", -1)])

    def write_event(self, event: dict):
        payload = {
            "ts": datetime.now(timezone.utc),
            **event,
        }
        self._events.insert_one(payload)

    def query_events(self, project_slug=None, config_slug=None, since=None, limit=100, project_id=None, config_id=None):
        clauses = []
        if project_slug is not None and project_id is not None:
            clauses.append({"$or": [{"project_slug": project_slug}, {"project_id": project_id}]})
        elif project_slug is not None:
            clauses.append({"project_slug": project_slug})
        elif project_id is not None:
            clauses.append({"project_id": project_id})
        if config_slug is not None and config_id is not None:
            clauses.append({"$or": [{"config_slug": config_slug}, {"config_id": config_id}]})
        elif config_slug is not None:
            clauses.append({"config_slug": config_slug})
        elif config_id is not None:
            clauses.append({"config_id": config_id})
        query = {}
        if clauses:
            query["$and"] = clauses
        if since is not None:
            query["ts"] = {"$gte": since}
        events = list(self._events.find(query, {"_id": 0}).sort("ts", -1).limit(limit))
        return [sanitize_doc(event) for event in events]
