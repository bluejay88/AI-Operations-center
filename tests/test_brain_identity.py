import pytest

from ai_ops_center.brain_identity import BrainIdentityProfile, FEATURE_IDS


def test_batch_maps_exactly_to_five_catalog_features():
    assert FEATURE_IDS == (
        "BRAIN-01-01",
        "BRAIN-01-02",
        "BRAIN-01-03",
        "BRAIN-01-04",
        "BRAIN-01-05",
    )


def test_identity_has_stable_fingerprint_and_public_capability_payload():
    first = BrainIdentityProfile()

    # Derived fields are rejected instead of silently becoming mutable input.
    assert len(first.fingerprint()) == 64
    assert first.public_payload()["feature_ids"] == list(FEATURE_IDS)
    with pytest.raises(ValueError, match="unknown identity fields"):
        BrainIdentityProfile.from_mapping(first.public_payload() | {"fingerprint": "ignored"})


def test_identity_round_trip_and_fingerprint_are_deterministic():
    raw = {
        "pet_name": "Nexus",
        "device_id": "brain-gaming-pc",
        "avatar": {"accent_color": "#53F6C5", "alt_text": "Brain guardian"},
        "voice": {"voice_id": "local-voice", "rate": 1.1},
        "personality": {"warmth": 0.8, "directness": 0.9},
    }
    one = BrainIdentityProfile.from_mapping(raw)
    two = BrainIdentityProfile.from_mapping(raw)
    assert one == two
    assert one.fingerprint() == two.fingerprint()


def test_device_identity_format_and_registry_collision_are_rejected():
    with pytest.raises(ValueError, match="DNS-style"):
        BrainIdentityProfile(device_id="Brain PC")
    profile = BrainIdentityProfile(device_id="brain-gaming-pc")
    with pytest.raises(ValueError, match="already registered"):
        profile.assert_unique_device_identity(["dev-laptop", "BRAIN-GAMING-PC"])
    profile.assert_unique_device_identity(["dev-laptop", "research-laptop"])


def test_avatar_and_voice_are_validated():
    with pytest.raises(ValueError, match="hex color"):
        BrainIdentityProfile.from_mapping({"avatar": {"accent_color": "green"}})
    with pytest.raises(ValueError, match="voice rate"):
        BrainIdentityProfile.from_mapping({"voice": {"rate": 3.0}})


def test_personality_adjustment_is_immutable_bounded_and_safety_scoped():
    original = BrainIdentityProfile()
    adjusted = original.adjust_personality(warmth=0.95, verbosity=0.2)
    assert adjusted.personality.warmth == 0.95
    assert original.personality.warmth == 0.78
    assert adjusted.fingerprint() != original.fingerprint()
    assert "never override safety, approval, audit, or authorization" in adjusted.prompt_context()
    with pytest.raises(ValueError, match="between 0.0 and 1.0"):
        original.adjust_personality(humor=1.1)
    with pytest.raises(ValueError, match="unknown personality traits"):
        original.adjust_personality(recklessness=1.0)
