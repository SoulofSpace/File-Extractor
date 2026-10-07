"""Privacy Engine for FILE XTRACTOR V4.

Provides:
- Application-level password management with Argon2id hashing
- Rate-limited password verification & recovery key workflow
- Sensitivity scanner for Indian IDs, Banking, Cards, and Confidential records
- Privacy Access Scope enforcement (NORMAL, PROTECTED, HIDDEN)
- Result Sanitizer for masking protected content when locked
"""

from __future__ import annotations

import logging
import os
import re
import secrets
import string
import time
from typing import Any, Dict, List, Optional, Tuple

import argon2

from intellifile.database import Database

logger = logging.getLogger(__name__)


# ── SENSITIVITY DETECTION REGEX PATTERNS ─────────────────────────────────────

RE_AADHAAR = re.compile(r"\b[2-9]{1}\d{3}[\s-]?\d{4}[\s-]?\d{4}\b")
RE_PAN = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]{1}\b")
RE_IFSC = re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b")
RE_CREDIT_CARD = re.compile(r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})\b")
RE_ACCOUNT_NUMBER = re.compile(r"(?i)\b(?:a/c|acct|account(?:\s+no|\s+number)?)[\s.:#-]*([0-9]{9,18})\b")
RE_PASSPORT = re.compile(r"\b[A-Z][0-9]{7}\b")
RE_VOTER_ID = re.compile(r"\b[A-Z]{3}[0-9]{7}\b")

# Keywords for context identification
KEYWORDS_BANKING = {
    "bank", "statement", "passbook", "salary slip", "payslip", "neft", "rtgs", "imps",
    "cheque", "deposit", "withdrawal", "hdfc", "sbi", "icici", "axis", "kotak", "pnb",
    "canara", "union bank", "overdraft", "balance"
}

KEYWORDS_ID = {
    "aadhaar", "uidai", "income tax department", "pan card", "passport", "election commission",
    "voter", "epic", "driving licence", "driving license", "identity card", "id card", "govt of india"
}

KEYWORDS_CONFIDENTIAL = {
    "strictly confidential", "private and confidential", "confidential", "nda",
    "non-disclosure", "proprietary", "trade secret", "internal use only"
}


class PrivacyEngine:
    """Manages application-level privacy states, authentication, and result sanitization."""

    def __init__(self, db: Database):
        self.db = db
        self.ph = argon2.PasswordHasher(
            time_cost=2,
            memory_cost=65536,  # 64 MB
            parallelism=1,
            hash_len=32,
            salt_len=16,
        )
        # In-memory authentication sessions: {token: (expiry_timestamp, created_at)}
        self._active_sessions: Dict[str, Tuple[float, float]] = {}
        # Rate-limiting: {ip_or_id: [timestamp, timestamp, ...]}
        self._failed_attempts: List[float] = []
        self._lockout_until: float = 0.0

    # ── PASSWORD & AUTHENTICATION ─────────────────────────────────────────────

    def is_password_configured(self) -> bool:
        """Check if privacy master password has been configured."""
        pwd_hash = self.db.get_privacy_setting("master_password_hash")
        return bool(pwd_hash and pwd_hash.strip())

    def setup_password(self, password: str) -> str:
        """Set up master password and generate a secure recovery key.
        
        Returns the plaintext recovery key (must be displayed to user once).
        """
        if not password or len(password) < 4:
            raise ValueError("Password must be at least 4 characters long.")

        # Hash password with Argon2id
        pwd_hash = self.ph.hash(password)
        self.db.set_privacy_setting("master_password_hash", pwd_hash)

        # Generate a 16-character alphanumeric recovery key formatted as XXXX-XXXX-XXXX-XXXX
        raw_key = "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(16))
        formatted_recovery_key = f"{raw_key[0:4]}-{raw_key[4:8]}-{raw_key[8:12]}-{raw_key[12:16]}"
        
        # Store Argon2id hash of recovery key (strip hyphens for normalization)
        norm_key = formatted_recovery_key.replace("-", "").upper()
        rec_hash = self.ph.hash(norm_key)
        self.db.set_privacy_setting("recovery_key_hash", rec_hash)

        # Set default privacy settings if not already present
        defaults = {
            "protect_banking": "true",
            "protect_ids": "true",
            "protect_personal_info": "true",
            "protect_confidential": "true",
            "protected_files_visibility": "show",  # show or hide in normal search
            "hide_protected_filename": "true",
            "protected_image_preview": "blur",     # blur or hide
            "protected_metadata_mode": "limited",   # limited or hide
            "face_indexing_enabled": "true",
            "multilingual_search_enabled": "true",
            "voice_search_enabled": "true",
        }
        for k, v in defaults.items():
            if self.db.get_privacy_setting(k) is None:
                self.db.set_privacy_setting(k, v)

        logger.info("Privacy password configured successfully.")
        return formatted_recovery_key

    def verify_password(self, password: str, session_duration_seconds: int = 1800) -> Tuple[bool, Optional[str], str]:
        """Verify password against Argon2id hash with rate-limiting.
        
        Returns: (success, session_token, message)
        """
        now = time.time()
        if now < self._lockout_until:
            wait_sec = int(self._lockout_until - now)
            return False, None, f"Too many failed attempts. Locked for {wait_sec} seconds."

        pwd_hash = self.db.get_privacy_setting("master_password_hash")
        if not pwd_hash:
            return False, None, "Privacy password has not been configured yet."

        try:
            self.ph.verify(pwd_hash, password)
            # Reset failed attempts on success
            self._failed_attempts.clear()
            self._lockout_until = 0.0

            # Generate session token (valid for session_duration_seconds, default 30 min)
            token = secrets.token_urlsafe(32)
            self._active_sessions[token] = (now + session_duration_seconds, now)
            return True, token, "Authentication successful."
        except argon2.exceptions.VerifyMismatchError:
            self._record_failed_attempt(now)
            return False, None, "Incorrect privacy password."
        except Exception as e:
            logger.error(f"Error during password verification: {e}")
            return False, None, "Verification error."

    def verify_recovery_key(self, recovery_key: str, new_password: str) -> Tuple[bool, str]:
        """Reset password using the recovery key.
        
        Returns: (success, message)
        """
        now = time.time()
        if now < self._lockout_until:
            wait_sec = int(self._lockout_until - now)
            return False, f"Too many failed attempts. Locked for {wait_sec} seconds."

        rec_hash = self.db.get_privacy_setting("recovery_key_hash")
        if not rec_hash:
            return False, "No recovery key found."

        norm_key = recovery_key.replace("-", "").replace(" ", "").upper()
        try:
            self.ph.verify(rec_hash, norm_key)
            self._failed_attempts.clear()
            self._lockout_until = 0.0

            if not new_password or len(new_password) < 4:
                return False, "New password must be at least 4 characters long."

            new_pwd_hash = self.ph.hash(new_password)
            self.db.set_privacy_setting("master_password_hash", new_pwd_hash)
            return True, "Password successfully reset using recovery key."
        except argon2.exceptions.VerifyMismatchError:
            self._record_failed_attempt(now)
            return False, "Invalid recovery key."
        except Exception as e:
            logger.error(f"Error verifying recovery key: {e}")
            return False, "Recovery verification error."

    def _record_failed_attempt(self, now: float) -> None:
        """Track failed attempts; apply lockout after 5 consecutive failures."""
        # Keep failures in last 5 minutes
        self._failed_attempts = [t for t in self._failed_attempts if now - t < 300]
        self._failed_attempts.append(now)
        if len(self._failed_attempts) >= 5:
            self._lockout_until = now + 60.0  # 60s lockout
            logger.warning("5 failed privacy password attempts. Rate-limiting triggered.")

    def validate_session(self, token: Optional[str]) -> bool:
        """Check if session token is valid and not expired."""
        if not token:
            return False
        now = time.time()
        session_info = self._active_sessions.get(token)
        if not session_info:
            return False
        expiry, created = session_info
        if now > expiry:
            self._active_sessions.pop(token, None)
            return False
        return True

    def revoke_session(self, token: Optional[str]) -> bool:
        """Revoke active session token."""
        if token and token in self._active_sessions:
            del self._active_sessions[token]
            return True
        return False

    # ── SENSITIVITY DETECTION & CLASSIFICATION ────────────────────────────────

    def scan_sensitivity(
        self,
        text: str,
        filename: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, str, float]:
        """Scan text and filename to determine sensitivity class and suggested privacy state.
        
        Returns:
            (sensitivity_class, suggested_privacy_state, confidence)
            sensitivity_class in: ["ID_DOCUMENT", "BANKING_FINANCE", "CONFIDENTIAL", "PERSONAL_INFO", "NONE"]
            suggested_privacy_state in: ["NORMAL", "PROTECTED", "HIDDEN"]
        """
        lower_text = text.lower() if text else ""
        lower_fn = filename.lower() if filename else ""
        combined_text = f"{lower_fn} {lower_text}"

        # 1. ID Documents check
        has_aadhaar = bool(RE_AADHAAR.search(text or ""))
        has_pan = bool(RE_PAN.search(text or ""))
        has_voter = bool(RE_VOTER_ID.search(text or ""))
        has_passport = bool(RE_PASSPORT.search(text or "")) and ("passport" in combined_text or "republic of india" in combined_text)
        has_id_keywords = any(k in combined_text for k in KEYWORDS_ID)

        if has_aadhaar or has_pan or has_passport or has_voter or (has_id_keywords and ("card" in combined_text or "identity" in combined_text)):
            protect_ids = self.db.get_privacy_setting("protect_ids", "true") == "true"
            state = "PROTECTED" if protect_ids else "NORMAL"
            return "ID_DOCUMENT", state, 0.95

        # 2. Banking & Finance check
        has_ifsc = bool(RE_IFSC.search(text or ""))
        has_card = bool(RE_CREDIT_CARD.search(text or ""))
        has_acct = bool(RE_ACCOUNT_NUMBER.search(text or ""))
        banking_count = sum(1 for k in KEYWORDS_BANKING if k in combined_text)

        if has_card or has_ifsc or (has_acct and banking_count >= 1) or banking_count >= 3:
            protect_banking = self.db.get_privacy_setting("protect_banking", "true") == "true"
            state = "PROTECTED" if protect_banking else "NORMAL"
            return "BANKING_FINANCE", state, 0.90

        # 3. Confidential records check
        has_confidential = any(k in combined_text for k in KEYWORDS_CONFIDENTIAL)
        if has_confidential:
            protect_conf = self.db.get_privacy_setting("protect_confidential", "true") == "true"
            state = "PROTECTED" if protect_conf else "NORMAL"
            return "CONFIDENTIAL", state, 0.85

        return "NONE", "NORMAL", 0.0

    # ── PRIVACY ACCESS SCOPE & SANITIZATION ───────────────────────────────────

    def get_privacy_scope(self, is_authenticated: bool) -> str:
        """Returns the privacy query scope: 'PRIVATE' if authenticated else 'NORMAL'."""
        return "PRIVATE" if is_authenticated else "NORMAL"

    def sanitize_results(
        self,
        results: List[Dict[str, Any]],
        is_authenticated: bool,
    ) -> List[Dict[str, Any]]:
        """Sanitizes candidate search results according to privacy settings and authentication.
        
        Hidden files are completely excluded in unauthenticated mode.
        Protected files are sanitized (masked name, hidden preview/snippet) when locked.
        """
        sanitized = []
        hide_fn_setting = self.db.get_privacy_setting("hide_protected_filename", "true") == "true"
        preview_mode = self.db.get_privacy_setting("protected_image_preview", "blur")
        metadata_mode = self.db.get_privacy_setting("protected_metadata_mode", "limited")
        protected_visibility = self.db.get_privacy_setting("protected_files_visibility", "show")

        for r in results:
            item = dict(r)
            state = (item.get("privacy_state") or "NORMAL").upper()

            # 1. HIDDEN files
            if state == "HIDDEN":
                if not is_authenticated:
                    # Never leak hidden files to unauthenticated users
                    continue
                # When authenticated in private mode, show with privacy flag
                item["is_hidden"] = True
                item["is_locked"] = False
                sanitized.append(item)
                continue

            # 2. PROTECTED files
            if state == "PROTECTED":
                if not is_authenticated:
                    if protected_visibility == "hide":
                        # If user configured to completely hide protected files from normal search
                        continue

                    # Mask protected file contents
                    item["is_protected"] = True
                    item["is_locked"] = True

                    file_type = item.get("file_type") or "file"
                    ext = os.path.splitext(item.get("file_name", ""))[1]

                    if hide_fn_setting:
                        if file_type == "image":
                            item["file_name"] = f"Protected Image{ext}"
                        elif file_type == "document":
                            item["file_name"] = f"Protected Document{ext}"
                        else:
                            item["file_name"] = f"Protected File{ext}"
                        
                        # Obfuscate file path to prevent leaking personal info
                        orig_path = item.get("file_path", "")
                        item["file_path"] = os.path.join(os.path.dirname(orig_path), item["file_name"])

                    # Mask preview / thumbnail
                    if preview_mode == "hide":
                        item["thumbnail_path"] = None
                        item["preview_path"] = None
                    else:  # blur
                        item["blur_preview"] = True

                    # Mask OCR and content snippets
                    item["snippet"] = "[Protected content - Enter password to view]"
                    item["ocr_text"] = ""
                    item["extracted_text"] = ""
                    item["match_evidence"] = "Protected content matched search criteria"

                    # Mask sensitive metadata if configured
                    if metadata_mode in ("limited", "hide"):
                        item["entities"] = []
                        item["detected_faces"] = []
                else:
                    item["is_protected"] = True
                    item["is_locked"] = False

                sanitized.append(item)
                continue

            # 3. NORMAL files
            item["is_protected"] = False
            item["is_locked"] = False
            item["is_hidden"] = False
            sanitized.append(item)

        return sanitized

    def sanitize_person_profile(
        self,
        person_data: Dict[str, Any],
        is_authenticated: bool,
    ) -> Dict[str, Any]:
        """Sanitizes person profile details, ensuring hidden files are never exposed."""
        profile = dict(person_data)
        if not is_authenticated:
            # Filter files list to exclude HIDDEN files
            if "files" in profile and isinstance(profile["files"], list):
                profile["files"] = [
                    f for f in profile["files"]
                    if (f.get("privacy_state") or "NORMAL").upper() != "HIDDEN"
                ]
                profile["file_count"] = len(profile["files"])
        return profile
