# AgentTerminalsWatch

Android app (Capacitor + Vite/React) — zeigt den Status aller SpockyMagicAI-Agenten in Echtzeit.

**App-ID:** `com.spocky.agentterminals` | **Version:** 0.1.0

## Architektur

```
src/          React-Frontend (Vite)
dist/         Build-Output → Capacitor webDir
android/      Capacitor-Android-Projekt (Gradle)
agent_status_api.py   Backend-API (FastAPI, Port 8765)
stripe_webhook.py     Stripe-Webhook für App-Käufe
tests/        pytest-Suite (99 Tests)
```

## Lokale Entwicklung

```bash
npm install
npm run dev          # Vite Dev-Server
```

## Android-Build (Debug)

```bash
npm run build        # dist/ erstellen
npx cap sync android # Sync in android/
cd android && ./gradlew assembleDebug
adb install app/build/outputs/apk/debug/app-debug.apk
```

## Android-Release-Build (Play Store)

Voraussetzung: Keystore muss von Daniel generiert worden sein (docs/APK_RELEASE_SIGNING.md).

```bash
export ATW_KEYSTORE_PATH="/pfad/zu/atw-release.jks"
export ATW_KEYSTORE_PASSWORD="..."
export ATW_KEY_ALIAS="atw-release"
export ATW_KEY_PASSWORD="..."

npm run build
npx cap sync android
cd android && ./gradlew bundleRelease
# → android/app/build/outputs/bundle/release/app-release.aab
```

## Tests

```bash
python3 -m pytest tests/ -q   # 99 Tests
```

## Play Store Deployment

Siehe `docs/APK_RELEASE_SIGNING.md` und GH#1753 für den vollständigen Deployment-Plan.
