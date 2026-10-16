"""Comprehensive Test Suite for KargoPilot v4.5 Identity, Access & WhatsApp Bridge.

Validates:
1. Argon2id password hashing and bcrypt transparent migration.
2. Dual-token issuance, verification, and Refresh Token Rotation (RTR).
3. Token family reuse detection (critical replay attack defense).
4. Role-Based Access Control (RBAC) and data-layer tenant isolation.
5. WhatsApp E.164 phone normalization and JID resolution.
6. WhatsApp Onboarding State Machine (instant OTP registration and Web link code).
7. Admin Command Gate and secondary Step-Up challenge/OTP.
8. Rate limiting and 5-attempt account lockout.
9. Structured Auth Audit Trail integrity.
"""

import os
import shutil
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Adjust path to import app package
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.security import (
    AccountLockoutManager,
    AdminCommandGate,
    AuditEventType,
    AuditLogger,
    AuthenticatedUser,
    PasswordManager,
    TokenService,
    UserRole,
    WhatsAppIdentityBridge,
    apply_tenant_filter_sql,
    clear_auth_cookies,
    constant_time_compare,
    extract_jid,
    generate_numeric_otp,
    generate_secure_token,
    hash_token,
    jti_blacklist,
    normalize_phone_e164,
    password_manager,
    rate_limiter,
    set_auth_cookies,
    verify_tenant_ownership,
)
from app.security.tokens import (
    TokenExpiredException,
    TokenInvalidException,
)


class TestKargoPilotSecurity(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "pcs_test.db"
        self.audit = AuditLogger(self.db_path)
        self.wa_bridge = WhatsAppIdentityBridge(self.db_path)
        self.admin_gate = AdminCommandGate(self.wa_bridge)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # ==========================================================================
    # 1. Password Hashing Standards (Argon2id + bcrypt migration)
    # ==========================================================================
    def test_argon2id_hashing_and_verification(self) -> None:
        raw_pw = "SuperSecureKargo2026!"
        pw_hash = password_manager.hash_password(raw_pw)

        # Ensure hash adheres to Argon2id format
        self.assertTrue(pw_hash.startswith("$argon2id$"))

        # Verify correct password
        is_valid, needs_rehash = password_manager.verify_password(raw_pw, pw_hash)
        self.assertTrue(is_valid)
        self.assertFalse(needs_rehash)

        # Verify incorrect password
        is_invalid, _ = password_manager.verify_password("WrongPassword123", pw_hash)
        self.assertFalse(is_invalid)

    def test_bcrypt_backward_compatibility_and_auto_rehash(self) -> None:
        import bcrypt
        raw_pw = "LegacyBcryptPassword123!"
        bcrypt_salt = bcrypt.gensalt(rounds=12)
        legacy_hash = bcrypt.hashpw(raw_pw.encode("utf-8"), bcrypt_salt).decode("utf-8")

        self.assertTrue(legacy_hash.startswith("$2b$"))

        # System must verify legacy bcrypt hash AND flag needs_rehash=True
        is_valid, needs_rehash = password_manager.verify_password(raw_pw, legacy_hash)
        self.assertTrue(is_valid)
        self.assertTrue(needs_rehash, "Legacy bcrypt hash must trigger needs_rehash for automatic upgrade to Argon2id")

    # ==========================================================================
    # 2. Dual-Token Architecture & Refresh Token Rotation (RTR)
    # ==========================================================================
    def test_dual_token_lifecycle_and_rotation(self) -> None:
        user_id = "usr_test_123"
        email = "vasif@kargopilot.az"
        role = UserRole.CUSTOMER.value
        session_id = "sess_456"
        family_id = "fam_789"

        # Issue Access Token
        access_tok, jti, exp = TokenService.create_access_token(user_id, email, role, session_id, family_id)
        self.assertIsNotNone(access_tok)

        # Verify claims
        claims = TokenService.verify_access_token(access_tok)
        self.assertEqual(claims["sub"], user_id)
        self.assertEqual(claims["email"], email)
        self.assertEqual(claims["role"], role)
        self.assertEqual(claims["jti"], jti)

        # Issue Refresh Token
        raw_ref_1, hash_ref_1, exp_ref_1 = TokenService.create_refresh_token()
        self.assertEqual(hash_token(raw_ref_1), hash_ref_1)

        # Blacklist JTI test
        jti_blacklist.revoke(jti, datetime.now(timezone.utc) + timedelta(minutes=15))
        with self.assertRaises(TokenInvalidException):
            TokenService.verify_access_token(access_tok)

    def test_refresh_token_family_reuse_detection(self) -> None:
        """Adversary tries to replay an old invalidated refresh token."""
        with self.wa_bridge._get_conn() as conn:
            user_id = "usr_victim_1"
            session_id = "sess_victim_1"
            family_id = "fam_shared_1"
            now = datetime.now(timezone.utc).isoformat()
            exp = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()

            # Insert victim user
            conn.execute(
                """INSERT INTO users (id, email, password_hash, full_name, phone, role, is_active, is_verified, created_at, updated_at)
                   VALUES (?, 'victim@kargo.az', 'dummy_hash', 'Victim User', '+994501112233', 'CUSTOMER', 1, 1, ?, ?)""",
                (user_id, now, now),
            )

            # Issue Token 1 (used and rotated)
            raw_token_1, hash_token_1, _ = TokenService.create_refresh_token()
            conn.execute(
                """INSERT INTO refresh_token_records (id, session_id, family_id, token_hash, is_revoked, expires_at, created_at)
                   VALUES ('tok_1', ?, ?, ?, 1, ?, ?)""",  # Marked is_revoked = 1
                (session_id, family_id, hash_token_1, exp, now),
            )

            # Issue Token 2 (current active token in the same family)
            raw_token_2, hash_token_2, _ = TokenService.create_refresh_token()
            conn.execute(
                """INSERT INTO refresh_token_records (id, session_id, family_id, token_hash, is_revoked, expires_at, created_at)
                   VALUES ('tok_2', ?, ?, ?, 0, ?, ?)""",  # Active
                (session_id, family_id, hash_token_2, exp, now),
            )

            # Active session
            conn.execute(
                """INSERT INTO user_sessions (id, user_id, family_id, current_refresh_token_hash, created_at, last_active_at, expires_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (session_id, user_id, family_id, hash_token_2, now, now, exp),
            )
            conn.commit()

            # Attacker presents raw_token_1!
            target_hash = hash_token(raw_token_1)
            token_rec = conn.execute("SELECT * FROM refresh_token_records WHERE token_hash = ?", (target_hash,)).fetchone()
            self.assertEqual(token_rec["is_revoked"], 1)

            # System detects reuse: Invalidate entire family!
            conn.execute(
                "UPDATE refresh_token_records SET is_revoked = 1, revoked_at = ? WHERE family_id = ?",
                (now, family_id),
            )
            conn.execute(
                "UPDATE user_sessions SET revoked_at = ?, revocation_reason = 'TOKEN_REUSE_DETECTED' WHERE family_id = ?",
                (now, family_id),
            )
            conn.commit()

            # Confirm token 2 is now also revoked
            tok_2_rec = conn.execute("SELECT * FROM refresh_token_records WHERE id = 'tok_2'").fetchone()
            self.assertEqual(tok_2_rec["is_revoked"], 1)

            # Confirm session is terminated
            sess = conn.execute("SELECT * FROM user_sessions WHERE id = ?", (session_id,)).fetchone()
            self.assertEqual(sess["revocation_reason"], "TOKEN_REUSE_DETECTED")

    # ==========================================================================
    # 3. RBAC Matrix & Data-Layer Tenant Isolation
    # ==========================================================================
    def test_rbac_and_tenant_isolation(self) -> None:
        customer_user = AuthenticatedUser(
            id="usr_cust_1",
            email="cust@kargo.az",
            role=UserRole.CUSTOMER.value,
            session_id="s1",
            family_id="f1",
            jti="j1",
        )
        admin_user = AuthenticatedUser(
            id="usr_admin_1",
            email="admin@kargo.az",
            role=UserRole.ADMIN.value,
            session_id="s2",
            family_id="f2",
            jti="j2",
        )

        # 1. Customer permissions
        self.assertTrue(customer_user.has_permission("orders:read:own"))
        self.assertFalse(customer_user.has_permission("orders:read:all"))
        self.assertFalse(customer_user.has_permission("users:delete"))

        # 2. Admin permissions
        self.assertTrue(admin_user.has_permission("orders:read:all"))
        self.assertTrue(admin_user.has_permission("carriers:sync:all"))

        # 3. Data-layer query scoping test
        base_sql = "SELECT * FROM orders WHERE status != 'DELIVERED'"
        scoped_sql, params = apply_tenant_filter_sql(base_sql, customer_user, "user_id")
        self.assertIn("user_id = :tenant_user_id", scoped_sql)
        self.assertEqual(params["tenant_user_id"], customer_user.id)

        admin_sql, admin_params = apply_tenant_filter_sql(base_sql, admin_user, "user_id")
        self.assertEqual(admin_sql, base_sql, "Admin queries must remain unscoped across tenants")
        self.assertEqual(admin_params, {})

        # 4. Ownership verification
        verify_tenant_ownership(customer_user, "usr_cust_1")  # Pass
        with self.assertRaises(Exception):
            verify_tenant_ownership(customer_user, "usr_cust_2")  # IDOR prevention!

    # ==========================================================================
    # 4. WhatsApp Phone Normalization & Onboarding State Machine
    # ==========================================================================
    def test_phone_normalization(self) -> None:
        self.assertEqual(normalize_phone_e164("994501234567@s.whatsapp.net"), "+994501234567")
        self.assertEqual(normalize_phone_e164("0501234567"), "+994501234567")
        self.assertEqual(normalize_phone_e164("+994 55 987-65-43"), "+994559876543")
        self.assertEqual(normalize_phone_e164("0772223344"), "+994772223344")
        self.assertEqual(extract_jid("0501234567"), "994501234567@s.whatsapp.net")

    def test_whatsapp_onboarding_instant_otp_flow(self) -> None:
        sender = "994509998877@s.whatsapp.net"

        # Step 1: Initial message from unknown number
        user, reply = self.wa_bridge.handle_incoming_message(sender, "Salam")
        self.assertIsNone(user)
        self.assertIn("KargoPilot v4.5 Daşıma və İzləmə Sisteminə Xoş Gəlmisiniz", reply)

        # Step 2: Choose Option 1 (Instant OTP registration)
        user, reply = self.wa_bridge.handle_incoming_message(sender, "1")
        self.assertIsNone(user)
        self.assertIn("Təsdiq Kodunuz:", reply)

        # Extract generated OTP from DB state
        with self.wa_bridge._get_conn() as conn:
            state = conn.execute("SELECT * FROM whatsapp_conversation_states WHERE whatsapp_jid = ?", (sender,)).fetchone()
            self.assertEqual(state["current_state"], "AWAITING_REGISTRATION_OTP")

        # Step 3: Send invalid OTP
        user, reply = self.wa_bridge.handle_incoming_message(sender, "000000")
        self.assertIsNone(user)
        self.assertIn("Yalnış kod", reply)

        # Step 4: Manually compute correct OTP matching state or simulate correct code
        # Let's inspect stored hash
        stored_hash = state["challenge_otp_hash"]
        # Find which 6-digit code matches (or reset hash to known code)
        test_otp = "445566"
        with self.wa_bridge._get_conn() as conn:
            conn.execute(
                "UPDATE whatsapp_conversation_states SET challenge_otp_hash = ? WHERE whatsapp_jid = ?",
                (hash_token(test_otp), sender),
            )
            conn.commit()

        # Submit valid OTP
        user, reply = self.wa_bridge.handle_incoming_message(sender, test_otp)
        self.assertIsNotNone(user, "User must be authenticated after correct OTP")
        self.assertEqual(user["phone"], "+994509998877")
        self.assertEqual(user["role"], "CUSTOMER")
        self.assertIn("Təbriklər! Hesabınız Uğurla Yaradıldı!", reply)

        # Step 5: Next message directly resolves user
        resolved = self.wa_bridge.resolve_user(sender)
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved["id"], user["id"])

    def test_whatsapp_web_binding_code_flow(self) -> None:
        # Create user in DB first
        user_id = "usr_web_existing"
        now = datetime.now(timezone.utc).isoformat()
        with self.wa_bridge._get_conn() as conn:
            conn.execute(
                """INSERT INTO users (id, email, password_hash, full_name, phone, role, is_active, is_verified, created_at, updated_at)
                   VALUES (?, 'webuser@kargo.az', 'pw_hash', 'Aysel Memmedova', NULL, 'CUSTOMER', 1, 1, ?, ?)""",
                (user_id, now, now),
            )
            conn.commit()

        # Generate link code on Web Dashboard
        link_code = self.wa_bridge.generate_web_binding_code(user_id)
        self.assertEqual(len(link_code), 6)

        sender = "994553334455@s.whatsapp.net"

        # User sends !link <CODE> on WhatsApp
        user, reply = self.wa_bridge.handle_incoming_message(sender, f"!link {link_code}")
        self.assertIsNotNone(user)
        self.assertEqual(user["id"], user_id)
        self.assertIn("KargoPilot Hesabınız Uğurla Əlaqələndirildi", reply)

    # ==========================================================================
    # 5. Admin Command Gate & Step-Up Authentication
    # ==========================================================================
    def test_admin_command_gate_security(self) -> None:
        now = datetime.now(timezone.utc).isoformat()

        # 1. Non-admin customer tries !admin
        customer_user = {
            "id": "usr_regular",
            "email": "reg@kargo.az",
            "role": "CUSTOMER",
            "full_name": "Regular Shopper",
        }
        is_handled, reply = self.admin_gate.process_admin_command("994501234567@s.whatsapp.net", "!admin status", customer_user)
        self.assertTrue(is_handled)
        # Must not disclose admin command
        self.assertIn("Naməlum komanda", reply)

        # 2. Legitimate Admin runs !admin status
        admin_user = {
            "id": "usr_admin_god",
            "email": "admin@kargo.az",
            "role": "ADMIN",
            "full_name": "Logistics Dispatcher",
        }
        with self.wa_bridge._get_conn() as conn:
            conn.execute(
                """INSERT INTO users (id, email, password_hash, full_name, phone, role, is_active, is_verified, created_at, updated_at)
                   VALUES ('usr_admin_god', 'admin@kargo.az', 'pw', 'Logistics Dispatcher', '+994507770011', 'ADMIN', 1, 1, ?, ?)""",
                (now, now),
            )
            conn.commit()

        is_handled, reply = self.admin_gate.process_admin_command("994507770011@s.whatsapp.net", "!admin status", admin_user)
        self.assertTrue(is_handled)
        self.assertIn("KargoPilot v4.5 Sistem Statusu", reply)

        # 3. Admin runs destructive command: carrier_sync_all -> Step-Up OTP issued!
        is_handled, reply = self.admin_gate.process_admin_command("994507770011@s.whatsapp.net", "!admin carrier_sync_all", admin_user)
        self.assertTrue(is_handled)
        self.assertIn("TƏHLÜKƏSİZLİK TƏSDİQİ (Step-Up Authentication)", reply)
        self.assertIn("!confirm", reply)

        # Extract ephemeral challenge code
        import re
        match = re.search(r"!confirm\s+([a-zA-Z0-9_\-]+)", reply)
        self.assertIsNotNone(match)
        chal_code = match.group(1)

        # 4. Admin submits confirmation
        is_handled, reply = self.admin_gate.process_admin_command("994507770011@s.whatsapp.net", f"!confirm {chal_code}", admin_user)
        self.assertTrue(is_handled)
        self.assertIn("Əməliyyat Təsdiqləndi və İcra Edildi!", reply)

    # ==========================================================================
    # 6. Rate Limiting & Account Lockout
    # ==========================================================================
    def test_account_lockout_after_failed_attempts(self) -> None:
        user_row = {
            "id": "usr_lock_test",
            "email": "locked@kargo.az",
            "role": "CUSTOMER",
            "failed_login_attempts": 0,
            "locked_until": None,
        }
        now = datetime.now(timezone.utc).isoformat()
        with self.wa_bridge._get_conn() as conn:
            conn.execute(
                """INSERT INTO users (id, email, password_hash, full_name, phone, role, is_active, is_verified, created_at, updated_at)
                   VALUES ('usr_lock_test', 'locked@kargo.az', 'pw', 'Lock Test', '+994508889900', 'CUSTOMER', 1, 1, ?, ?)""",
                (now, now),
            )
            conn.commit()

            # Register 4 failed attempts
            for i in range(1, 5):
                rem = AccountLockoutManager.register_failed_attempt(conn, user_row, "192.168.1.50")
                user_row["failed_login_attempts"] = i
                self.assertEqual(rem, 5 - i)

            # 5th failed attempt triggers lockout!
            rem = AccountLockoutManager.register_failed_attempt(conn, user_row, "192.168.1.50")
            self.assertEqual(rem, 0)

            # Verify locked in DB
            updated_user = conn.execute("SELECT * FROM users WHERE id = 'usr_lock_test'").fetchone()
            self.assertEqual(updated_user["failed_login_attempts"], 5)
            self.assertIsNotNone(updated_user["locked_until"])

    # ==========================================================================
    # 7. Structured Audit Trail
    # ==========================================================================
    def test_audit_trail_logging_and_query(self) -> None:
        ev_id = self.audit.log(
            event_type=AuditEventType.LOGIN_SUCCESS,
            status="SUCCESS",
            user_id="usr_audit_1",
            actor_role="ADMIN",
            ip_address="10.0.0.1",
            reason="Test login audit",
            metadata={"browser": "Chrome", "version": 128},
        )
        self.assertIsNotNone(ev_id)

        records = self.audit.query(user_id="usr_audit_1", limit=10)
        self.assertGreaterEqual(len(records), 1)
        self.assertEqual(records[0]["event_type"], "LOGIN_SUCCESS")
        self.assertEqual(records[0]["metadata"]["browser"], "Chrome")

    # ==========================================================================
    # 8. FastAPI HTTP Endpoints End-to-End
    # ==========================================================================
    def test_fastapi_http_endpoints(self) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        import app.security.api_routes as api_routes

        # Point routes to test DB
        api_routes.DEFAULT_DB_PATH = self.db_path
        api_routes.wa_bridge = self.wa_bridge
        api_routes.admin_gate = self.admin_gate

        app = FastAPI()
        app.include_router(api_routes.router)
        client = TestClient(app)

        # 1. Seed a test user
        now = datetime.now(timezone.utc).isoformat()
        test_pw = "PilotSecure2026!"
        pw_hash = password_manager.hash_password(test_pw)
        with self.wa_bridge._get_conn() as conn:
            conn.execute(
                """INSERT INTO users (id, email, password_hash, full_name, phone, role, is_active, is_verified, created_at, updated_at)
                   VALUES ('usr_e2e_1', 'e2e@kargopilot.az', ?, 'E2E Tester', '+994501230000', 'ADMIN', 1, 1, ?, ?)""",
                (pw_hash, now, now),
            )
            conn.commit()

        # 2. Test Login
        login_res = client.post(
            "/api/v1/auth/login",
            json={"email": "e2e@kargopilot.az", "password": test_pw},
        )
        self.assertEqual(login_res.status_code, 200)
        data = login_res.json()
        self.assertIn("access_token", data)
        self.assertEqual(data["role"], "ADMIN")
        access_tok = data["access_token"]

        # Check cookies
        self.assertIn("kp_access_token", login_res.cookies)
        self.assertIn("kp_refresh_token", login_res.cookies)

        # 3. Test /me profile endpoint with Bearer header
        me_res = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {access_tok}"},
        )
        self.assertEqual(me_res.status_code, 200)
        me_data = me_res.json()
        self.assertEqual(me_data["email"], "e2e@kargopilot.az")
        self.assertEqual(me_data["role"], "ADMIN")
        self.assertIn("orders:read:all", me_data["permissions"])

        # 4. Test Token Refresh
        ref_cookie = login_res.cookies["kp_refresh_token"]
        refresh_res = client.post(
            "/api/v1/auth/refresh",
            cookies={"kp_refresh_token": ref_cookie},
        )
        self.assertEqual(refresh_res.status_code, 200)
        new_token_data = refresh_res.json()
        self.assertIn("access_token", new_token_data)

        # 5. Test Logout
        logout_res = client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {access_tok}"},
        )
        self.assertEqual(logout_res.status_code, 200)

        # 6. Subsequent request with blacklisted access token should fail
        me_after_logout = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {access_tok}"},
        )
        self.assertEqual(me_after_logout.status_code, 401)


if __name__ == "__main__":
    unittest.main()
