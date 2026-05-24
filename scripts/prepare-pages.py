#!/usr/bin/env python3
import argparse
import base64
import html
import shutil
import sys
from pathlib import Path


def fail(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(1)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def key_to_base64(path: Path | None) -> str:
    if not path:
        return ""
    return base64.b64encode(path.read_bytes()).decode("ascii")


def clean_url(url: str) -> str:
    return url.rstrip("/")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare a static GitHub Pages site for a Flatpak repository."
    )
    parser.add_argument("--repo-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--app-id", required=True)
    parser.add_argument("--app-name", default="Logseq DB")
    parser.add_argument("--branch", default="master")
    parser.add_argument("--repo-name", default="logseq-db")
    parser.add_argument("--repo-title", default="Logseq DB Flatpak")
    parser.add_argument("--repo-comment", default="Unofficial Logseq DB nightly Flatpak builds")
    parser.add_argument(
        "--repo-description",
        default="Auto-built Flatpak repository for upstream Logseq DB nightly releases.",
    )
    parser.add_argument("--base-url", default="")
    parser.add_argument("--repo-url", default="")
    parser.add_argument("--gpg-key", type=Path)
    parser.add_argument("--icon-path", default="flatpak/com.logseq.LogseqDB.svg", type=Path)
    args = parser.parse_args()

    repo_dir = args.repo_dir.resolve()
    output_dir = args.output_dir.resolve()
    published_repo = output_dir / "repo"
    if output_dir == repo_dir or repo_dir in output_dir.parents:
        fail("--output-dir must not be inside --repo-dir")

    if published_repo.exists():
        shutil.rmtree(published_repo)
    output_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(repo_dir, published_repo)

    icon_name = "logo.png"
    if args.icon_path.exists():
        icon_name = f"logo{args.icon_path.suffix or '.png'}"
        shutil.copy2(args.icon_path, output_dir / icon_name)

    base_url = clean_url(args.base_url)
    repo_url = clean_url(args.repo_url) if args.repo_url else ""
    if not repo_url:
        repo_url = f"{base_url}/repo" if base_url else published_repo.as_uri()

    icon_url = f"{base_url}/{icon_name}" if base_url else (output_dir / icon_name).as_uri()
    gpg_key = key_to_base64(args.gpg_key)

    gpg_line = f"GPGKey={gpg_key}\n" if gpg_key else ""
    repo_file = (
        "[Flatpak Repo]\n"
        "Version=1\n"
        f"Title={args.repo_title}\n"
        f"Url={repo_url}\n"
        f"Homepage={base_url or repo_url}\n"
        f"Comment={args.repo_comment}\n"
        f"Description={args.repo_description}\n"
        f"Icon={icon_url}\n"
        f"DefaultBranch={args.branch}\n"
        f"{gpg_line}"
    )
    write_text(output_dir / f"{args.repo_name}.flatpakrepo", repo_file)

    flatpakref_file = (
        "[Flatpak Ref]\n"
        "Version=1\n"
        f"Name={args.app_id}\n"
        f"Branch={args.branch}\n"
        f"Title={args.app_name}\n"
        f"Url={repo_url}\n"
        "RuntimeRepo=https://dl.flathub.org/repo/flathub.flatpakrepo\n"
        "IsRuntime=false\n"
        f"SuggestRemoteName={args.repo_name}\n"
        f"Homepage={base_url or repo_url}\n"
        f"Comment={args.repo_comment}\n"
        f"Description={args.repo_description}\n"
        f"Icon={icon_url}\n"
        f"{gpg_line}"
    )
    write_text(output_dir / f"{args.app_id}.flatpakref", flatpakref_file)

    warning = ""
    install_command = (
        f"flatpak remote-add --user --if-not-exists --from {args.repo_name} "
        f"{base_url}/{args.repo_name}.flatpakrepo"
        if base_url
        else f"flatpak remote-add --user --if-not-exists --from {args.repo_name} {output_dir / (args.repo_name + '.flatpakrepo')}"
    )
    if not gpg_key:
        warning = (
            "<p><strong>Unsigned repository:</strong> add it with "
            "<code>--no-gpg-verify</code> until CI signing secrets are configured.</p>"
        )
        install_command = (
            f"flatpak remote-add --user --if-not-exists --no-gpg-verify {args.repo_name} {repo_url}"
        )

    repo_link = f"{args.repo_name}.flatpakrepo"
    ref_link = f"{args.app_id}.flatpakref"
    index = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(args.repo_title)}</title>
  <style>
    body {{
      max-width: 760px;
      margin: 48px auto;
      padding: 0 20px;
      font: 16px/1.5 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: #1f2933;
    }}
    img {{ width: 96px; height: 96px; }}
    code {{ background: #eef2f6; padding: 2px 5px; border-radius: 4px; }}
    pre {{ background: #111827; color: #e5e7eb; padding: 16px; overflow-x: auto; border-radius: 6px; }}
    a {{ color: #0b67c1; }}
  </style>
</head>
<body>
  <img src="{html.escape(icon_name)}" alt="">
  <h1>{html.escape(args.repo_title)}</h1>
  <p>{html.escape(args.repo_description)}</p>
  {warning}
  <p><a href="{repo_link}">Add Flatpak repository</a></p>
  <p><a href="{ref_link}">Install {html.escape(args.app_name)} directly</a></p>
  <pre><code>{html.escape(install_command)}
flatpak install --user {html.escape(args.repo_name)} {html.escape(args.app_id)}
flatpak update --user {html.escape(args.app_id)}</code></pre>
</body>
</html>
"""
    write_text(output_dir / "index.html", index)
    write_text(output_dir / ".nojekyll", "")

    print(f"Prepared {output_dir}")
    print(f"Repository URL: {repo_url}")
    print(f"Repo file: {output_dir / repo_link}")
    print(f"Flatpak ref: {output_dir / ref_link}")


if __name__ == "__main__":
    main()
