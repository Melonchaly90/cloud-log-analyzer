"""
IAM (Identity & Access Management) Module
Handles authentication, role-based access control, and password hashing.
"""

import os
import hashlib
import hmac
import uuid
from db.database import DatabaseManager


def _hash_password(password: str, salt: str = None) -> tuple[str, str]:
    """Return (salt, hashed_password) using PBKDF2-HMAC-SHA256."""
    if salt is None:
        salt = uuid.uuid4().hex
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations=260_000,
    )
    return salt, dk.hex()


def _verify_password(stored_salt: str, stored_hash: str, provided: str) -> bool:
    _, candidate_hash = _hash_password(provided, stored_salt)
    return hmac.compare_digest(stored_hash, candidate_hash)


class IAMManager:
    """
    Simulates a cloud IAM service with:
    - Local user database (seeded with defaults on first run)
    - Role-based access: admin vs. viewer
    - Secure password verification (PBKDF2)
    """

    def __init__(self):
        self.db = DatabaseManager()
        self._seed_default_users()

    def _seed_default_users(self):
        """Create default admin and viewer accounts if none exist."""
        if self.db.user_count() > 0:
            return

        admin_pass  = os.environ.get("ADMIN_PASSWORD",  "Admin@1234")
        viewer_pass = os.environ.get("VIEWER_PASSWORD", "Viewer@1234")

        self._create_user("admin",  admin_pass,  is_admin=True)
        self._create_user("viewer", viewer_pass, is_admin=False)

    def _create_user(self, username: str, password: str, is_admin: bool = False):
        salt, pw_hash = _hash_password(password)
        self.db.create_user(
            user_id  = uuid.uuid4().hex,
            username = username,
            pw_salt  = salt,
            pw_hash  = pw_hash,
            is_admin = is_admin,
        )

    def authenticate(self, username: str, password: str) -> dict | None:
        """
        Verify credentials.
        Returns user dict on success, None on failure.
        """
        user = self.db.get_user_by_username(username)
        if not user:
            return None
        if _verify_password(user["pw_salt"], user["pw_hash"], password):
            return {
                "id":       user["id"],
                "username": user["username"],
                "is_admin": bool(user["is_admin"]),
            }
        return None

    def has_permission(self, user_id: str, permission: str) -> bool:
        """
        Simple RBAC: admins have all permissions,
        viewers can only read non-sensitive resources.
        """
        user = self.db.get_user_by_id(user_id)
        if not user:
            return False
        if user["is_admin"]:
            return True
        # Viewers may only access these
        viewer_permissions = {"view_dashboard", "view_results", "upload_logs"}
        return permission in viewer_permissions
