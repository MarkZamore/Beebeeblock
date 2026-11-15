"""Build the options.txt key lines from the recorded NeoForge registry and layout."""
import csv
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRESET = HERE.parent.parent / "launcher/controls-preset.txt"
UNBOUND = "key.keyboard.unknown"


def registry():
    with (HERE / "registered-keys.tsv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream, delimiter="\t"))
    names = {row["name"]: row for row in rows}
    if not names or len(names) != len(rows):
        raise ValueError("Empty or duplicated native registry")
    return names


def vanilla_bindings():
    return json.loads((HERE / "vanilla.json").read_text(encoding="utf-8"))


def layout():
    selected = vanilla_bindings()
    for line in (HERE / "layout.tsv").read_text(encoding="utf-8").splitlines():
        name, key = line.split("\t")
        if name in selected:
            raise ValueError(f"Repeated or vanilla layout entry: {name}")
        selected[name] = "key.keyboard." + key
    return selected


def render(names, selected):
    if unknown := selected.keys() - names.keys():
        raise ValueError(f"Unregistered mappings: {sorted(unknown)}")
    header = "# Beebeeblock 3.07.8, Minecraft 1.21.1 / NeoForge 21.1.251\n"
    return header + "".join(f"key_{name}:{selected.get(name, UNBOUND)}\n" for name in names)


if __name__ == "__main__":
    PRESET.write_bytes(render(registry(), layout()).encode("utf-8"))
