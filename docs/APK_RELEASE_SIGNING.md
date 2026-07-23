# ATW APK Release-Signing — Setup-Anleitung (Daniel-HIL)

**Owner:** Daniel (Keystore-Ownership) | **Erstellt:** 2026-07-23 (ICT, Notion 3a65154b-eb42-812e)

## Warum das nötig ist

Google-Play-Console lehnt debug-signed APKs ab. Für Production-Release brauchen wir einen
selbst-generierten Release-Keystore (JKS oder PKCS12). Dieser Keystore ist **einmalig zu
generieren** und muss danach **für die gesamte App-Lebenszeit sicher aufbewahrt werden** —
sonst können wir keine Updates mehr signieren (verlorener Keystore = App muss neu unter
neuer Applikations-ID veröffentlicht werden).

## Schritt 1 — Keystore generieren (Daniel-Action, einmalig)

```bash
keytool -genkeypair \
  -alias atw-release \
  -keyalg RSA -keysize 4096 \
  -validity 25000 \
  -keystore ~/atw-release.jks \
  -storetype JKS
```

Der Prompt fragt nach:
- **Keystore-Passwort** (min 6 Zeichen — Daniel wählt starkes Passwort, in Password-Manager speichern)
- **Key-Passwort** (kann dasselbe sein — bei "Same as keystore password?" → yes)
- CN/OU/O/L/ST/C (Vorname Nachname / IT / Bratschke Solutions GmbH / Bochum / NRW / DE)

## Schritt 2 — ENV setzen (in `~/.bashrc` oder secrets-manager)

```bash
export ATW_KEYSTORE_PATH="/home/daniel/atw-release.jks"
export ATW_KEYSTORE_PASSWORD="<KEYSTORE-PW>"
export ATW_KEY_ALIAS="atw-release"
export ATW_KEY_PASSWORD="<KEY-PW>"
```

**WICHTIG:** Keystore-File NIEMALS in Git committen. `.gitignore` enthält `*.jks` und `*.keystore`.

## Schritt 3 — Release-Build starten

```bash
cd /home/claude/projects/AgentTerminalsWatch/android
./gradlew clean assembleRelease
```

APK landet in: `android/app/build/outputs/apk/release/app-release.apk`

## Schritt 4 — Google-Play-Console-Upload

1. https://play.google.com/console → App auswählen (oder neu erstellen: "AgentTerminalsWatch")
2. Release → Production → Neuen Release erstellen
3. `app-release.apk` hochladen
4. Release-Notes ausfüllen
5. Rollout stufenweise (10% → 50% → 100%)

## Backup-Regel

Nach Keystore-Erzeugung SOFORT sichern:
- **Location 1:** verschlüsselter Cloud-Speicher (rclone → Backblaze o.ä.)
- **Location 2:** offline (USB-Stick im Safe)
- **Passwort:** Password-Manager mit 2FA

Ohne diesen Keystore ist die App-Identität verloren.

## R145-Verify

Dieser Setup wird von `tests/test_android_release_signing.py` getestet:
- build.gradle hat signingConfigs-Block
- release-buildType referenziert signingConfig
- Keystore-Path kommt aus ENV (nicht hardcoded)
- Diese Doku existiert und erwähnt keytool + ATW_KEYSTORE_PASSWORD + ATW_KEY_ALIAS
