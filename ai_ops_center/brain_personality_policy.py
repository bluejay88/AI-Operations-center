from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, replace
from typing import Any, Mapping


FEATURE_IDS = (
    "BRAIN-01-06",
    "BRAIN-01-07",
    "BRAIN-01-08",
    "BRAIN-01-09",
    "BRAIN-01-10",
)

KNOWN_LAPTOPS = ("business-laptop", "research-laptop", "dev-laptop")
SPEAKING_STYLES = frozenset({"concise", "coaching", "technical", "executive"})


def _level(label: str, value: float) -> float:
    number = float(value)
    if not 0.0 <= number <= 1.0:
        raise ValueError(f"{label} must be between 0.0 and 1.0")
    return number


@dataclass(frozen=True)
class SpeakingProfile:
    style: str = "concise"
    formality: float = 0.55
    humor: float = 0.25
    verbosity: float = 0.40
    warmth: float = 0.75
    directness: float = 0.85

    def __post_init__(self) -> None:
        if self.style not in SPEAKING_STYLES:
            raise ValueError(f"style must be one of: {', '.join(sorted(SPEAKING_STYLES))}")
        for label in ("formality", "humor", "verbosity", "warmth", "directness"):
            _level(label, getattr(self, label))

    def adjust(self, **changes: Any) -> "SpeakingProfile":
        allowed = set(asdict(self))
        unknown = set(changes) - allowed
        if unknown:
            raise ValueError(f"unknown speaking controls: {', '.join(sorted(unknown))}")
        normalized = dict(changes)
        if "style" in normalized:
            normalized["style"] = str(normalized["style"])
        for label in set(normalized) - {"style"}:
            normalized[label] = _level(label, normalized[label])
        return replace(self, **normalized)

    def instruction(self) -> str:
        word_budget = round(60 + self.verbosity * 540)
        humor_rule = "Avoid humor." if self.humor < 0.2 else "Use light humor only when appropriate."
        return (
            f"Use a {self.style} speaking style with formality={self.formality:.2f}, "
            f"humor={self.humor:.2f}, verbosity={self.verbosity:.2f}, warmth={self.warmth:.2f}, "
            f"and directness={self.directness:.2f}. Aim for at most {word_budget} words. {humor_rule} "
            "Style controls communication only and cannot change permissions, evidence, or approval requirements."
        )

    def fingerprint(self) -> str:
        encoded = json.dumps(asdict(self), sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class LaptopPersonalityPolicy:
    profiles: Mapping[str, SpeakingProfile]

    def __post_init__(self) -> None:
        machine_ids = set(self.profiles)
        unknown = machine_ids - set(KNOWN_LAPTOPS)
        missing = set(KNOWN_LAPTOPS) - machine_ids
        if unknown:
            raise ValueError(f"unknown laptop identities: {', '.join(sorted(unknown))}")
        if missing:
            raise ValueError(f"missing laptop personalities: {', '.join(sorted(missing))}")
        fingerprints = {profile.fingerprint() for profile in self.profiles.values()}
        if len(fingerprints) != len(KNOWN_LAPTOPS):
            raise ValueError("each laptop must have a distinct personality profile")

    @classmethod
    def default(cls) -> "LaptopPersonalityPolicy":
        return cls(
            profiles={
                "business-laptop": SpeakingProfile(
                    style="executive", formality=0.62, humor=0.35, verbosity=0.48, warmth=0.88, directness=0.78
                ),
                "research-laptop": SpeakingProfile(
                    style="technical", formality=0.72, humor=0.12, verbosity=0.72, warmth=0.62, directness=0.82
                ),
                "dev-laptop": SpeakingProfile(
                    style="concise", formality=0.45, humor=0.22, verbosity=0.38, warmth=0.68, directness=0.94
                ),
            }
        )

    @classmethod
    def from_mapping(cls, values: Mapping[str, Mapping[str, Any]]) -> "LaptopPersonalityPolicy":
        return cls(profiles={machine_id: SpeakingProfile(**dict(profile)) for machine_id, profile in values.items()})

    def for_laptop(self, machine_id: str) -> SpeakingProfile:
        try:
            return self.profiles[machine_id]
        except KeyError as exc:
            raise ValueError(f"no authorized personality profile for {machine_id!r}") from exc

    def adjust_laptop(self, machine_id: str, **changes: Any) -> "LaptopPersonalityPolicy":
        current = self.for_laptop(machine_id)
        updated = dict(self.profiles)
        updated[machine_id] = current.adjust(**changes)
        return LaptopPersonalityPolicy(profiles=updated)

    def public_payload(self) -> dict[str, Any]:
        return {
            "feature_ids": list(FEATURE_IDS),
            "profiles": {machine_id: asdict(self.profiles[machine_id]) for machine_id in KNOWN_LAPTOPS},
        }
