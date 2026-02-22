#!/usr/bin/env python3
from datetime import datetime, timezone


class AuditEvents:
    def __init__(self, events_col):
        self._events = events_col
        self._events.create_index([("project_id", 1), ("ts", -1)])
        self._events.create_index([("config_id", 1), ("ts", -1)])
        self._events.create_index([("token_id", 1), ("ts", -1)])

    def write_event(self, event: dict):
        payload = {
            "ts": datetime.now(timezone.utc),
            **event,
        }
        self._events.insert_one(payload)

    def query_events(self, project_id=None, config_id=None, since=None, limit=100):
        query = {}
        if project_id is not None:
            query["project_id"] = project_id
        if config_id is not None:
            query["config_id"] = config_id
        if since is not None:
            query["ts"] = {"$gte": since}
        return list(self._events.find(query, {"_id": 0}).sort("ts", -1).limit(limit))
