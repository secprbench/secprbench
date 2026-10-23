import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from secprbench.judge.auth import isolated_auth_environment


class JudgeAuthTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.modern = self.home / ".config/anthropic/credentials/default.json"
        self.modern.parent.mkdir(parents=True)
        self.modern.write_text(json.dumps({"type": "oauth_token", "access_token": "TEST-MODERN"}))
        profile = self.home / ".config/anthropic/configs/default.json"
        profile.parent.mkdir()
        profile.write_text(
            json.dumps(
                {
                    "version": "1.0",
                    "authentication": {
                        "type": "user_oauth",
                        "client_id": "TEST-CLIENT",
                        "ignored": "do not copy",
                    },
                    "hooks": "do not copy",
                }
            )
        )
        self.legacy = self.home / ".caw/auth/claude/credentials.json"
        self.legacy.parent.mkdir(parents=True)
        self.legacy.write_text(json.dumps({"claudeAiOauth": {"accessToken": "TEST-LEGACY"}}))

    def prepare(self, env=None):
        with patch("secprbench.judge.auth.Path.home", return_value=self.home):
            return isolated_auth_environment(env or {}, self.root / "isolated")

    def test_modern_precedes_expired_legacy_and_profile_is_whitelisted(self):
        env = self.prepare()
        modern = Path(env["ANTHROPIC_CONFIG_DIR"])
        copied = modern / "credentials/default.json"
        self.assertEqual(copied.read_bytes(), self.modern.read_bytes())
        self.assertEqual(copied.stat().st_mode & 0o777, 0o600)
        self.assertFalse((Path(env["CLAUDE_CONFIG_DIR"]) / ".credentials.json").exists())
        self.assertEqual((modern / "active_config").read_text(), "default\n")
        profile = json.loads((modern / "configs/default.json").read_text())
        self.assertEqual(
            profile, {"version": "1.0", "authentication": {"type": "user_oauth", "client_id": "TEST-CLIENT"}}
        )

    def test_explicit_legacy_override_prevents_ambient_modern_fallback(self):
        env = self.prepare({"SECPRBENCH_JUDGE_AUTH_FILE": str(self.legacy)})
        self.assertEqual(
            (Path(env["CLAUDE_CONFIG_DIR"]) / ".credentials.json").read_bytes(), self.legacy.read_bytes()
        )
        self.assertFalse((Path(env["ANTHROPIC_CONFIG_DIR"]) / "credentials/default.json").exists())
        self.assertNotEqual(env["ANTHROPIC_CONFIG_DIR"], str(self.modern.parent.parent))
        self.assertTrue(Path(env["XDG_CONFIG_HOME"]).is_dir())
        self.assertNotIn("HOME", env)

    def test_gateway_environment_does_not_copy_unrelated_user_profiles(self):
        env = self.prepare(
            {"ANTHROPIC_AUTH_TOKEN": "TEST-GATEWAY", "ANTHROPIC_BASE_URL": "https://example.invalid"}
        )
        self.assertFalse((Path(env["CLAUDE_CONFIG_DIR"]) / ".credentials.json").exists())
        self.assertFalse((Path(env["ANTHROPIC_CONFIG_DIR"]) / "credentials/default.json").exists())
        self.assertEqual(env["ANTHROPIC_AUTH_TOKEN"], "TEST-GATEWAY")

    def test_legacy_fallback_and_missing_explicit_file(self):
        self.modern.unlink()
        env = self.prepare()
        self.assertEqual(
            (Path(env["CLAUDE_CONFIG_DIR"]) / ".credentials.json").read_bytes(), self.legacy.read_bytes()
        )
        with self.assertRaises(FileNotFoundError):
            self.prepare({"SECPRBENCH_JUDGE_AUTH_FILE": str(self.root / "missing")})

    def test_logged_in_claude_profile_precedes_stale_caw_profile(self):
        self.modern.unlink()
        current = self.home / ".claude/.credentials.json"
        current.parent.mkdir()
        current.write_text(json.dumps({"claudeAiOauth": {"accessToken": "CURRENT"}}))
        (self.home / ".claude.json").write_text(json.dumps({
            "oauthAccount": {"organizationUuid": "CURRENT-ORG"},
            "userID": "CURRENT-USER", "hooks": {"ignored": True}}))
        env = self.prepare()
        classic = Path(env["CLAUDE_CONFIG_DIR"])
        self.assertEqual((classic / ".credentials.json").read_bytes(), current.read_bytes())
        profile = json.loads((classic / ".claude.json").read_text())
        self.assertEqual(profile["oauthAccount"], {"organizationUuid": "CURRENT-ORG"})
        self.assertNotIn("hooks", profile)
