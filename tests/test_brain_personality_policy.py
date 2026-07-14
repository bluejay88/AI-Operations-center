import pytest

from ai_ops_center.brain_personality_policy import (
    FEATURE_IDS,
    KNOWN_LAPTOPS,
    LaptopPersonalityPolicy,
    SpeakingProfile,
)


def test_batch_maps_to_exact_catalog_features():
    assert FEATURE_IDS == tuple(f"BRAIN-01-{item:02d}" for item in range(6, 11))


def test_default_policy_defines_a_distinct_profile_for_every_laptop():
    policy = LaptopPersonalityPolicy.default()
    assert set(policy.profiles) == set(KNOWN_LAPTOPS)
    assert len({profile.fingerprint() for profile in policy.profiles.values()}) == 3
    assert policy.for_laptop("business-laptop").style == "executive"
    assert policy.for_laptop("research-laptop").style == "technical"
    assert policy.for_laptop("dev-laptop").style == "concise"


def test_speaking_formality_humor_and_verbosity_are_independently_adjustable():
    original = LaptopPersonalityPolicy.default()
    adjusted = original.adjust_laptop(
        "business-laptop", style="coaching", formality=0.4, humor=0.6, verbosity=0.7
    )
    profile = adjusted.for_laptop("business-laptop")
    assert (profile.style, profile.formality, profile.humor, profile.verbosity) == ("coaching", 0.4, 0.6, 0.7)
    assert original.for_laptop("business-laptop").style == "executive"


def test_levels_and_style_are_strictly_validated():
    with pytest.raises(ValueError, match="verbosity must be between"):
        SpeakingProfile(verbosity=1.01)
    with pytest.raises(ValueError, match="style must be one of"):
        SpeakingProfile(style="reckless")
    with pytest.raises(ValueError, match="unknown speaking controls"):
        SpeakingProfile().adjust(authorization="bypass")


def test_policy_rejects_missing_unknown_and_duplicate_laptop_profiles():
    default = LaptopPersonalityPolicy.default()
    with pytest.raises(ValueError, match="missing laptop personalities"):
        LaptopPersonalityPolicy(profiles={"dev-laptop": default.for_laptop("dev-laptop")})
    with pytest.raises(ValueError, match="unknown laptop identities"):
        LaptopPersonalityPolicy(profiles=default.profiles | {"untrusted-laptop": SpeakingProfile()})
    same = SpeakingProfile()
    with pytest.raises(ValueError, match="distinct personality"):
        LaptopPersonalityPolicy(profiles={machine_id: same for machine_id in KNOWN_LAPTOPS})


def test_policy_defensively_freezes_caller_and_exposed_mapping():
    raw = dict(LaptopPersonalityPolicy.default().profiles)
    policy = LaptopPersonalityPolicy(profiles=raw)
    raw["dev-laptop"] = SpeakingProfile(style="executive", humor=0.99)
    assert policy.for_laptop("dev-laptop").style == "concise"
    with pytest.raises(TypeError):
        policy.profiles["dev-laptop"] = SpeakingProfile(style="executive")  # type: ignore[index]


def test_resolution_fails_closed_and_instruction_preserves_authority_boundary():
    policy = LaptopPersonalityPolicy.default()
    with pytest.raises(ValueError, match="no authorized personality"):
        policy.for_laptop("unknown-laptop")
    instruction = policy.for_laptop("research-laptop").instruction()
    assert "cannot change permissions, evidence, or approval requirements" in instruction
    assert "at most" in instruction


def test_public_payload_is_ordered_and_does_not_claim_certification():
    payload = LaptopPersonalityPolicy.default().public_payload()
    assert payload["feature_ids"] == list(FEATURE_IDS)
    assert list(payload["profiles"]) == list(KNOWN_LAPTOPS)
    assert payload["inventory_version"] == "machines.yaml:laptops-v1"
    assert "status" not in payload
    assert "operational" not in str(payload).lower()
