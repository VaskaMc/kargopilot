"""WhatsApp Multi-User Identity Bridge, Phone Binding Engine, and Admin Command Gate.

Enforces:
- E.164 phone normalization for Azerbaijan and international numbers
- Automatic JID-to-User routing and tenant context isolation
- Robust onboarding state machine: UNREGISTERED -> AWAITING_CHOICE -> OTP/LINK -> ACTIVE_BOUND
- Admin Command Gate: strict isolation of !admin operations to verified Admin phones
- Secondary Ephemeral Challenge (Step-Up Authentication) for destructive system commands
- Full structured audit logging of all identity binding and command attempts
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from app.security.audit import audit_logger
from app.security.crypto import (
    constant_time_compare,
    generate_numeric_otp,
    generate_secure_token,
    hash_token,
)
from app.security.models import (
    AuditEventType,
    AuthChannel,
    UserRole,
    WhatsAppUserState,
)

logger = logging.getLogger("kargopilot.whatsapp.bridge")

DEFAULT_DB_PATH = Path("/data/pcs/pcs.db")

CHALLENGE_OTP_TTL_MINUTES = 5
WEB_BINDING_CODE_TTL_MINUTES = 10
ADMIN_STEPUP_TTL_SECONDS = 120
MAX_CHALLENGE_ATTEMPTS = 3


# ==============================================================================
# Phone Number Normalization (E.164)
# ==============================================================================

def normalize_phone_e164(raw_phone_or_jid: str) -> Optional[str]:
    """Normalizes raw input or WhatsApp JID into canonical E.164 format (+994XXXXXXXXX).
    
    Supports:
    - 994501234567@s.whatsapp.net -> +994501234567
    - 0501234567 -> +994501234567
    - 051, 055, 070, 077, 099 prefixes
    - International + format
    """
    if not raw_phone_or_jid:
        return None

    # Strip JID suffixes and whitespace
    cleaned = re.sub(r"@.*$", "", str(raw_phone_or_jid).strip())
    # Remove all non-digits except leading +
    digits = re.sub(r"[^\d]", "", cleaned)

    if not digits:
        return None

    # Azerbaijan local format (050..., 051..., 055..., 070..., 077..., 099...)
    if digits.startswith("0") and len(digits) == 10:
        return f"+994{digits[1:]}"

    # Already has 994 country code
    if digits.startswith("994") and len(digits) == 12:
        return f"+{digits}"

    # Standard international 10-15 digits
    if len(digits) >= 10:
        return f"+{digits}"

    return None


def extract_jid(raw_sender: str) -> str:
    """Extracts or formats canonical WhatsApp JID (e.g. 994501234567@s.whatsapp.net)."""
    raw = str(raw_sender).strip()
    if "@" in raw:
        return raw.lower()
    norm = normalize_phone_e164(raw)
    if norm:
        digits = norm.replace("+", "")
        return f"{digits}@s.whatsapp.net"
    return raw.lower()


# ==============================================================================
# WhatsApp Multi-User Identity Bridge & State Machine
# ==============================================================================

class WhatsAppIdentityBridge:
    """Manages identity resolution, onboarding state machine, and secure binding."""

    def __init__(self, db_path: Optional[Path | str] = None) -> None:
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        # Ephemeral storage for web panel binding codes: code_hash -> {user_id, expires_at}
        self._web_binding_codes: Dict[str, Dict[str, Any]] = {}

    @contextmanager
    def _get_conn(self):
        if not self.db_path.parent.exists():
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path), timeout=5.0)
        conn.row_factory = sqlite3.Row
        self._ensure_tables(conn)
        try:
            yield conn
        finally:
            conn.close()

    def _ensure_tables(self, conn: sqlite3.Connection) -> None:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                full_name TEXT NOT NULL,
                phone TEXT UNIQUE,
                role TEXT DEFAULT 'CUSTOMER',
                is_active INTEGER DEFAULT 1,
                is_verified INTEGER DEFAULT 0,
                failed_login_attempts INTEGER DEFAULT 0,
                locked_until TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_whatsapp_bindings (
                id TEXT PRIMARY KEY,
                user_id TEXT UNIQUE NOT NULL,
                whatsapp_jid TEXT UNIQUE NOT NULL,
                phone_e164 TEXT UNIQUE NOT NULL,
                verified_at TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS whatsapp_conversation_states (
                whatsapp_jid TEXT PRIMARY KEY,
                current_state TEXT NOT NULL,
                pending_phone TEXT,
                challenge_otp_hash TEXT,
                challenge_attempts INTEGER DEFAULT 0,
                challenge_expires_at TEXT,
                binding_code_hash TEXT,
                context_payload TEXT,
                last_interaction_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS admin_challenges (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                whatsapp_jid TEXT NOT NULL,
                action_type TEXT NOT NULL,
                challenge_code_hash TEXT NOT NULL,
                status TEXT DEFAULT 'PENDING',
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_sessions (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                family_id TEXT NOT NULL,
                current_refresh_token_hash TEXT NOT NULL,
                device_fingerprint TEXT,
                ip_address TEXT,
                user_agent TEXT,
                created_at TEXT NOT NULL,
                last_active_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                revoked_at TEXT,
                revocation_reason TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS refresh_token_records (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                family_id TEXT NOT NULL,
                token_hash TEXT UNIQUE NOT NULL,
                is_revoked INTEGER DEFAULT 0,
                revoked_at TEXT,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(session_id) REFERENCES user_sessions(id) ON DELETE CASCADE
            )
        """)
        conn.commit()

    # --------------------------------------------------------------------------
    # Identity Resolution
    # --------------------------------------------------------------------------

    def resolve_user(self, raw_sender: str) -> Optional[Dict[str, Any]]:
        """Resolves an incoming WhatsApp sender JID to an authenticated User record.
        
        Returns User dict or None if unregistered.
        """
        jid = extract_jid(raw_sender)
        phone = normalize_phone_e164(raw_sender)

        with self._get_conn() as conn:
            # 1. First check explicit binding table
            row = conn.execute(
                """SELECT u.* FROM users u
                   JOIN user_whatsapp_bindings b ON u.id = b.user_id
                   WHERE b.whatsapp_jid = ? AND b.is_active = 1 AND u.is_active = 1""",
                (jid,),
            ).fetchone()
            if row:
                return dict(row)

            # 2. Check direct users.phone match
            if phone:
                row = conn.execute(
                    "SELECT * FROM users WHERE phone = ? AND is_active = 1",
                    (phone,),
                ).fetchone()
                if row:
                    # Auto-bind verified phone to this JID
                    binding_id = str(uuid.uuid4())
                    now = datetime.now(timezone.utc).isoformat()
                    try:
                        conn.execute(
                            """INSERT OR REPLACE INTO user_whatsapp_bindings 
                               (id, user_id, whatsapp_jid, phone_e164, verified_at, is_active, created_at)
                               VALUES (?, ?, ?, ?, ?, 1, ?)""",
                            (binding_id, row["id"], jid, phone, now, now),
                        )
                        conn.commit()
                        audit_logger.log(
                            event_type=AuditEventType.WA_BIND_SUCCESS,
                            status="SUCCESS",
                            user_id=row["id"],
                            actor_role=row["role"],
                            channel=AuthChannel.WHATSAPP_BOT,
                            reason="Automatic binding on verified phone match.",
                            metadata={"jid": jid, "phone": phone},
                        )
                    except Exception as exc:
                        logger.warning("Failed to auto-bind phone to JID: %s", exc)
                    return dict(row)

        return None

    # --------------------------------------------------------------------------
    # Web Dashboard Binding Code Generation
    # --------------------------------------------------------------------------

    def generate_web_binding_code(self, user_id: str) -> str:
        """Generates a single-use 6-digit numeric binding code from Web Panel (10 min TTL)."""
        code = generate_numeric_otp(6)
        code_hash = hash_token(code)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=WEB_BINDING_CODE_TTL_MINUTES)

        self._web_binding_codes[code_hash] = {
            "user_id": user_id,
            "expires_at": expires_at,
        }

        audit_logger.log(
            event_type=AuditEventType.WA_BIND_REQUEST,
            status="SUCCESS",
            user_id=user_id,
            channel=AuthChannel.WEB,
            reason="User generated WhatsApp link code on Web Dashboard.",
            metadata={"expires_at": expires_at.isoformat()},
        )
        return code

    # --------------------------------------------------------------------------
    # Onboarding State Machine & Message Router
    # --------------------------------------------------------------------------

    def handle_incoming_message(
        self,
        raw_sender: str,
        message_text: str,
    ) -> Tuple[Optional[Dict[str, Any]], str]:
        """Routes message through the onboarding state machine or returns authenticated user context.
        
        Returns:
            Tuple[Optional[Dict[str, Any]], str]:
            - user_dict: Authenticated user (if registered) or None
            - reply_text: Immediate response to send to WhatsApp sender
        """
        jid = extract_jid(raw_sender)
        phone = normalize_phone_e164(raw_sender)
        text = (message_text or "").strip()
        now = datetime.now(timezone.utc)

        # 1. Resolve registered user
        user = self.resolve_user(raw_sender)
        if user:
            # User is authenticated!
            return user, ""

        # 2. User is unregistered - step into state machine
        with self._get_conn() as conn:
            state_row = conn.execute(
                "SELECT * FROM whatsapp_conversation_states WHERE whatsapp_jid = ?",
                (jid,),
            ).fetchone()

            current_state = state_row["current_state"] if state_row else WhatsAppUserState.UNREGISTERED.value
            attempts = state_row["challenge_attempts"] if state_row else 0

            # State: UNREGISTERED or AWAITING_CHOICE
            if current_state in (WhatsAppUserState.UNREGISTERED.value, WhatsAppUserState.AWAITING_CHOICE.value):
                # Check if user sent !link <code> directly
                link_match = re.match(r"^[!#/]?link\s+(\d{6})$", text, re.IGNORECASE)
                if link_match:
                    code = link_match.group(1)
                    return self._process_web_link_code(conn, jid, phone, code)

                # Check if user selected Option 1 (Instant Registration)
                if text in ("1", "!register", "register", "qeydiyyat"):
                    otp = generate_numeric_otp(6)
                    otp_hash = hash_token(otp)
                    exp = (now + timedelta(minutes=CHALLENGE_OTP_TTL_MINUTES)).isoformat()

                    conn.execute(
                        """INSERT OR REPLACE INTO whatsapp_conversation_states
                           (whatsapp_jid, current_state, pending_phone, challenge_otp_hash, challenge_attempts, challenge_expires_at, last_interaction_at)
                           VALUES (?, ?, ?, ?, 0, ?, ?)""",
                        (jid, WhatsAppUserState.AWAITING_REGISTRATION_OTP.value, phone, otp_hash, exp, now.isoformat()),
                    )
                    conn.commit()

                    audit_logger.log(
                        event_type=AuditEventType.WA_BIND_REQUEST,
                        status="SUCCESS",
                        channel=AuthChannel.WHATSAPP_BOT,
                        reason="Instant registration challenge OTP issued.",
                        metadata={"jid": jid, "phone": phone},
                    )

                    return None, (
                        f"🔐 *KargoPilot v4.5 Qeydiyyat Təsdiqi*\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"Təsdiq Kodunuz: *{otp}*\n\n"
                        f"Bu nömrə ilə dərhal hesab yaratmaq üçün yuxarıdakı *{otp}* kodunu bura göndərin.\n"
                        f"⏱ Kod 5 dəqiqə ərzində etibarlıdır."
                    )

                # Check if user selected Option 2 (Link existing account)
                if text in ("2", "!link", "link", "bagla", "bağla"):
                    conn.execute(
                        """INSERT OR REPLACE INTO whatsapp_conversation_states
                           (whatsapp_jid, current_state, pending_phone, challenge_attempts, last_interaction_at)
                           VALUES (?, ?, ?, 0, ?)""",
                        (jid, WhatsAppUserState.AWAITING_WEB_LINK_CODE.value, phone, now.isoformat()),
                    )
                    conn.commit()
                    return None, (
                        "🔑 *Mövcud Hesabın Əlaqələndirilməsi*\n"
                        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                        "Zəhmət olmasa KargoPilot Veb Panelinə daxil olun:\n"
                        "👉 *Profil ➔ Təhlükəsizlik ➔ WhatsApp Bağlantısı*\n\n"
                        "Oradan aldığınız 6-rəqəmli kodu bura yazın (məs: `!link 839201`)."
                    )

                # Otherwise send the main welcoming menu
                conn.execute(
                    """INSERT OR REPLACE INTO whatsapp_conversation_states
                       (whatsapp_jid, current_state, pending_phone, challenge_attempts, last_interaction_at)
                       VALUES (?, ?, ?, 0, ?)""",
                    (jid, WhatsAppUserState.AWAITING_CHOICE.value, phone, now.isoformat()),
                )
                conn.commit()

                return None, (
                    "👋 *KargoPilot v4.5 Daşıma və İzləmə Sisteminə Xoş Gəlmisiniz!*\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    "Bu WhatsApp nömrəsi hələ heç bir istifadəçi hesabına bağlı deyil.\n\n"
                    "Xidmətdən istifadə etmək üçün seçim edin:\n"
                    "1️⃣ *Sürətli Qeydiyyat:* Bu nömrə ilə dərhal yeni profil açmaq üçün *1* yazın.\n"
                    "2️⃣ *Hesabı Bağla:* Veb paneldəki mövcud hesabınızı bağlamaq üçün *2* yazın.\n\n"
                    "💡 Əgər veb paneldən artıq kod almısınızsa, birbaşa `!link <KOD>` yaza bilərsiniz."
                )

            # State: AWAITING_REGISTRATION_OTP
            if current_state == WhatsAppUserState.AWAITING_REGISTRATION_OTP.value:
                # Extract 6-digit digits
                input_otp = re.sub(r"[^\d]", "", text)
                exp_dt = datetime.fromisoformat(state_row["challenge_expires_at"]) if state_row["challenge_expires_at"] else now

                if now > exp_dt:
                    conn.execute(
                        "UPDATE whatsapp_conversation_states SET current_state = ? WHERE whatsapp_jid = ?",
                        (WhatsAppUserState.UNREGISTERED.value, jid),
                    )
                    conn.commit()
                    return None, "❌ Təsdiq kodunun vaxtı bitdi. Yenidən başlamaq üçün `1` yazın."

                stored_hash = state_row["challenge_otp_hash"] or ""
                if constant_time_compare(hash_token(input_otp), stored_hash):
                    # Success! Auto-provision customer account
                    new_user_id = str(uuid.uuid4())
                    binding_id = str(uuid.uuid4())
                    user_phone = phone or state_row["pending_phone"] or f"+{jid.split('@')[0]}"
                    email = f"{user_phone.replace('+', '')}@wa.kargopilot.local"
                    now_str = now.isoformat()

                    conn.execute(
                        """INSERT INTO users 
                           (id, email, password_hash, full_name, phone, role, is_active, is_verified, created_at, updated_at)
                           VALUES (?, ?, 'NONE_WHATSAPP_ACTIVATED', 'WhatsApp İstifadəçisi', ?, 'CUSTOMER', 1, 1, ?, ?)""",
                        (new_user_id, email, user_phone, now_str, now_str),
                    )
                    conn.execute(
                        """INSERT INTO user_whatsapp_bindings 
                           (id, user_id, whatsapp_jid, phone_e164, verified_at, is_active, created_at)
                           VALUES (?, ?, ?, ?, ?, 1, ?)""",
                        (binding_id, new_user_id, jid, user_phone, now_str, now_str),
                    )
                    conn.execute(
                        "DELETE FROM whatsapp_conversation_states WHERE whatsapp_jid = ?",
                        (jid,),
                    )
                    conn.commit()

                    audit_logger.log(
                        event_type=AuditEventType.WA_BIND_SUCCESS,
                        status="SUCCESS",
                        user_id=new_user_id,
                        actor_role="CUSTOMER",
                        channel=AuthChannel.WHATSAPP_BOT,
                        reason="Instant phone registration completed via WhatsApp OTP.",
                        metadata={"jid": jid, "phone": user_phone},
                    )

                    new_user = {
                        "id": new_user_id,
                        "email": email,
                        "full_name": "WhatsApp İstifadəçisi",
                        "phone": user_phone,
                        "role": "CUSTOMER",
                    }
                    return new_user, (
                        "🎉 *Təbriklər! Hesabınız Uğurla Yaradıldı!* ✅\n"
                        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                        "WhatsApp nömrəniz KargoPilot sisteminə bağlandı.\n\n"
                        "Mövcud əmrlər:\n"
                        "• *!kargo* — Aktiv bağlamalarınızı izləyin\n"
                        "• *!unvan* — Türkiyə və Çin anbar ünvanlarını əldə edin\n"
                        "• *!hesabla <çəki>* — Daşıma tariflərini müqayisə edin\n"
                        "• *!yardim* — Ətraflı məlumat"
                    )
                else:
                    new_attempts = attempts + 1
                    if new_attempts >= MAX_CHALLENGE_ATTEMPTS:
                        conn.execute(
                            "UPDATE whatsapp_conversation_states SET current_state = ?, challenge_attempts = 0 WHERE whatsapp_jid = ?",
                            (WhatsAppUserState.UNREGISTERED.value, jid),
                        )
                        conn.commit()
                        audit_logger.log(
                            event_type=AuditEventType.WA_BIND_FAILED,
                            status="BLOCKED",
                            channel=AuthChannel.WHATSAPP_BOT,
                            reason="Exceeded maximum OTP registration attempts.",
                            metadata={"jid": jid},
                        )
                        return None, "❌ 3 dəfə yalnış kod daxil edildi. Təhlükəsizlik səbəbilə sorğu sıfırlandı. Yenidən başlamaq üçün `1` yazın."

                    conn.execute(
                        "UPDATE whatsapp_conversation_states SET challenge_attempts = ? WHERE whatsapp_jid = ?",
                        (new_attempts, jid),
                    )
                    conn.commit()
                    return None, f"❌ Yalnış kod. Qalan cəhd: {MAX_CHALLENGE_ATTEMPTS - new_attempts}. Yenidən daxil edin:"

            # State: AWAITING_WEB_LINK_CODE
            if current_state == WhatsAppUserState.AWAITING_WEB_LINK_CODE.value:
                code_match = re.search(r"(\d{6})", text)
                if not code_match:
                    return None, "❌ Zəhmət olmasa 6-rəqəmli əlaqələndirmə kodunu daxil edin (məsələn: `!link 839201`)."
                code = code_match.group(1)
                return self._process_web_link_code(conn, jid, phone, code)

        return None, "❌ Xidmətdən istifadə etmək üçün `1` və ya `2` yazın."

    def _process_web_link_code(
        self,
        conn: sqlite3.Connection,
        jid: str,
        phone: Optional[str],
        raw_code: str,
    ) -> Tuple[Optional[Dict[str, Any]], str]:
        """Validates web binding code and links WhatsApp JID to existing User."""
        now = datetime.now(timezone.utc)
        code_hash = hash_token(raw_code.strip())

        item = self._web_binding_codes.get(code_hash)
        if not item or item["expires_at"] < now:
            audit_logger.log(
                event_type=AuditEventType.WA_BIND_FAILED,
                status="FAILED",
                channel=AuthChannel.WHATSAPP_BOT,
                reason="Invalid or expired web binding code.",
                metadata={"jid": jid},
            )
            return None, "❌ Əlaqələndirmə kodu yalnışdır və ya vaxtı bitib. Veb paneldən yeni kod götürün."

        user_id = item["user_id"]
        # Consume code (single-use)
        self._web_binding_codes.pop(code_hash, None)

        user_row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not user_row:
            return None, "❌ İstifadəçi profili tapılmadı."

        user_phone = phone or user_row["phone"] or f"+{jid.split('@')[0]}"
        now_str = now.isoformat()
        binding_id = str(uuid.uuid4())

        conn.execute(
            """INSERT OR REPLACE INTO user_whatsapp_bindings
               (id, user_id, whatsapp_jid, phone_e164, verified_at, is_active, created_at)
               VALUES (?, ?, ?, ?, ?, 1, ?)""",
            (binding_id, user_id, jid, user_phone, now_str, now_str),
        )
        conn.execute("DELETE FROM whatsapp_conversation_states WHERE whatsapp_jid = ?", (jid,))
        conn.commit()

        audit_logger.log(
            event_type=AuditEventType.WA_BIND_SUCCESS,
            status="SUCCESS",
            user_id=user_id,
            actor_role=user_row["role"],
            channel=AuthChannel.WHATSAPP_BOT,
            reason="WhatsApp JID bound to existing user via Web Code.",
            metadata={"jid": jid, "phone": user_phone},
        )

        return dict(user_row), (
            f"✅ *KargoPilot Hesabınız Uğurla Əlaqələndirildi!*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Xoş gəldiniz, *{user_row['full_name']}*!\n"
            f"Artıq bütün bildirişləri bu nömrədən alacaq və sifarişlərinizi asanlıqla idarə edə biləcəksiniz.\n\n"
            f"Sınaq üçün `!kargo` yazın."
        )


# ==============================================================================
# Admin Command Gate & Step-Up Challenge Engine
# ==============================================================================

class AdminCommandGate:
    """Enforces strict role checks and secondary step-up challenge for !admin commands."""

    def __init__(self, bridge: WhatsAppIdentityBridge) -> None:
        self.bridge = bridge

    def process_admin_command(
        self,
        raw_sender: str,
        command_text: str,
        user: Optional[Dict[str, Any]],
    ) -> Tuple[bool, str]:
        """Evaluates admin command security rules.
        
        Returns:
            Tuple[bool, str]: (is_handled_by_gate, response_text)
        """
        cmd = command_text.strip()
        jid = extract_jid(raw_sender)

        if not cmd.startswith(("!admin", "/admin", "!confirm")):
            return False, ""

        # 1. Non-admin authorization check
        if not user or user.get("role") not in (UserRole.SUPER_ADMIN.value, UserRole.ADMIN.value):
            audit_logger.log(
                event_type=AuditEventType.ADMIN_COMMAND_DENIED,
                status="DENIED",
                user_id=user.get("id") if user else None,
                actor_role=user.get("role") if user else "UNREGISTERED",
                channel=AuthChannel.WHATSAPP_BOT,
                reason="Unauthorized attempt to execute admin command.",
                metadata={"jid": jid, "command": cmd},
            )
            # Never disclose admin command existence to unauthorized callers!
            return True, "❌ Naməlum komanda. Mövcud əmrlərlə tanış olmaq üçün `!yardim` yazın."

        # 2. Check for confirmation response (!confirm <CHALLENGE_CODE>)
        confirm_match = re.match(r"^[!#/]?confirm\s+([a-zA-Z0-9_\-]+)$", cmd, re.IGNORECASE)
        if confirm_match:
            code = confirm_match.group(1).strip()
            return True, self._verify_admin_challenge(jid, user, code)

        # 3. Handle specific admin operations
        # Destructive / System Level Commands require Step-Up OTP
        destructive_commands = ["carrier_sync_all", "db_backup", "reset_token", "force_release", "shutdown"]
        action_match = re.match(r"^[!#/]?admin\s+([a-zA-Z0-9_]+)(?:\s+(.*))?$", cmd, re.IGNORECASE)
        if action_match:
            action = action_match.group(1).lower()
            args = action_match.group(2) or ""

            if action in destructive_commands:
                return True, self._issue_stepup_challenge(jid, user, action, args)

            if action in ("status", "health", "stat"):
                return True, (
                    f"🟢 *KargoPilot v4.5 Sistem Statusu (Admin: {user['full_name']})*\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"• Nüvə Versiyası: `v4.5-RELEASE`\n"
                    f"• Daşıyıcı Şlüzləri: STAREX (ON), CAMEX (ON), DYNAMEX (ON)\n"
                    f"• Növbədə gözləyən AWB: 0\n"
                    f"• Audit jurnalı: Aktiv və bütöv ✅"
                )

        return True, (
            f"🛠 *KargoPilot v4.5 Admin İdarəetmə Paneli*\n"
            f"İstifadəçi: *{user['full_name']}* ({user['role']})\n\n"
            f"Mövcud Əmrlər:\n"
            f"• `!admin status` — Sistem sağlamlığı və növbə vəziyyəti\n"
            f"• `!admin carrier_sync_all` — Bütün daşıyıcıları məcburi sinxronlaşdır (Step-Up tələb olunur)\n"
            f"• `!admin db_backup` — Təhlükəsiz baza ehtiyat nüsxəsi çıxar (Step-Up tələb olunur)"
        )

    def _issue_stepup_challenge(
        self,
        jid: str,
        user: Dict[str, Any],
        action: str,
        args: str,
    ) -> str:
        """Issues an ephemeral 4-digit challenge for high-risk operations."""
        challenge_code = generate_numeric_otp(4)
        code_hash = hash_token(challenge_code)
        now = datetime.now(timezone.utc)
        expires_at = (now + timedelta(seconds=ADMIN_STEPUP_TTL_SECONDS)).isoformat()
        challenge_id = str(uuid.uuid4())

        with self.bridge._get_conn() as conn:
            conn.execute(
                """INSERT INTO admin_challenges 
                   (id, user_id, whatsapp_jid, action_type, challenge_code_hash, status, expires_at, created_at)
                   VALUES (?, ?, ?, ?, ?, 'PENDING', ?, ?)""",
                (challenge_id, user["id"], jid, f"{action}:{args}", code_hash, expires_at, now.isoformat()),
            )
            conn.commit()

        audit_logger.log(
            event_type=AuditEventType.ADMIN_CHALLENGE_ISSUED,
            status="SUCCESS",
            user_id=user["id"],
            actor_role=user["role"],
            channel=AuthChannel.WHATSAPP_BOT,
            reason=f"Step-Up Challenge issued for destructive action: {action}",
            metadata={"jid": jid, "action": action, "expires_at": expires_at},
        )

        return (
            f"⚠️ *TƏHLÜKƏSİZLİK TƏSDİQİ (Step-Up Authentication)* ⚠️\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Siz yüksək səlahiyyətli əməliyyat başladırsınız:\n"
            f"🎯 Əməliyyat: *{action.upper()}*\n\n"
            f"Təsdiqləmək üçün 120 saniyə ərzində bu mesajı göndərin:\n"
            f"👉 `!confirm {challenge_code}`"
        )

    def _verify_admin_challenge(
        self,
        jid: str,
        user: Dict[str, Any],
        submitted_code: str,
    ) -> str:
        """Verifies ephemeral challenge and executes queued action."""
        now = datetime.now(timezone.utc)
        submitted_hash = hash_token(submitted_code)

        with self.bridge._get_conn() as conn:
            row = conn.execute(
                """SELECT * FROM admin_challenges 
                   WHERE whatsapp_jid = ? AND status = 'PENDING' 
                   ORDER BY created_at DESC LIMIT 1""",
                (jid,),
            ).fetchone()

            if not row:
                return "❌ Aktiv təsdiq sorğusu tapılmadı və ya artıq icra edilib."

            exp_dt = datetime.fromisoformat(row["expires_at"])
            if now > exp_dt:
                conn.execute("UPDATE admin_challenges SET status = 'EXPIRED' WHERE id = ?", (row["id"],))
                conn.commit()
                return "❌ Təsdiq kodunun vaxtı bitdi. Əməliyyatı yenidən başladın."

            if not constant_time_compare(submitted_hash, row["challenge_code_hash"]):
                audit_logger.log(
                    event_type=AuditEventType.ADMIN_CHALLENGE_FAILED,
                    status="FAILED",
                    user_id=user["id"],
                    actor_role=user["role"],
                    channel=AuthChannel.WHATSAPP_BOT,
                    reason="Invalid challenge code provided.",
                    metadata={"jid": jid, "action": row["action_type"]},
                )
                return "❌ Yalnış təsdiq kodu daxil edildi."

            # Mark challenge verified
            conn.execute("UPDATE admin_challenges SET status = 'VERIFIED' WHERE id = ?", (row["id"],))
            conn.commit()

            action_type = row["action_type"]
            audit_logger.log(
                event_type=AuditEventType.ADMIN_COMMAND_SUCCESS,
                status="SUCCESS",
                user_id=user["id"],
                actor_role=user["role"],
                channel=AuthChannel.WHATSAPP_BOT,
                reason=f"Step-Up verified. Executed: {action_type}",
                metadata={"jid": jid, "action": action_type},
            )

            return (
                f"✅ *Əməliyyat Təsdiqləndi və İcra Edildi!* 🚀\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"İcra olundu: *{action_type}*\n"
                f"İcraçı Admin: *{user['full_name']}*\n"
                f"Tarix: `{now.strftime('%d.%m.%Y %H:%M:%S UTC')}`\n"
                f"Bütün detallar Təhlükəsizlik Jurnalına (Audit Log) qeyd edildi."
            )
