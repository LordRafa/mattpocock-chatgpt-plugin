#!/usr/bin/env python3
"""Package upstream Matt Pocock skills for ChatGPT without storing them in Git.

Treat the cloned upstream repository as data; never execute upstream scripts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import stat
import zipfile
from pathlib import Path, PurePosixPath

import yaml

NAME = "mattpocock-skills-chatgpt"
SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
UPSTREAM = "https://github.com/mattpocock/skills"
SEMVER = re.compile(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?\Z")
MAX_FILE = 10 * 1024 * 1024


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def skill_frontmatter(path: Path) -> tuple[dict, str]:
    source = path.read_text(encoding="utf-8")
    parts = source.split("---\n", 2)
    if len(parts) != 3 or parts[0] != "":
        raise ValueError(f"Missing SKILL.md YAML frontmatter: {path}")
    metadata = yaml.safe_load(parts[1])
    if not isinstance(metadata, dict):
        raise ValueError(f"Invalid frontmatter: {path}")
    name, desc = metadata.get("name"), metadata.get("description")
    if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name):
        raise ValueError(f"Invalid skill name: {path}")
    if not isinstance(desc, str) or not desc.strip():
        raise ValueError(f"Missing skill description: {path}")
    return metadata, parts[2]


def package_skill(source: Path, target: Path) -> str:
    if source.is_symlink() or not source.is_dir() or not (source / "SKILL.md").is_file():
        raise ValueError(f"Invalid source skill: {source}")
    metadata, body = skill_frontmatter(source / "SKILL.md")
    name = metadata["name"]
    if source.name != name:
        raise ValueError(f"Directory and skill name mismatch: {source}")
    for item in source.rglob("*"):
        if item.is_symlink():
            raise ValueError(f"Symlinks are not allowed: {item}")
        if item.is_file() and item.stat().st_size > MAX_FILE:
            raise ValueError(f"Oversized upstream file: {item}")
        if ".git" in item.relative_to(source).parts:
            raise ValueError(f"Git internals found in skill: {item}")
    if (source / "SKILL.md").stat().st_size > 1_048_576:
        raise ValueError(f"SKILL.md is too large: {source}")
    shutil.copytree(source, target, symlinks=False)
    portable = {"name": name, "description": metadata["description"]}
    (target / "SKILL.md").write_text(
        "---\n" + yaml.safe_dump(portable, sort_keys=False, allow_unicode=True, width=120)
        + "---\n" + body, encoding="utf-8"
    )
    disable = metadata.get("disable-model-invocation", False)
    if not isinstance(disable, bool):
        raise ValueError(f"disable-model-invocation must be boolean: {source}")
    agent_path = target / "agents" / "openai.yaml"
    agent = yaml.safe_load(agent_path.read_text(encoding="utf-8")) if agent_path.exists() else {}
    if agent is None:
        agent = {}
    if not isinstance(agent, dict):
        raise ValueError(f"agents/openai.yaml must be a mapping: {source}")
    if disable:
        policy = agent.setdefault("policy", {})
        if not isinstance(policy, dict):
            raise ValueError(f"Invalid agent policy: {source}")
        policy["allow_implicit_invocation"] = False
    if disable or agent_path.exists():
        agent_path.parent.mkdir(parents=True, exist_ok=True)
        agent_path.write_text(yaml.safe_dump(agent, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return name


def build(upstream: Path, plugin_dir: Path, dist: Path, state_file: Path, sha: str) -> dict:
    upstream = upstream.resolve()
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise ValueError("Expected a 40-character upstream Git SHA")
    manifest = read_json(upstream / ".claude-plugin" / "plugin.json")
    version = manifest.get("version")
    if not isinstance(version, str) or not SEMVER.fullmatch(version):
        raise ValueError(f"Invalid upstream plugin version: {version!r}")
    entries = manifest.get("skills")
    if not isinstance(entries, list) or not entries:
        raise ValueError("No skills listed in upstream plugin manifest")
    if plugin_dir.exists() or plugin_dir.is_symlink():
        raise ValueError(f"Output must not exist: {plugin_dir}")
    plugin_dir.mkdir(parents=True)
    skills = plugin_dir / "skills"
    skills.mkdir()
    names = set()
    for entry in entries:
        if not isinstance(entry, str) or not entry.startswith("./skills/"):
            raise ValueError(f"Unexpected upstream path: {entry!r}")
        rel = PurePosixPath(entry)
        if ".." in rel.parts or ".git" in rel.parts or len(rel.parts) != 3:
            raise ValueError(f"Unsafe upstream path: {entry!r}")
        source = upstream / entry
        if not source.resolve().is_relative_to(upstream) or source.is_symlink():
            raise ValueError(f"Source escapes upstream: {entry}")
        name = source.name
        if name in names:
            raise ValueError(f"Duplicate skill name: {name}")
        names.add(name)
        package_skill(source, skills / name)
    licence = upstream / "LICENSE"
    if not licence.is_file() or licence.is_symlink():
        raise ValueError("Missing upstream LICENSE")
    shutil.copyfile(licence, plugin_dir / "LICENSE")
    plugin_manifest = {
        "$schema": SCHEMA,
        "name": NAME,
        "version": version,
        "description": "Unofficial ChatGPT package of Matt Pocock's engineering and productivity skills.",
        "author": {"name": "Matt Pocock (skills); independent community packaging"},
        "repository": UPSTREAM,
        "homepage": UPSTREAM,
        "license": "MIT",
        "keywords": ["engineering", "skills", "development", "teaching"],
        "extensions": {"com.openai": {"interface": {
            "displayName": "Matt Pocock Skills (Unofficial)",
            "shortDescription": "Coding and learning skills",
            "longDescription": "An independently generated ChatGPT distribution of Matt Pocock's skills; some workflows require CLI tools not available in web chat.",
            "developerName": "Independent community packaging",
            "category": "Productivity",
            "capabilities": [],
            "defaultPrompt": "Help me choose the appropriate Matt Pocock skill for my task."
        }}}
    }
    (plugin_dir / "plugin.json").write_text(json.dumps(plugin_manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (plugin_dir / "ATTRIBUTION.md").write_text(
        "# Attribution\n\nOriginal skills created by **Matt Pocock**: " + UPSTREAM +
        "\n\nThis unofficial distribution is generated automatically. "
        "See LICENSE for the original MIT license.\n\n"
        "The skill instructions may describe Claude Code features that aren't available in all ChatGPT sessions.\n",
        encoding="utf-8"
    )
    files = sorted((p for p in plugin_dir.rglob("*") if p.is_file()), key=lambda p: p.relative_to(plugin_dir).as_posix())
    digest = hashlib.sha256()
    for file in files:
        rel = file.relative_to(plugin_dir).as_posix().encode()
        data = file.read_bytes()
        digest.update(rel + b"\0" + str(len(data)).encode() + b"\0" + data)
    fingerprint = digest.hexdigest()
    previous = read_json(state_file) if state_file.is_file() else {}
    if previous and not SEMVER.fullmatch(str(previous.get("version", ""))):
        raise ValueError("Invalid version in saved state")
    if previous:
        prev_core = tuple(int(x) for x in previous["version"].split("-")[0].split("+")[0].split("."))
        new_core = tuple(int(x) for x in version.split("-")[0].split("+")[0].split("."))
        if new_core < prev_core:
            raise ValueError("Upstream version decreased; refusing to publish older version")
    changed = fingerprint != previous.get("fingerprint") or version != previous.get("version")
    meta = plugin_dir / "metadata"
    meta.mkdir()
    (meta / "upstream.json").write_text(json.dumps({
        "repository": UPSTREAM, "commit": sha, "version": version,
        "fingerprint": fingerprint, "skill_count": len(names)
    }, indent=2) + "\n", encoding="utf-8")
    dist.mkdir(parents=True, exist_ok=True)
    archive = dist / f"{NAME}-v{version}.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for file in sorted((p for p in plugin_dir.rglob("*") if p.is_file()), key=lambda p: p.relative_to(plugin_dir).as_posix()):
            arcname = f"{NAME}/{file.relative_to(plugin_dir).as_posix()}"
            info = zipfile.ZipInfo(arcname, date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            mode = 0o755 if file.stat().st_mode & stat.S_IXUSR else 0o644
            info.external_attr = (stat.S_IFREG | mode) << 16
            z.writestr(info, file.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert f"{NAME}/plugin.json" in z.namelist()
        assert len(z.namelist()) == len(set(z.namelist()))
    new_state = {"version": version, "fingerprint": fingerprint, "upstream_sha": sha, "skill_count": len(names)}
    (dist / "state.json").write_text(json.dumps(new_state, indent=2) + "\n", encoding="utf-8")
    return {**new_state, "changed": changed, "archive": str(archive)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", type=Path, required=True)
    parser.add_argument("--plugin-out", type=Path, required=True)
    parser.add_argument("--dist", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--github-output", type=Path)
    a = parser.parse_args()
    r = build(a.upstream, a.plugin_out, a.dist, a.state, a.sha)
    print(json.dumps(r, indent=2))
    if a.github_output:
        with a.github_output.open("a", encoding="utf-8") as f:
            f.write(f"changed={str(r['changed']).lower()}\nversion={r['version']}\narchive={r['archive']}\n")


if __name__ == "__main__":
    main()
