from ai_ops_center import worker
from ai_ops_center.pet_instruction_protocol import InstructionDecision


def _message(message_type="brain_instruction", metadata=None):
    return {
        "id": 41,
        "target_id": "dev-laptop",
        "status": "delivered",
        "message_type": message_type,
        "subject": "Protected instruction",
        "priority": 80,
        "metadata": metadata or {},
    }


def test_unsigned_brain_instruction_is_rejected_without_acknowledgement(monkeypatch):
    events = []
    monkeypatch.setattr(worker, "speaker_feed", lambda *args, **kwargs: {"messages": [_message()]})
    monkeypatch.setattr(worker, "submit_listener_event", lambda **kwargs: events.append(kwargs) or {"event_id": 1})
    monkeypatch.setattr(worker, "acknowledge_speaker_message", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("must not ack")))
    assert worker._consume_machine_messages("dev-laptop") == 0
    assert events[0]["event_type"] == "speaker_message_rejected"
    assert events[0]["metadata"]["instruction_decision"]["feature_id"] == "PET-02-04"


def test_noninstruction_notification_preserves_existing_receipt_path(monkeypatch):
    events = []
    acknowledgements = []
    monkeypatch.setattr(worker, "speaker_feed", lambda *args, **kwargs: {"messages": [_message("status_update")]})
    monkeypatch.setattr(worker, "submit_listener_event", lambda **kwargs: events.append(kwargs) or {"event_id": 1})
    monkeypatch.setattr(worker, "acknowledge_speaker_message", lambda *args, **kwargs: acknowledgements.append((args, kwargs)))
    assert worker._consume_machine_messages("dev-laptop") == 1
    assert events[0]["event_type"] == "speaker_message_received"
    assert len(acknowledgements) == 1


def test_connectivity_query_returns_allowlisted_structured_evidence(monkeypatch):
    events = []
    acknowledgements = []
    message = _message(
        "connectivity_diagnostic_query",
        metadata={
            "requested_channels": ["ssh-22", "arbitrary-shell"],
            "correlation_id": "connectivity-query-7",
        },
    )
    monkeypatch.setattr(worker, "speaker_feed", lambda *args, **kwargs: {"messages": [message]})
    monkeypatch.setattr(worker, "submit_listener_event", lambda **kwargs: events.append(kwargs) or {"event_id": 1})
    monkeypatch.setattr(worker, "acknowledge_speaker_message", lambda *args, **kwargs: acknowledgements.append((args, kwargs)))

    assert worker._consume_machine_messages("dev-laptop") == 1
    response = events[0]
    assert response["event_type"] == "connectivity_diagnostic_response"
    assert response["metadata"]["requested_channels"] == ["ssh-22"]
    assert response["metadata"]["correlation_id"] == "connectivity-query-7"
    assert response["metadata"]["host_shell_executed"] is False
    assert events[1]["event_type"] == "speaker_message_received"
    assert len(acknowledgements) == 1


def test_verified_instruction_enters_existing_receipt_path(monkeypatch):
    envelope = {"signer_id": "brain-gaming-pc"}
    events = []
    monkeypatch.setattr(worker, "speaker_feed", lambda *args, **kwargs: {"messages": [_message(metadata={"instruction_envelope": envelope})]})
    monkeypatch.setattr(
        worker,
        "verify_instruction",
        lambda *args, **kwargs: InstructionDecision(
            True,
            "accepted",
            "PET-02-05",
            "instruction-0001",
            "dev-laptop",
            "brain-gaming-pc",
            "a" * 64,
        ),
    )
    monkeypatch.setattr(worker, "submit_listener_event", lambda **kwargs: events.append(kwargs) or {"event_id": 1})
    monkeypatch.setattr(worker, "acknowledge_speaker_message", lambda *args, **kwargs: None)
    assert worker._consume_machine_messages("dev-laptop") == 1
    assert events[0]["event_type"] == "speaker_message_received"
    assert events[0]["metadata"]["instruction_decision"]["instruction_id"] == "instruction-0001"
    assert events[0]["metadata"]["instruction_decision"]["signer_id"] == "brain-gaming-pc"
    assert events[0]["metadata"]["verified_envelope_sha256"] == "a" * 64
