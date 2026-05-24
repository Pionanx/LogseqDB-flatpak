#!/usr/bin/env python3
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


UPSTREAM_REPO = "logseq/logseq"
NIGHTLY_TAG = "nightly"
ASSET_RE = re.compile(r"^Logseq-linux-x86_64-.*\.zip$")


def fail(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(1)


def request(url: str) -> urllib.request.Request:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "logseq-db-flatpak-release-check",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return urllib.request.Request(url, headers=headers)


def fetch_json(url: str, allow_404: bool = False) -> dict | None:
    try:
        with urllib.request.urlopen(request(url), timeout=60) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        if allow_404 and exc.code == 404:
            return None
        fail(f"failed to fetch {url}: HTTP {exc.code}")
    except Exception as exc:
        fail(f"failed to fetch {url}: {exc}")


def parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def github_tag_url(repo: str, tag: str) -> str:
    quoted_tag = urllib.parse.quote(tag, safe="")
    return f"https://api.github.com/repos/{repo}/releases/tags/{quoted_tag}"


def write_outputs(outputs: dict[str, str]) -> None:
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as fh:
            for key, value in outputs.items():
                fh.write(f"{key}={value.replace(chr(10), ' ')}\n")

    generated = Path("build/generated")
    generated.mkdir(parents=True, exist_ok=True)
    with (generated / "check.env").open("w", encoding="utf-8") as fh:
        for key, value in outputs.items():
            escaped = value.replace(chr(39), chr(39) + chr(34) + chr(39) + chr(34) + chr(39))
            fh.write(f"{key.upper()}='{escaped}'\n")


def version_from_asset(asset_name: str) -> str:
    prefix = "Logseq-linux-x86_64-"
    suffix = ".zip"
    if asset_name.startswith(prefix) and asset_name.endswith(suffix):
        return asset_name[len(prefix) : -len(suffix)]
    fail(f"cannot derive version from asset {asset_name!r}")


def release_tag_from_version(version: str) -> str:
    safe_version = re.sub(r"[^A-Za-z0-9._-]+", "-", version).strip("-")
    return f"logseq-db-{safe_version}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Resolve whether a Logseq DB Flatpak release should be built.")
    parser.add_argument(
        "--packaging-repo",
        required=True,
        help="This GitHub repository in owner/name form.",
    )
    parser.add_argument(
        "--force",
        default="false",
        help="Build even when the matching packaging release already exists.",
    )
    args = parser.parse_args()

    release = fetch_json(github_tag_url(UPSTREAM_REPO, NIGHTLY_TAG))
    if not release:
        fail("could not resolve upstream nightly release")

    assets = [asset for asset in release.get("assets", []) if ASSET_RE.match(asset.get("name", ""))]
    if not assets:
        names = ", ".join(asset.get("name", "<unnamed>") for asset in release.get("assets", []))
        fail(f"nightly release has no Linux x86_64 zip asset. Assets: {names}")

    asset = sorted(assets, key=lambda item: item["name"])[0]
    version = version_from_asset(asset["name"])
    release_tag = release_tag_from_version(version)
    existing_release = fetch_json(github_tag_url(args.packaging_repo, release_tag), allow_404=True)
    exists = existing_release is not None
    force = parse_bool(args.force)
    should_build = force or not exists
    reason = "forced rebuild" if force and exists else "new upstream nightly" if should_build else f"{release_tag} already exists"

    outputs = {
        "tag": NIGHTLY_TAG,
        "version": version,
        "release_tag": release_tag,
        "asset_name": asset["name"],
        "should_build": "true" if should_build else "false",
        "exists": "true" if exists else "false",
        "reason": reason,
        "upstream_release_name": release.get("name") or NIGHTLY_TAG,
    }
    write_outputs(outputs)

    print(f"Upstream tag: {NIGHTLY_TAG}")
    print(f"Upstream release: {outputs['upstream_release_name']}")
    print(f"Version: {version}")
    print(f"Packaging release tag: {release_tag}")
    print(f"Asset: {asset['name']}")
    print(f"Existing packaging release: {outputs['exists']}")
    print(f"Should build: {outputs['should_build']} ({reason})")


if __name__ == "__main__":
    main()
