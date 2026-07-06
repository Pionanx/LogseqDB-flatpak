#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_ID="com.logseq.LogseqDB"
APP_BRANCH="master"
REPO_NAME="${FLATPAK_REPO_NAME:-logseq-db}"
REPO_TITLE="${FLATPAK_REPO_TITLE:-Logseq DB Flatpak}"
REPO_COMMENT="${FLATPAK_REPO_COMMENT:-Unofficial Logseq DB nightly Flatpak builds}"
REPO_DESCRIPTION="${FLATPAK_REPO_DESCRIPTION:-Auto-built Flatpak repository for upstream Logseq DB nightly releases.}"
BASE_URL="${FLATPAK_BASE_URL:-}"
REPO_URL="${FLATPAK_REPO_URL:-}"
GPG_KEY_ID="${FLATPAK_GPG_KEY_ID:-}"
GPG_HOMEDIR="${FLATPAK_GPG_HOMEDIR:-${GNUPGHOME:-}}"
GPG_PUBLIC_KEY="${FLATPAK_GPG_PUBLIC_KEY:-}"

find_default_gpg_public_key() {
  local candidate
  for candidate in \
    "$ROOT/flatpak-repo.gpg" \
    "$ROOT/flatpak-repo.asc" \
    "$ROOT/flatpak-repo-public.gpg" \
    "$ROOT/flatpak-repo-public.asc" \
    "$ROOT/public.gpg" \
    "$ROOT/public.asc" \
    "$ROOT/gpg.key" \
    "$ROOT/gpg.asc" \
    "$ROOT/../flatpak-repo.gpg" \
    "$ROOT/../flatpak-repo.asc" \
    "$ROOT/../flatpak-repo-public.gpg" \
    "$ROOT/../flatpak-repo-public.asc" \
    "$ROOT/../public.gpg" \
    "$ROOT/../public.asc" \
    "$ROOT/../gpg.key" \
    "$ROOT/../gpg.asc"; do
    if [[ -f "$candidate" ]]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
}

gpg_homedir_args=()
if [[ -n "$GPG_HOMEDIR" ]]; then
  gpg_homedir_args=(--homedir "$GPG_HOMEDIR")
fi

if [[ -z "$GPG_PUBLIC_KEY" ]]; then
  GPG_PUBLIC_KEY="$(find_default_gpg_public_key || true)"
fi
if [[ -z "$GPG_KEY_ID" && -n "$GPG_PUBLIC_KEY" ]] && command -v gpg >/dev/null 2>&1; then
  GPG_KEY_ID="$(gpg --show-keys --with-colons "$GPG_PUBLIC_KEY" 2>/dev/null | awk -F: '$1 == "fpr" { print $10; exit }')"
  if [[ -n "$GPG_KEY_ID" ]] && ! gpg "${gpg_homedir_args[@]}" --batch --list-secret-keys "$GPG_KEY_ID" >/dev/null 2>&1; then
    GPG_KEY_ID=""
    GPG_PUBLIC_KEY=""
  fi
fi
if [[ -n "$GPG_KEY_ID" && -z "$GPG_PUBLIC_KEY" ]] && command -v gpg >/dev/null 2>&1; then
  GPG_PUBLIC_KEY="$ROOT/build/generated/flatpak-public.gpg"
  mkdir -p "$(dirname "$GPG_PUBLIC_KEY")"
  gpg "${gpg_homedir_args[@]}" --batch --export "$GPG_KEY_ID" > "$GPG_PUBLIC_KEY"
fi

cd "$ROOT"

python3 scripts/prepare-release.py

if command -v desktop-file-validate >/dev/null 2>&1; then
  desktop-file-validate flatpak/com.logseq.LogseqDB.desktop
fi

if command -v appstreamcli >/dev/null 2>&1; then
  appstreamcli validate --no-net build/generated/com.logseq.LogseqDB.metainfo.xml
fi

if command -v flatpak-builder >/dev/null 2>&1; then
  BUILDER=(flatpak-builder)
elif flatpak info --user org.flatpak.Builder >/dev/null 2>&1 || flatpak info org.flatpak.Builder >/dev/null 2>&1; then
  BUILDER=(flatpak run --command=sh org.flatpak.Builder -c)
else
  echo "error: flatpak-builder is not installed." >&2
  echo "Install either the host flatpak-builder package or org.flatpak.Builder from Flathub." >&2
  exit 1
fi

rm -rf .flatpak-build-dir .flatpak-repo

builder_args=(--repo=.flatpak-repo --force-clean --disable-updates --user)
if [[ "${BUILDER[0]}" == "flatpak" ]]; then
  if flatpak run --command=flatpak-builder org.flatpak.Builder --help | grep -q -- "--disable-rofiles-fuse"; then
    builder_args+=(--disable-rofiles-fuse)
  fi
elif "${BUILDER[@]}" --help | grep -q -- "--disable-rofiles-fuse"; then
  builder_args+=(--disable-rofiles-fuse)
fi
if [[ -n "$GPG_KEY_ID" ]]; then
  if [[ "${BUILDER[0]}" == "flatpak" ]]; then
    echo "error: signing requires the host flatpak-builder command, not org.flatpak.Builder." >&2
    exit 1
  fi
  builder_args+=(--gpg-sign="$GPG_KEY_ID")
  if [[ -n "$GPG_HOMEDIR" ]]; then
    builder_args+=(--gpg-homedir="$GPG_HOMEDIR")
  fi
fi
builder_args+=(.flatpak-build-dir com.logseq.LogseqDB.yml)

if [[ "${BUILDER[0]}" == "flatpak" ]]; then
  printf -v builder_command ' %q' "${builder_args[@]}"
  "${BUILDER[@]}" "cd '$ROOT' && XDG_DATA_HOME='${XDG_DATA_HOME:-$HOME/.local/share}' flatpak-builder$builder_command"
else
  "${BUILDER[@]}" "${builder_args[@]}"
fi

mkdir -p dist
# shellcheck disable=SC1091
. build/generated/release.env

update_repo_args=(
  --title="$REPO_TITLE"
  --comment="$REPO_COMMENT"
  --description="$REPO_DESCRIPTION"
  --default-branch="$APP_BRANCH"
  --generate-static-deltas
)
if [[ -n "$BASE_URL" ]]; then
  update_repo_args+=(--homepage="$BASE_URL" --icon="$BASE_URL/logo.svg")
fi
if [[ -n "$GPG_KEY_ID" ]]; then
  update_repo_args+=(--gpg-sign="$GPG_KEY_ID")
  if [[ -n "$GPG_PUBLIC_KEY" ]]; then
    update_repo_args+=(--gpg-import="$GPG_PUBLIC_KEY")
  fi
  if [[ -n "$GPG_HOMEDIR" ]]; then
    update_repo_args+=(--gpg-homedir="$GPG_HOMEDIR")
  fi
fi

flatpak build-update-repo "${update_repo_args[@]}" .flatpak-repo

bundle_args=()
if [[ -n "$REPO_URL" ]]; then
  bundle_args+=(--repo-url="$REPO_URL")
fi
if [[ -n "$GPG_PUBLIC_KEY" ]]; then
  bundle_args+=(--gpg-keys="$GPG_PUBLIC_KEY")
fi

flatpak build-bundle "${bundle_args[@]}" .flatpak-repo "dist/$BUNDLE_NAME" "$APP_ID" "$APP_BRANCH"
(cd dist && sha256sum "$BUNDLE_NAME" > "$BUNDLE_NAME.sha256")

rm -rf dist/pages
pages_args=(
  --repo-dir .flatpak-repo
  --output-dir dist/pages
  --app-id "$APP_ID"
  --app-name "Logseq DB"
  --branch "$APP_BRANCH"
  --repo-name "$REPO_NAME"
  --repo-title "$REPO_TITLE"
  --repo-comment "$REPO_COMMENT"
  --repo-description "$REPO_DESCRIPTION"
  --icon-path flatpak/com.logseq.LogseqDB.svg
)
if [[ -n "$BASE_URL" ]]; then
  pages_args+=(--base-url "$BASE_URL")
fi
if [[ -n "$REPO_URL" ]]; then
  pages_args+=(--repo-url "$REPO_URL")
fi
if [[ -n "$GPG_PUBLIC_KEY" ]]; then
  pages_args+=(--gpg-key "$GPG_PUBLIC_KEY")
fi

python3 scripts/prepare-pages.py "${pages_args[@]}"

echo "Built dist/$BUNDLE_NAME"
echo "Prepared Flatpak repository in dist/pages"
