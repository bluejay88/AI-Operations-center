import asyncio

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from ai_ops_center import api


def request(request_id: str, purpose: str) -> api.ModelQueryRequest:
    return api.ModelQueryRequest(
        purpose=purpose,
        prompt="Safe status question",
        requester="business-laptop",
        target_id="business-laptop",
        request_id=request_id,
        auto_create_tasks=False,
        require_approval=False,
        options={"interaction": "pet_chat"},
    )


def http_request() -> Request:
    return Request({"type": "http", "method": "POST", "path": "/models/query", "headers": [], "app": api.app})


def test_cancellation_is_scoped_to_one_unpredictable_request_id(monkeypatch):
    async def scenario():
        release = {"first": asyncio.Event(), "second": asyncio.Event()}

        async def fake_submit_model_query(**kwargs):
            purpose = kwargs["purpose"]
            await release[purpose].wait()
            return {"status": "recorded", "synthesized_response": purpose}

        monkeypatch.setattr(api, "submit_model_query", fake_submit_model_query)
        first_id = "pet_11111111222222223333333344444444"
        second_id = "pet_aaaaaaaa55555555bbbbbbbb66666666"
        first = asyncio.create_task(api.models_query(request(first_id, "first"), http_request()))
        second = asyncio.create_task(api.models_query(request(second_id, "second"), http_request()))
        await asyncio.sleep(0)

        receipt = await api.cancel_model_query(first_id, http_request())
        assert receipt == {
            "request_id": first_id,
            "cancellation_requested": True,
            "status": "stop_requested",
            "scope": "request_only",
            "upstream_cancellation_guaranteed": False,
        }
        with pytest.raises(asyncio.CancelledError):
            await first
        assert not second.done()

        release["second"].set()
        response = await second
        assert response["request_id"] == second_id
        assert response["synthesized_response"] == "second"
        assert first_id not in api._model_query_tasks
        assert second_id not in api._model_query_tasks

    asyncio.run(scenario())


def test_cancel_unknown_request_is_honest_noop():
    receipt = asyncio.run(api.cancel_model_query("pet_00000000000000000000000000000000", http_request()))
    assert receipt["cancellation_requested"] is False
    assert receipt["status"] == "not_active"
    assert receipt["upstream_cancellation_guaranteed"] is False


def test_cancel_rejects_invalid_request_id():
    with pytest.raises(HTTPException) as error:
        asyncio.run(api.cancel_model_query("../all", http_request()))
    assert error.value.status_code == 422
