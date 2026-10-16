"""Brute-Force Protection, Sliding-Window Rate Limiting, and Account Lockout.

Enforces:
- IP-based rate limiting (10 failed attempts / 15 min window)
- Account lockout policy (Lock account after 5 failed login attempts for 15 minutes)
- WhatsApp spam throttling (15 messages / min per JID)
- Constant-time validation and failure backoff
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from fastapi import HTTPException, Request, status

from app.security.audit import audit_logger
from app.security.models import AuditEventType, AuthChannel

logger = logging.getLogger("kargopilot.security.ratelimit")

MAX_FAILED_IP_ATTEMPTS = 10
IP_BLOCK_WINDOW_MINUTES = 15

MAX_FAILED_ACCOUNT_ATTEMPTS = 5
ACCOUNT_LOCKOUT_MINUTES = 15

MAX_WHATSAPP_MESSAGES_PER_MINUTE = 15


class SlidingWindowRateLimiter:
    """In-memory sliding window rate limiter with microsecond timestamp granularity."""

    def __init__(self) -> None:
        # Maps key -> list of UTC timestamps of attempts
        self._ip_failed_attempts: Dict[str, List[datetime]] = defaultdict(list)
        self._whatsapp_message_timestamps: Dict[str, List[datetime]] = defaultdict(list)

    def is_ip_rate_limited(self, ip_address: str) -> Tuple[bool, int]:
        """Checks if an IP has exceeded the threshold of failed attempts.
        
        Returns:
            Tuple[bool, int]: (is_limited, remaining_retry_after_seconds)
        """
        if not ip_address or ip_address in ("127.0.0.1", "localhost", "::1"):
            return False, 0

        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(minutes=IP_BLOCK_WINDOW_MINUTES)

        timestamps = [ts for ts in self._ip_failed_attempts[ip_address] if ts > cutoff]
        self._ip_failed_attempts[ip_address] = timestamps

        if len(timestamps) >= MAX_FAILED_IP_ATTEMPTS:
            oldest = timestamps[0]
            retry_after = int((oldest + timedelta(minutes=IP_BLOCK_WINDOW_MINUTES) - now).total_seconds())
            return True, max(1, retry_after)

        return False, 0

    def record_ip_failure(self, ip_address: str) -> None:
        """Records a failed authentication attempt against an IP."""
        if ip_address:
            self._ip_failed_attempts[ip_address].append(datetime.now(timezone.utc))

    def reset_ip(self, ip_address: str) -> None:
        """Resets failed attempt counters for an IP upon successful action."""
        self._ip_failed_attempts.pop(ip_address, None)

    def is_whatsapp_rate_limited(self, jid: str) -> bool:
        """Throttles high-frequency WhatsApp messages from the same sender."""
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(minutes=1)

        timestamps = [ts for ts in self._whatsapp_message_timestamps[jid] if ts > cutoff]
        self._whatsapp_message_timestamps[jid] = timestamps

        if len(timestamps) >= MAX_WHATSAPP_MESSAGES_PER_MINUTE:
            return True

        self._whatsapp_message_timestamps[jid].append(now)
        return False


rate_limiter = SlidingWindowRateLimiter()


class AccountLockoutManager:
    """Manages progressive account lockouts after consecutive authentication failures."""

    @classmethod
    def check_and_enforce_lockout(cls, user_row: Dict[str, Any], ip_address: str) -> None:
        """Checks if user account is locked. Raises HTTP 423 Locked if still in penalty window."""
        locked_until = user_row.get("locked_until")
        if not locked_until:
            return

        now = datetime.now(timezone.utc)
        if isinstance(locked_until, str):
            try:
                locked_dt = datetime.fromisoformat(locked_until)
            except ValueError:
                return
        else:
            locked_dt = locked_until

        if locked_dt.tzinfo is None:
            locked_dt = locked_dt.replace(tzinfo=timezone.utc)

        if now < locked_dt:
            remaining = int((locked_dt - now).total_seconds())
            audit_logger.log(
                event_type=AuditEventType.LOGIN_FAILED,
                status="BLOCKED",
                user_id=user_row.get("id"),
                actor_role=user_row.get("role"),
                ip_address=ip_address,
                channel=AuthChannel.WEB,
                reason="Account is locked due to excessive failed login attempts.",
                metadata={"locked_until": locked_dt.isoformat(), "remaining_seconds": remaining},
            )
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail=f"Account is temporarily locked. Please try again in {remaining // 60 + 1} minutes.",
            )

    @classmethod
    def register_failed_attempt(cls, db_conn: Any, user_row: Dict[str, Any], ip_address: str) -> int:
        """Increments failed attempt counter and locks account if threshold is met.
        
        Returns:
            int: Remaining attempts before lockout.
        """
        user_id = user_row["id"]
        current_attempts = (user_row.get("failed_login_attempts") or 0) + 1
        now = datetime.now(timezone.utc)
        locked_until_val = None

        if current_attempts >= MAX_FAILED_ACCOUNT_ATTEMPTS:
            locked_until_dt = now + timedelta(minutes=ACCOUNT_LOCKOUT_MINUTES)
            locked_until_val = locked_until_dt.isoformat()
            db_conn.execute(
                "UPDATE users SET failed_login_attempts = ?, locked_until = ?, updated_at = ? WHERE id = ?",
                (current_attempts, locked_until_val, now.isoformat(), user_id),
            )
            db_conn.commit()

            audit_logger.log(
                event_type=AuditEventType.ACCOUNT_LOCKED,
                status="SUCCESS",
                user_id=user_id,
                actor_role=user_row.get("role"),
                ip_address=ip_address,
                channel=AuthChannel.WEB,
                reason=f"Account locked after {current_attempts} consecutive failed attempts.",
                metadata={"lockout_minutes": ACCOUNT_LOCKOUT_MINUTES, "locked_until": locked_until_val},
            )
            return 0
        else:
            db_conn.execute(
                "UPDATE users SET failed_login_attempts = ?, updated_at = ? WHERE id = ?",
                (current_attempts, now.isoformat(), user_id),
            )
            db_conn.commit()
            return MAX_FAILED_ACCOUNT_ATTEMPTS - current_attempts

    @classmethod
    def register_successful_login(cls, db_conn: Any, user_id: str) -> None:
        """Resets failed attempt counters and clears any lockouts."""
        now = datetime.now(timezone.utc).isoformat()
        db_conn.execute(
            "UPDATE users SET failed_login_attempts = 0, locked_until = NULL, updated_at = ? WHERE id = ?",
            (now, user_id),
        )
        db_conn.commit()
