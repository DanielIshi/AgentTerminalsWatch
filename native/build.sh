#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
SDK="${ANDROID_HOME:-/home/claude/.android/sdk}"
TOOLS="$SDK/build-tools/35.0.0"
ANDROID_JAR="$SDK/platforms/android-36/android.jar"
mkdir -p build/classes build/dex
"$TOOLS/aapt2" compile --dir res -o build/resources.zip
"$TOOLS/aapt2" link -o build/resources.ap_ --manifest AndroidManifest.xml -I "$ANDROID_JAR" build/resources.zip
find src -name '*.java' > build/sources.txt
javac -source 8 -target 8 -Xlint:-options -classpath "$ANDROID_JAR" -d build/classes @build/sources.txt
jar cf build/classes.jar -C build/classes .
"$TOOLS/d8" --min-api 26 --lib "$ANDROID_JAR" --output build/dex build/classes.jar
cp build/resources.ap_ build/unsigned.apk
python3 - <<'ZIP'
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
with ZipFile('build/unsigned.apk','a',compression=ZIP_DEFLATED) as apk:
    for dex in Path('build/dex').glob('*.dex'):
        apk.write(dex,dex.name)
ZIP
"$TOOLS/zipalign" -f 4 build/unsigned.apk build/aligned.apk
# Signing material is external; never generate a new key for an existing installation.
KEYSTORE="${WATCH_KEYSTORE:-$HOME/.android/debug.keystore}"
ALIAS="${WATCH_KEY_ALIAS:-androiddebugkey}"
export WATCH_SIGN_STORE_PASS="${WATCH_SIGN_STORE_PASS:-android}"
export WATCH_SIGN_KEY_PASS="${WATCH_SIGN_KEY_PASS:-android}"
"$TOOLS/apksigner" sign --ks "$KEYSTORE" --ks-key-alias "$ALIAS" --ks-pass env:WATCH_SIGN_STORE_PASS --key-pass env:WATCH_SIGN_KEY_PASS --out build/agent-terminals-ceo-preview.apk build/aligned.apk
"$TOOLS/apksigner" verify --print-certs build/agent-terminals-ceo-preview.apk
# Compare with the real existing APK before calling this artifact an update.
OLD_CERT=05a676fcc3b750ca7e8b57955394a2b9e8c7665249918277e4b836816b91de12
NEW_CERT=$("$TOOLS/apksigner" verify --print-certs build/agent-terminals-ceo-preview.apk | sed -n 's/Signer #1 certificate SHA-256 digest: //p')
if [[ "$NEW_CERT" != "$OLD_CERT" ]]; then
  echo 'PREVIEW ONLY: signer differs from the preserved 2026-05-31 APK. Do not uninstall or replace the existing app.'
else
  cp build/agent-terminals-ceo-preview.apk build/agent-terminals-ceo-update.apk
  echo 'Update certificate matches preserved APK.'
fi
sha256sum build/agent-terminals-ceo-preview.apk
