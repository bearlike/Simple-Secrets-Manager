#!/usr/bin/env python3
"""User-Pass authentication for Secrets Manager"""

from werkzeug.security import generate_password_hash, check_password_hash
from bson.timestamp import Timestamp
from textwrap import dedent
import datetime as dt
import re
import os


class _password_policy:
    def __init__(self):
        # Username policy: regex pattern
        self.uname_pat = "[a-zA-Z0-9_]+"
        # min length (default: 6)
        self.length = os.environ.get("PASSWORD_POLICY_LENGTH", 6)
        # need min. (default: 1) uppercase letters
        self.uppercase = os.environ.get("PASSWORD_POLICY_UPPERCASE", 1)
        # need min. (default: 1) uppercase letters
        self.lowercase = os.environ.get("PASSWORD_POLICY_LOWERCASE", 1)
        # need min. (default: 1) digits
        self.numbers = os.environ.get("PASSWORD_POLICY_NUMBERS", 1)
        # need min. (default: 1) special characters
        self.special = os.environ.get("PASSWORD_POLICY_SPECIAL", 1)

    def __repr__(self):
        policy_str = f"""
        (1) Minimum of {self.length} characters in length.
        (2) Must have at least {self.lowercase} lowercase characters.
        (3) Must have at least {self.uppercase}uppercase characters.
        (4) Must have at least {self.numbers} numbers.
        (5) Must have at least {self.special} special characters.
        """
        policy_str = dedent(policy_str).replace("\n", " ")
        return policy_str

    def check(self, password):
        """Password policy/rules to encourage users to employ strong passwords.
        Args:
            password (str): Password string
        Returns:
            bool: True if password policy is satisfied
        """
        if (
            len(password) >= self.length
            and len(re.findall("[a-z]", password)) >= self.lowercase
            and len(re.findall("[A-Z]", password)) >= self.uppercase
            and len(re.findall("[0-9]", password)) >= self.numbers
            and len(re.findall("[^a-z^A-Z^0-9]", password)) >= self.special
        ):
            return True
        return False


class User_Pass:
    def __init__(self, userpass_auth_col):
        """Userpass operations
        Args:
            userpass_auth_col (pymongo.collection.Collection)
        """
        # * Create unique index on 'username' for secrets_manager_auth.userpass
        # * db.userpass.createIndex( { "username": 1 }, { unique: true } )
        self._userpass = userpass_auth_col
        self.p_pol = _password_policy()

    def register(self, username, password):
        """Register a new user
        Args:
            username (str): Username
            password (str): Password
        Returns:
            dict : Dictionary with operation status
        """
        # Username policy check
        if not re.fullmatch(self.p_pol.uname_pat, username):
            return f"Username does not match {self.p_pol.uname_pat}", 400
        # Password policy check
        if not self.p_pol.check(password):
            return f"Password policy not met. {self.p_pol}", 400
        finder = self._userpass.find_one({"username": username})
        if not finder:
            password = generate_password_hash(password, method="pbkdf2:sha256")
            data = {
                "username": username,
                "password": password,
                "added_on": Timestamp(int(dt.datetime.today().timestamp()), 1),
            }
            _ = self._userpass.insert_one(data)
            status = {"status": "OK"}
            return status, 200
        return "User already exist", 400

    def remove(self, username):
        """Deletes an existing user
        Args:
            username (str): Username
        Returns:
            dict : Dictionary with operation status
        """
        finder = self._userpass.find_one({"username": username})
        if not finder:
            return "User does not exist", 400
        _ = self._userpass.delete_one({"username": username})
        result = {"status": "OK"}
        return result, 200

    def is_authorized(self, username, password):
        """Check if a userpass is valid
        Args:
            username (str): Username
            password (str): Password
        Returns:
            bool: True for valid userpass and False otherwise.
        """
        finder = self._userpass.find_one({"username": username})
        # Return False, if username is not found
        if not finder:
            return False
        # Return True, if userpass is valid
        return check_password_hash(finder["password"], password)
