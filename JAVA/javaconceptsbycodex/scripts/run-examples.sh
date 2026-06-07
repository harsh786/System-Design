#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
rm -rf out
javac -d out $(find src/main/java -name "*.java")
java -cp out com.codex.javaconcepts.AllExamplesRunner

