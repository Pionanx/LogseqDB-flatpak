#!/usr/bin/env python3
import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
import urllib.request
from pathlib import Path


UPSTREAM_REPO = "logseq/logseq"
API_ROOT = f"https://api.github.com/repos/{UPSTREAM_REPO}"
NIGHTLY_TAG = "nightly"
ASSET_RE = re.compile(r"^Logseq-linux-x86_64-.*\.zip$")


def fail(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(1)


def request(url: str) -> urllib.request.Request:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "logseq-db-flatpak-release-script",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return urllib.request.Request(url, headers=headers)


def fetch_json(url: str) -> dict:
    try:
        with urllib.request.urlopen(request(url), timeout=60) as response:
            return json.load(response)
    except Exception as exc:
        fail(f"failed to fetch {url}: {exc}")


def download_sha256(url: str, output: Path) -> str:
    output.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    try:
        with urllib.request.urlopen(request(url), timeout=300) as response, output.open("wb") as fh:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
                fh.write(chunk)
    except Exception as exc:
        fail(f"failed to download {url}: {exc}")
    return digest.hexdigest()


def sh_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def version_from_asset(asset_name: str) -> str:
    prefix = "Logseq-linux-x86_64-"
    suffix = ".zip"
    if asset_name.startswith(prefix) and asset_name.endswith(suffix):
        return asset_name[len(prefix) : -len(suffix)]
    fail(f"cannot derive version from asset {asset_name!r}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate Flatpak manifest inputs from the Logseq DB nightly GitHub Release."
    )
    parser.add_argument(
        "--repo-root",
        default=Path(__file__).resolve().parents[1],
        type=Path,
        help="Packaging repository root.",
    )
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    release = fetch_json(f"{API_ROOT}/releases/tags/{NIGHTLY_TAG}")
    assets = [asset for asset in release.get("assets", []) if ASSET_RE.match(asset.get("name", ""))]
    if not assets:
        names = ", ".join(asset.get("name", "<unnamed>") for asset in release.get("assets", []))
        fail(f"nightly release has no Linux x86_64 zip asset. Assets: {names}")

    asset = sorted(assets, key=lambda item: item["name"])[0]
    asset_url = asset.get("browser_download_url")
    if not asset_url:
        fail(f"asset {asset.get('name')} has no browser_download_url")

    digest = asset.get("digest") or ""
    if digest.startswith("sha256:"):
        asset_sha256 = digest.removeprefix("sha256:")
    else:
        cache_path = repo_root / "build" / "downloads" / asset["name"]
        asset_sha256 = download_sha256(asset_url, cache_path)

    version = version_from_asset(asset["name"])
    release_date = (release.get("published_at") or dt.date.today().isoformat())[:10]
    upstream_release_name = release.get("name") or NIGHTLY_TAG
    bundle_name = f"LogseqDB-{version}-x86_64.flatpak"

    manifest_template = (repo_root / "com.logseq.LogseqDB.yml.in").read_text(encoding="utf-8")
    manifest = (
        manifest_template.replace("@LOGSEQ_DB_ZIP_URL@", asset_url)
        .replace("@LOGSEQ_DB_ZIP_SHA256@", asset_sha256)
    )
    write_text(repo_root / "com.logseq.LogseqDB.yml", manifest)

    metainfo_template = (
        repo_root / "flatpak" / "com.logseq.LogseqDB.metainfo.xml.in"
    ).read_text(encoding="utf-8")
    metainfo = (
        metainfo_template.replace("@VERSION@", version)
        .replace("@RELEASE_DATE@", release_date)
        .replace("@UPSTREAM_RELEASE_NAME@", upstream_release_name)
    )
    write_text(repo_root / "build" / "generated" / "com.logseq.LogseqDB.metainfo.xml", metainfo)

    env = {
        "LOGSEQ_DB_TAG": NIGHTLY_TAG,
        "LOGSEQ_DB_VERSION": version,
        "LOGSEQ_DB_RELEASE_DATE": release_date,
        "LOGSEQ_DB_UPSTREAM_RELEASE_NAME": upstream_release_name,
        "LOGSEQ_DB_ASSET_NAME": asset["name"],
        "LOGSEQ_DB_ASSET_URL": asset_url,
        "LOGSEQ_DB_ASSET_SHA256": asset_sha256,
        "BUNDLE_NAME": bundle_name,
    }
    env_text = "".join(f"{key}={sh_quote(value)}\n" for key, value in env.items())
    write_text(repo_root / "build" / "generated" / "release.env", env_text)

    print(f"Generated Flatpak inputs for Logseq DB {version}")
    print(f"Upstream release: {upstream_release_name}")
    print(f"Asset: {asset['name']}")
    print(f"SHA256: {asset_sha256}")


if __name__ == "__main__":
    main()
