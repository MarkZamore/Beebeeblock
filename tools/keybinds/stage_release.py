"""Stage a preset-only update over the existing verified pack release."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from build_preset import PRESET

PRESET_PATH = "launcher/controls-preset.txt"
REPO = PRESET.parent.parent


def fingerprint(data):
    return {"sizeBytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def encode(data):
    return (json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


def read_asset(path, descriptor, names):
    data = path.read_bytes()
    require(all(descriptor[k] == v for k, v in fingerprint(data).items()), f"Asset fingerprint differs: {path.name}")
    with ZipFile(io.BytesIO(data)) as archive:
        require(sorted(archive.namelist()) == sorted(names), f"Unexpected archive contents: {path.name}")
        return {name: archive.read(name) for name in names}


def zip_bytes(members, library=False):
    result = io.BytesIO()
    with ZipFile(result, "w") as archive:
        for name, data in members.items():
            entry = ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            entry.create_system = 0 if library else 3
            archive.writestr(entry, data, compress_type=ZIP_DEFLATED)
    return result.getvalue()


def stage(base, launcher_archive, library_archive, output):
    manifest = json.loads(base.read_bytes())
    require(manifest["packId"] == "minecraft-16" and manifest["minecraftVersion"] == "1.21.1" and
            manifest["loader"] == {"type": "neoforge", "version": "21.1.251"}, "Unexpected pack platform")
    revision = subprocess.check_output(["git", "-C", str(REPO), "rev-parse", "HEAD"], text=True).strip()
    subprocess.run(["git", "-C", str(REPO), "merge-base", "--is-ancestor", manifest["revision"], revision], check=True)
    require(PRESET.read_bytes() == subprocess.check_output(
        ["git", "-C", str(REPO), "show", f"{revision}:{PRESET_PATH}"]), "Preset differs from Git")
    assets = manifest["assets"]
    launcher_assets = [row for row in assets if any(name.startswith("launcher/") for name in row["covers"])]
    require(len(launcher_assets) == 1, "Expected one launcher data archive")
    launcher = launcher_assets[0]
    require(launcher["kind"] == "zipRoot" and all(name.startswith("launcher/") for name in launcher["covers"]),
            "Unexpected launcher archive")
    files = {row["path"]: row for row in manifest["files"]}
    launcher_files = read_asset(launcher_archive, launcher, launcher["covers"])
    for name, data in launcher_files.items():
        require(files[name] == {"path": name, **fingerprint(data)}, f"Launcher member differs: {name}")
    launcher_files[PRESET_PATH] = PRESET.read_bytes()
    files[PRESET_PATH] = {"path": PRESET_PATH, **fingerprint(launcher_files[PRESET_PATH])}
    launcher_bytes = zip_bytes(dict(sorted(launcher_files.items())))
    launcher_pin = fingerprint(launcher_bytes)
    launcher_name = f"r-{launcher_pin['sha256'][:12]}-launcher.zip"

    library = read_asset(library_archive, manifest["library"], ["library.json", "preview.jpg"])
    card = json.loads(library["library.json"])
    require(card["revision"] == manifest["revision"] and card["id"] == manifest["packId"],
            "Library and pack revisions differ")
    card["revision"] = revision
    library["library.json"] = json.dumps(card, ensure_ascii=False, indent=2).encode() + b"\n"
    library_bytes = zip_bytes(library, library=True)
    library_pin = fingerprint(library_bytes)
    library_name = f"library-{library_pin['sha256']}.zip"

    manifest["revision"] = revision
    manifest["generatedAtUtc"] = subprocess.check_output(
        ["git", "-C", str(REPO), "show", "-s", "--format=%cI", revision], text=True).strip()
    manifest["library"] = {"name": library_name, "revision": revision, **library_pin}
    manifest["files"] = sorted(files.values(), key=lambda row: row["path"])
    manifest["assets"] = sorted([row for row in assets if row != launcher] + [
        {"name": launcher_name, "kind": "zipRoot", "covers": sorted(launcher_files), **launcher_pin}
    ], key=lambda row: row["name"])
    require(sorted(asset_path for row in manifest["assets"] for asset_path in row["covers"]) == sorted(files),
            "Asset mapping does not cover the manifest exactly once")

    output.mkdir()
    (output / launcher_name).write_bytes(launcher_bytes)
    (output / library_name).write_bytes(library_bytes)
    (output / "pack-manifest.json").write_bytes(encode(manifest))
    print(files[PRESET_PATH])


if __name__ == "__main__":
    stage(*map(Path, sys.argv[1:]))
