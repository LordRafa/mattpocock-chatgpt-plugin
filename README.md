# Matt Pocock Skills → ChatGPT (unofficial, automated packaging)

> **The original skills are by [Matt Pocock](https://github.com/mattpocock).**  
> Original project: **[mattpocock/skills](https://github.com/mattpocock/skills)**.  
> This independent project is an unofficial packaging tool—not a fork, not a replacement for the original project, and not affiliated with Matt Pocock or OpenAI.

This repository exists simply to **make Matt Pocock's skills easier to use in personal ChatGPT**. It automatically generates an OpenAI-compatible, skills-only plugin ZIP from his original public repository. **Matt's skills are never copied into this repository's Git history.** They are fetched at build time and distributed only in generated GitHub Release ZIPs.

## Automated packaging

Every Monday at **04:00 UTC**, on a manual workflow dispatch, or after relevant tooling changes:

1. Clone the original repository read-only on an ephemeral GitHub Actions runner.
2. Read its `.claude-plugin/plugin.json` to identify the included skills.
3. Copy `SKILL.md`, supporting files, and existing `agents/openai.yaml` settings; adjust Claude-specific frontmatter when necessary.
4. Set the generated plugin version to **exactly Matt's original plugin version**. For example, upstream `1.3.2` becomes `mattpocock-skills-chatgpt-v1.3.2.zip`, not a separately bumped version.
5. If plugin content or the upstream version changes, publish/update a GitHub Release asset. If Matt changes content without bumping the version, the ZIP for that same release tag is refreshed (unless release immutability prevents replacement).
6. Commit **only non-skill sync metadata** (`state/latest.json`), to avoid re-releasing unchanged packages.

**The generated skills themselves are never committed to this repository.** Releases preserve the original MIT license, attribution, and upstream commit SHA. The packaging workflow **does not execute upstream scripts**.

## Installation (personal ChatGPT accounts)

Download the newest `mattpocock-skills-chatgpt-vX.Y.Z.zip` from [Releases](../../releases). Use ChatGPT's Plugin Creator to install it as a private skills-only plugin. For a later release, update your existing plugin rather than creating another one.

The GitHub Release is produced automatically, but personal ChatGPT plugins do not have a confirmed unattended GitHub marketplace-sync mechanism. Installing the new ZIP in ChatGPT remains a separate step.

Skills can refer to Claude Code-specific tools and terminal workflows. Packaging them doesn't automatically make those tools available inside ChatGPT web. Treat skill instructions from third-party sources as untrusted until reviewed.

## Run locally

Requires Git, Python 3.12+ and PyYAML:

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
git clone --depth 1 https://github.com/mattpocock/skills.git /tmp/matt-skills
python -m scripts.build \
  --upstream /tmp/matt-skills \
  --sha "$(git -C /tmp/matt-skills rev-parse HEAD)" \
  --plugin-out /tmp/matt-plugin/output/mattpocock-skills-chatgpt \
  --dist /tmp/matt-plugin/dist \
  --state state/latest.json
```

To trigger packaging manually, open **Actions → Package Matt Pocock skills → Run workflow**. GitHub may automatically disable scheduled actions after 60 days of inactivity in a public repository.

## Credits and license

- **Original skills:** Created by Matt Pocock and upstream contributors. [Original repository](https://github.com/mattpocock/skills), [upstream MIT license](https://github.com/mattpocock/skills/blob/main/LICENSE). Generated ZIPs include the original license unchanged.
- **Packaging tooling and this repository:** MIT licensed, see [LICENSE](LICENSE).
- This project makes no claim of authorship of the original skills or endorsement from Matt Pocock or OpenAI.

Please report problems with the **skill content** to its original project and problems with **the converter/automation** to this repository.
