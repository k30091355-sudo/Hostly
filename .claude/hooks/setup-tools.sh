#!/usr/bin/env bash
# Installiert beim Sitzungsstart den archify-Skill, falls er fehlt.
# caveman wird über .claude/settings.json (enabledPlugins) geladen.
set -u
if [ ! -d "$HOME/.claude/skills/archify" ] && command -v npx >/dev/null 2>&1; then
  DO_NOT_TRACK=1 DISABLE_TELEMETRY=1 timeout 120 \
    npx -y skills@1.9.0 add tt-a1i/archify -g -a claude-code -y --copy >/dev/null 2>&1 || true
fi
exit 0
