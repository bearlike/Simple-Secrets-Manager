#!/usr/bin/env python3
"""KV (Key-Value) Secret Engine for Secrets Manager"""

import re


class Key_Value_Secrets:
    def __init__(self, kv_col):
        """KV stands for Key-Value collection
        Args:
            kv_col (pymongo.collection.Collection)
        """
        # * Create unique index on 'path' for the kv collection
        # * db.kv.createIndex( { "path": 1 }, { unique: true } )
        self._kv = kv_col

    def get(self, path, key):
        finder = self._kv.find_one({"path": path})
        if not finder:
            return "'Path' not found in KV engine", 404
        if key not in finder["data"].keys():
            return f"Key not found in '{path}'", 404
        result = {
            "value": finder["data"][key],
            "status": "OK",
            "path": path,
            "key": key,
        }
        return result, 200

    def add(self, path, key, value):
        pattern = "[a-zA-Z0-9_]+"
        if not (re.fullmatch(pattern, key) and re.fullmatch(pattern, path)):
            return f"Key and/or Path does not match {pattern}", 400
        finder = self._kv.find_one({"path": path})
        if finder is None:
            # Create a Path where kv(s) goes into
            finder = {
                "path": path,
                "data": {},
            }
            _ = self._kv.insert_one(finder)
        if key not in finder["data"].keys():
            # After Creating path, add kv
            self._kv.update_one(
                {"path": path}, {"$set": {f"data.{key}": value}}
            )
            result = {
                "status": "success",
                "path": path,
                "key": key,
            }
        else:
            return {"status": f"Key already exist in '{path}'"}, 400
        return result, 200

    def delete(self, path, key):
        finder = self._kv.find_one({"path": path})
        if not finder:
            return "Path not found", 404
        if key not in finder["data"].keys():
            return f"Key not found in '{path}'", 404
        self._kv.update_one({"path": path}, {"$unset": {f"data.{key}": 1}})
        # TODO: Delete document if path has no kv(s)
        result = {"status": "OK", "path": path, "key": key}
        return result, 200

    def update(self, path, key, value):
        finder = self._kv.find_one({"path": path})
        if not finder:
            return "Path not found", 404
        if key not in finder["data"].keys():
            return f"Key not found in '{path}'", 404
        self._kv.update_one({"path": path}, {"$set": {f"data.{key}": value}})
        result = {"status": "OK", "path": path, "key": key}
        return result, 200
