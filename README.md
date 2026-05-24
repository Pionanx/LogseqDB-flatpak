# Logseq DB Flatpak Release Packaging

This repository packages the upstream Logseq DB Linux nightly zip as a Flatpak
app. The GitHub workflow publishes a single-file `.flatpak` bundle to GitHub
Releases and can optionally publish an updateable Flatpak repository to GitHub
Pages.

Upstream project: <https://github.com/logseq/logseq>

The package app ID is `com.logseq.LogseqDB`, so it does not replace the stable
Flathub `com.logseq.Logseq` package.

## Local Build

Install Flatpak tooling and the required runtime:

```bash
flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
flatpak install --user -y flathub org.flatpak.Builder org.freedesktop.Platform//25.08 org.freedesktop.Sdk//25.08 org.electronjs.Electron2.BaseApp//25.08
```

Build the latest upstream DB nightly:

```bash
./scripts/build-flatpak.sh
```

The output is written to `dist/`:

```bash
flatpak install --user -y dist/LogseqDB-*-x86_64.flatpak
flatpak run com.logseq.LogseqDB
```

The script also prepares a static Flatpak repository under `dist/pages/`. For
local testing without GPG signing:

```bash
flatpak --user remote-add --if-not-exists --no-gpg-verify logseq-db dist/pages/repo
flatpak --user install -y logseq-db com.logseq.LogseqDB
flatpak --user update com.logseq.LogseqDB
```

## GitHub Release

Run the `Build Flatpak Release` workflow manually. It resolves the current
upstream `logseq/logseq` `nightly` release and packages the
`Logseq-linux-x86_64-*.zip` asset.

The workflow also runs every 6 hours. Scheduled runs only build when this
packaging repository does not already have the matching `logseq-db-<version>`
release tag.

The workflow:

1. Reads the upstream `nightly` GitHub Release metadata.
2. Finds the `Logseq-linux-x86_64-*.zip` asset.
3. Checks whether `logseq-db-<upstream-version>` already exists.
4. Generates the Flatpak manifest with the asset URL and SHA256.
5. Builds `LogseqDB-<version>-x86_64.flatpak`.
6. Publishes the bundle to this repository's GitHub Releases.

Manual workflow runs enable `force` by default, so they can rebuild an existing
Flatpak release. Scheduled runs never force rebuilds.

If `deploy_pages` is enabled in a manual workflow run, it also publishes:

- `https://<owner>.github.io/<repo>/logseq-db.flatpakrepo`
- `https://<owner>.github.io/<repo>/com.logseq.LogseqDB.flatpakref`
- `https://<owner>.github.io/<repo>/repo/`

Enable GitHub Pages for this repository with source set to **GitHub Actions** if
you want the updateable repository. Unsigned repositories require
`--no-gpg-verify`, which is appropriate only for personal testing.

For a signed remote, configure:

1. A passphrase-less GPG key dedicated to this Flatpak repository.
2. Repository secret `FLATPAK_GPG_PRIVATE_KEY` containing the private key export.
3. Repository variable `FLATPAK_GPG_KEY_ID`, or secret `FLATPAK_GPG_KEY_ID`.

## Notes

This follows Logseq's DB version nightly builds. Use a test graph or backups
before relying on it for important data.
