"""R145 TDD — ATW Android Release-Signing-Konfiguration (Notion 3a65154b-eb42-812e).

Prüft strukturell dass build.gradle Release-Signing-Slot hat, der ENV-Vars liest.
Keystore selbst wird von Daniel gesetzt (HIL, siehe docs/APK_RELEASE_SIGNING.md).
Ohne diese Struktur produziert `./gradlew assembleRelease` debug-signed APK
die Google-Play ablehnt.
"""
from __future__ import annotations

from pathlib import Path

BUILD_GRADLE = Path(__file__).resolve().parent.parent / "android" / "app" / "build.gradle"
DOCS = Path(__file__).resolve().parent.parent / "docs" / "APK_RELEASE_SIGNING.md"


def _read_gradle():
    return BUILD_GRADLE.read_text()


def test_build_gradle_exists():
    assert BUILD_GRADLE.exists()


def test_signing_config_block_present():
    """build.gradle must declare a signingConfigs block."""
    gradle = _read_gradle()
    assert "signingConfigs" in gradle, (
        "Release-Signing kann nicht funktionieren ohne signingConfigs-Block"
    )


def test_release_block_references_signing_config():
    """The release buildType (inside buildTypes) must reference a signingConfig."""
    gradle = _read_gradle()
    import re
    # Match buildTypes { ... release { ... } ... } specifically
    m = re.search(
        r"buildTypes\s*\{.*?release\s*\{(.*?)\n\s*\}",
        gradle, re.DOTALL,
    )
    assert m, "no buildTypes.release block found"
    release_body = m.group(1)
    assert "signingConfig" in release_body, (
        "buildTypes.release referenziert keinen signingConfig → APK wird debug-signed → "
        "Google-Play-Console lehnt ab"
    )


def test_signing_config_reads_env_vars():
    """Keystore-Path + Passwords müssen aus ENV kommen (nicht hardcoded)."""
    gradle = _read_gradle()
    # Expect at least one System.getenv or project.property reference
    assert (
        "System.getenv" in gradle or "project.property" in gradle or "findProperty" in gradle
    ), (
        "signing-config muss ENV oder gradle-properties lesen (nicht hardcoded), "
        "damit .env/CI-Secrets funktioniert"
    )


def test_release_signing_doc_exists():
    """Daniel muss wissen wie er den Keystore erzeugt."""
    assert DOCS.exists(), (
        f"Doku fehlt: {DOCS}. Ohne Anleitung kann Daniel den Keystore nicht erzeugen."
    )
    body = DOCS.read_text()
    for expected in ["keytool", "keystore", "ATW_KEYSTORE_PASSWORD", "ATW_KEY_ALIAS"]:
        assert expected in body, f"Doku muss '{expected}' erwähnen"
