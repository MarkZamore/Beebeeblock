"""Apply Beebeeblock's release files to a verified author build or public release."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from build_preset import PRESET

PRESET_PATH = "launcher/controls-preset.txt"
OWNERSHIP_PATH = "launcher/pack-owned.txt"
WARNING_SCRIPT = "kubejs/client_scripts/lanminecraft_multiplayer_warning.js"
WARNING_SHA256 = "3137e176701ae1d94ec73d99bc2dd007ef0c77fc053283d6489fc1a51ea4bfef"
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


def verify_warning(manifest, archives):
    files = {row["path"]: row for row in manifest["files"]}
    require(files.get(WARNING_SCRIPT, {}).get("sha256") == WARNING_SHA256,
            "Manifest is missing the reviewed multiplayer warning setting")
    for path in (WARNING_SCRIPT, OWNERSHIP_PATH):
        row, = (asset for asset in manifest["assets"] if path in asset["covers"])
        members = read_asset(archives / row["name"], row, row["covers"])
        data = members[path]
        require(files[path] == {"path": path, **fingerprint(data)}, f"Archive member differs: {path}")
        if path == OWNERSHIP_PATH:
            require(WARNING_SCRIPT in data.decode().splitlines(), "Warning script must be pack-owned")


def stage(base, output):
    manifest = json.loads(base.read_bytes())
    require(manifest["packId"] == "minecraft-16" and manifest["minecraftVersion"] == "1.21.1" and
            manifest["loader"]["type"] == "neoforge" and manifest["loader"]["version"].startswith("21.1."),
            "Review multiplayer warning policy on a changed pack platform")
    revision = subprocess.check_output(["git", "-C", str(REPO), "rev-parse", "HEAD"], text=True).strip()
    subprocess.run(["git", "-C", str(REPO), "merge-base", "--is-ancestor", manifest["revision"], revision], check=True)
    changes = {}
    for name in (PRESET_PATH, WARNING_SCRIPT):
        data = (REPO / name).read_bytes()
        require(data == subprocess.check_output(
            ["git", "-C", str(REPO), "show", f"{revision}:{name}"]), f"Pack file differs from Git: {name}")
        changes[name] = data
    assets = manifest["assets"]
    launcher_assets = [row for row in assets if any(name.startswith("launcher/") for name in row["covers"])]
    require(len(launcher_assets) == 1, "Expected one launcher data archive")
    launcher = launcher_assets[0]
    require(launcher["kind"] == "zipRoot" and all(name.startswith("launcher/") for name in launcher["covers"]),
            "Unexpected launcher archive")
    files = {row["path"]: row for row in manifest["files"]}
    require(any(name.startswith("mods/kubejs-neoforge-") and name.endswith(".jar") for name in files),
            "Review multiplayer warning policy after KubeJS removal")
    require(fingerprint(changes[WARNING_SCRIPT])["sha256"] == WARNING_SHA256,
            "Warning script differs from the reviewed policy")
    scripts_assets = [row for row in assets if WARNING_SCRIPT in row["covers"]]
    require(len(scripts_assets) <= 1 and all(row["kind"] == "zipRoot" for row in scripts_assets),
            "Unexpected multiplayer warning script archive")
    scripts = next(iter(scripts_assets), None)
    rebuilt = {}
    for suffix, row, path in (
        ("launcher", launcher, PRESET_PATH),
        ("multiplayer-warning", scripts, WARNING_SCRIPT),
    ):
        members = read_asset(base.parent / row["name"], row, row["covers"]) if row else {}
        for name, data in members.items():
            require(files[name] == {"path": name, **fingerprint(data)}, f"Archive member differs: {name}")
        if path == PRESET_PATH:
            claims = set(members[OWNERSHIP_PATH].decode().splitlines()) | {WARNING_SCRIPT}
            members[OWNERSHIP_PATH] = ("\n".join(sorted(claims)) + "\n").encode()
        members[path] = changes[path]
        for name, data in members.items():
            files[name] = {"path": name, **fingerprint(data)}
        data = zip_bytes(dict(sorted(members.items())))
        pin = fingerprint(data)
        name = f"r-{pin['sha256'][:12]}-{suffix}.zip"
        rebuilt[name] = (data, {"name": name, "kind": "zipRoot", "covers": sorted(members), **pin})

    library = read_asset(base.parent / manifest["library"]["name"], manifest["library"],
                         ["library.json", "preview.jpg"])
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
    manifest["assets"] = sorted(
        [row for row in assets if row not in (launcher, scripts)] + [row for _, row in rebuilt.values()],
        key=lambda row: row["name"],
    )
    require(sorted(asset_path for row in manifest["assets"] for asset_path in row["covers"]) == sorted(files),
            "Asset mapping does not cover the manifest exactly once")

    output.mkdir()
    for name, (data, _) in rebuilt.items():
        (output / name).write_bytes(data)
    (output / library_name).write_bytes(library_bytes)
    verify_warning(manifest, output)
    (output / "pack-manifest.json").write_bytes(encode(manifest))
    for name in changes:
        print(files[name])


if __name__ == "__main__":
    if sys.argv[1] == "verify":
        manifest = Path(sys.argv[2])
        verify_warning(json.loads(manifest.read_bytes()), manifest.parent)
    else:
        stage(*map(Path, sys.argv[1:]))
