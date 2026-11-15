#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
JSON_JAR="${ANDROID_JSON_JAR:-/usr/share/java/com.android.json.jar}"
[[ -f "$JSON_JAR" ]] || { echo 'Set ANDROID_JSON_JAR or install libandroid-json-java.' >&2; exit 1; }
mkdir -p build/test-classes
javac -cp "$JSON_JAR" -d build/test-classes test/OutboxTest.java src/com/spockymagicai/agentterminals/{RequestPolicy,Outbox}.java
java -cp "build/test-classes:$JSON_JAR" OutboxTest
javac -d build/test-classes test/NotificationPolicyTest.java src/com/spockymagicai/agentterminals/NotificationPolicy.java
java -cp build/test-classes NotificationPolicyTest
