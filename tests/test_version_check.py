import json
import time

from fabric_skills_settings.core import version_check


def test_update_notice_reports_newer_cached_version(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    cache_path = tmp_path / version_check.PACKAGE_NAME / "version-check.json"
    cache_path.parent.mkdir(parents=True)
    cache_path.write_text(
        json.dumps({"checked_at": time.time(), "latest": "1.2.0"}),
        encoding="utf-8",
    )

    notice = version_check.update_notice("1.1.0")

    assert notice is not None
    assert "fabric-skills-settings 1.2.0 is available" in notice
    assert "uv tool upgrade fabric-skills-settings" in notice


def test_update_notice_suppressed_when_disabled(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    monkeypatch.setenv(version_check.DISABLE_ENV, "1")

    assert version_check.update_notice("1.1.0") is None


def test_check_latest_version_uses_cache_without_network(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    cache_path = tmp_path / version_check.PACKAGE_NAME / "version-check.json"
    cache_path.parent.mkdir(parents=True)
    cache_path.write_text(
        json.dumps({"checked_at": time.time(), "latest": "1.1.0"}),
        encoding="utf-8",
    )

    def fail_fetch():
        raise AssertionError("network should not be called for fresh cache")

    monkeypatch.setattr(version_check, "_fetch_latest_version", fail_fetch)

    result = version_check.check_latest_version("1.0.0")

    assert result is not None
    assert result.latest == "1.1.0"
    assert result.update_available is True


def test_check_latest_version_returns_current_when_not_newer(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    monkeypatch.setattr(version_check, "_fetch_latest_version", lambda: "1.0.0")

    result = version_check.check_latest_version("1.0.0")

    assert result is not None
    assert result.update_available is False


def test_unknown_current_version_skips_check(monkeypatch):
    def fail_fetch():
        raise AssertionError("unknown version should skip network")

    monkeypatch.setattr(version_check, "_fetch_latest_version", fail_fetch)

    assert version_check.check_latest_version("0+unknown") is None
