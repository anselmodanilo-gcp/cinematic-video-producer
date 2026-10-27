#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DEST="${HOME}/.gemini/config/skills/cinematic-video-producer"
AGENT_DEST="${HOME}/.gemini/config/agents"

mkdir -p "${SKILL_DEST}/references" "${SKILL_DEST}/scripts" "${AGENT_DEST}"

if [ "${SCRIPT_DIR}" != "${SKILL_DEST}" ]; then
  cp "${SCRIPT_DIR}/SKILL.md" "${SKILL_DEST}/SKILL.md"
  cp -R "${SCRIPT_DIR}/references/"* "${SKILL_DEST}/references/"
  cp -R "${SCRIPT_DIR}/scripts/"* "${SKILL_DEST}/scripts/"
fi

cp "${SCRIPT_DIR}/agents/video-producer.md" "${AGENT_DEST}/video-producer.md"

echo "Skill 'cinematic-video-producer' e subagente 'video-producer' instalados com sucesso em ~/.gemini/config/"
