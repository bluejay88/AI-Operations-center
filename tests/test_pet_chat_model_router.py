from ai_ops_center.model_router import _governed_prompt, _synthesize


def test_pet_chat_prompt_requests_direct_conversation() -> None:
    prompt = _governed_prompt("PET conversation", "Hello", False, interaction="pet_chat")
    assert "Reply directly to the user" in prompt
    assert "Do not output implementation plans" in prompt
    assert "require Brain/Jayla approval" in prompt


def test_pet_chat_synthesis_returns_only_first_completed_reply() -> None:
    result = _synthesize(
        [
            {"status": "completed", "provider": "one", "text": "Hello from your PET."},
            {"status": "completed", "provider": "two", "text": "Second provider response."},
            {"status": "failed", "provider": "three", "error": "secret diagnostic"},
        ],
        interaction="pet_chat",
    )
    assert result == "Hello from your PET."


def test_pet_chat_synthesis_has_safe_provider_failure_fallback() -> None:
    result = _synthesize([{"status": "failed", "error": "raw provider failure"}], interaction="pet_chat")
    assert "temporarily unavailable" in result
    assert "No task was started" in result
    assert "raw provider failure" not in result
