"""Check exact coverage, base controls and the NeoForge simple conflict model."""
from itertools import combinations
import re

from build_preset import PRESET, UNBOUND, layout, registry, render, vanilla_bindings

KEYBOARD = re.compile(
    r"key\.keyboard\.(?:[a-z0-9]|f(?:[1-9]|1[0-2])|keypad\.(?:[0-9]|add|multiply|divide|decimal)"
    r"|space|tab|left\.shift|left\.control|(?:left|right)\.alt|slash|grave\.accent|equal|minus"
    r"|(?:left|right)\.bracket|apostrophe|backslash|comma|period|semicolon|caps\.lock"
    r"|page\.(?:up|down)|up|down|left|right|insert|delete|home|end|escape|backspace|unknown)"
)
MODIFIERS = {"SHIFT": "shift", "CONTROL": "control", "ALT": "alt"}


def overlaps(first, second):
    return first == second or "UNIVERSAL" in (first, second)


def modifier_key(modifier, keyboard):
    return modifier in MODIFIERS and keyboard in {
        f"key.keyboard.{side}.{MODIFIERS[modifier]}" for side in ("left", "right")
    }


def conflict(a, b):
    key_a, mod_a, ctx_a = a
    key_b, mod_b, ctx_b = b
    if not overlaps(ctx_a, ctx_b):
        return False
    if modifier_key(mod_a, key_b) or modifier_key(mod_b, key_a):
        return True
    return key_a == key_b and (
        mod_a == mod_b or ("NONE" in (mod_a, mod_b) and
                           (overlaps(ctx_a, "IN_GAME") or overlaps(ctx_b, "IN_GAME")))
    )


def main():
    names = registry()
    selected = layout()
    if PRESET.read_bytes() != render(names, selected).encode("utf-8"):
        raise ValueError("Run build_preset.py to regenerate the shipped file")
    for name, value in vanilla_bindings().items():
        if names[name]["observed"] != value or selected[name] != value:
            raise ValueError(f"Base mapping changed: {name}")
    active = {}
    for name, value in selected.items():
        key, separator, modifier = value.partition(":")
        if not (KEYBOARD.fullmatch(key) or key in {"key.mouse.left", "key.mouse.right", "key.mouse.middle"}):
            raise ValueError(f"Unknown input: {value}")
        if separator and (modifier not in MODIFIERS or modifier_key(modifier, key)):
            raise ValueError(f"Invalid chord: {value}")
        context = names[name]["context"]
        if context not in {"UNIVERSAL", "GUI", "IN_GAME"}:
            raise ValueError(f"Unknown conflict context: {name}")
        if key != UNBOUND:
            active[name] = key, modifier or "NONE", context
    conflicts = [(a, b) for a, b in combinations(active, 2) if conflict(active[a], active[b])]
    if conflicts:
        raise ValueError(f"Overlapping bindings: {conflicts}")
    previous = {}
    for name, row in names.items():
        key, _, mod = row["observed"].partition(":")
        if key != UNBOUND:
            previous[name] = key, mod or "NONE", row["context"]
    prior_pairs = sum(conflict(previous[a], previous[b]) for a, b in combinations(previous, 2))
    print(f"{len(names)} mappings, {len(active)} bound, {len(names) - len(active)} unbound, "
          f"{sum(mod != 'NONE' for _, mod, _ in active.values())} chords, "
          f"{len(vanilla_bindings())} base mappings, {prior_pairs} -> 0 modeled conflicts")


if __name__ == "__main__":
    main()
