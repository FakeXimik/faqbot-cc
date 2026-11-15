import pytest
import requests

import app as appmod


@pytest.fixture
def client():
    appmod.app.config["TESTING"] = True
    return appmod.app.test_client()


def fake_cqa(response=None, error=None, calls=None):
    """Build a stand-in for ask_cqa that records the request body."""
    def _fake(body):
        if calls is not None:
            calls.append(body)
        if error:
            raise error
        return response
    return _fake


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.data == b"ok"


def test_empty_question_rejected(client):
    r = client.post("/api/ask", json={"question": "   "})
    assert r.status_code == 400


def test_too_long_question_rejected(client):
    r = client.post("/api/ask", json={"question": "a" * 501})
    assert r.status_code == 400


def test_good_answer_with_prompts(client, monkeypatch):
    calls = []
    monkeypatch.setattr(appmod, "ask_cqa", fake_cqa(calls=calls, response={
        "answers": [{
            "id": 12,
            "answer": "Sharding splits data horizontally.",
            "confidenceScore": 0.87,
            "source": "Lecture 05",
            "dialog": {"prompts": [
                {"displayOrder": 1, "qnaId": 14, "displayText": "Second"},
                {"displayOrder": 0, "qnaId": 13, "displayText": "First"},
            ]},
        }]
    }))
    r = client.post("/api/ask", json={"question": "What is sharding?"})
    data = r.get_json()
    assert r.status_code == 200
    assert data["found"] is True
    assert data["answer"] == "Sharding splits data horizontally."
    assert data["source"] == "Lecture 05"
    assert data["qnaId"] == 12
    assert [p["text"] for p in data["prompts"]] == ["First", "Second"]  # sorted by displayOrder
    assert calls[0]["question"] == "What is sharding?"
    assert calls[0]["confidenceScoreThreshold"] == appmod.THRESHOLD


def test_low_confidence_gives_fallback(client, monkeypatch):
    monkeypatch.setattr(appmod, "ask_cqa", fake_cqa(response={
        "answers": [{"id": 5, "answer": "something", "confidenceScore": 0.02}]
    }))
    data = client.post("/api/ask", json={"question": "Weather in Tirana?"}).get_json()
    assert data["found"] is False
    assert data["message"] == appmod.FALLBACK


def test_no_match_id_minus_one_gives_fallback(client, monkeypatch):
    monkeypatch.setattr(appmod, "ask_cqa", fake_cqa(response={
        "answers": [{"id": -1, "answer": "No good match found in KB.", "confidenceScore": 0.0}]
    }))
    data = client.post("/api/ask", json={"question": "Tell me a joke"}).get_json()
    assert data["found"] is False


def test_empty_answers_gives_fallback(client, monkeypatch):
    monkeypatch.setattr(appmod, "ask_cqa", fake_cqa(response={"answers": []}))
    data = client.post("/api/ask", json={"question": "anything"}).get_json()
    assert data["found"] is False


def test_follow_up_click_sends_qna_id_and_context(client, monkeypatch):
    calls = []
    monkeypatch.setattr(appmod, "ask_cqa", fake_cqa(calls=calls, response={
        "answers": [{"id": 13, "answer": "Replication copies data.", "confidenceScore": 1.0}]
    }))
    r = client.post("/api/ask", json={"qnaId": 13, "previousQnaId": 12})
    assert r.get_json()["found"] is True
    assert calls[0]["qnaId"] == 13
    assert calls[0]["context"] == {"previousQnaId": 12}
    assert "question" not in calls[0]


def test_cqa_failure_returns_502(client, monkeypatch):
    monkeypatch.setattr(appmod, "ask_cqa",
                        fake_cqa(error=requests.ConnectionError("down")))
    r = client.post("/api/ask", json={"question": "What is VNet?"})
    assert r.status_code == 502
    assert "error" in r.get_json()
