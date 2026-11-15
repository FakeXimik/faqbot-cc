import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

ENDPOINT = os.environ.get("AZURE_LANGUAGE_ENDPOINT", "").rstrip("/")
KEY = os.environ.get("AZURE_LANGUAGE_KEY", "")
PROJECT = os.environ.get("CQA_PROJECT_NAME", "")
DEPLOYMENT = os.environ.get("CQA_DEPLOYMENT_NAME", "production")
THRESHOLD = float(os.environ.get("CONFIDENCE_THRESHOLD", "0.25"))

FALLBACK = ("I couldn't find an answer in the course materials. "
            "Try rephrasing your question, for example: \"What is a VNet?\"")


def ask_cqa(body):
    url = f"{ENDPOINT}/language/:query-knowledgebases"
    params = {"projectName": PROJECT, "deploymentName": DEPLOYMENT,
              "api-version": "2021-10-01"}
    headers = {"Ocp-Apim-Subscription-Key": KEY}
    r = requests.post(url, params=params, headers=headers, json=body, timeout=15)
    r.raise_for_status()
    return r.json()


@app.get("/")
def index():
    return app.send_static_file("index.html")


@app.get("/health")
def health():
    return "ok"


@app.post("/api/ask")
def api_ask():
    data = request.get_json(silent=True) or {}
    question = str(data.get("question", "")).strip()
    qna_id = data.get("qnaId")
    prev_id = data.get("previousQnaId")

    if not question and qna_id is None:
        return jsonify(error="Question is empty"), 400
    if len(question) > 500:
        return jsonify(error="Question is too long (max 500 characters)"), 400

    # Input with fewer than 2 letters/digits (e.g. '""', '???') is not a real
    # question; CQA can still fuzzy-match it, so answer with the fallback directly.
    if qna_id is None and sum(c.isalnum() for c in question) < 2:
        return jsonify(found=False, message=FALLBACK)

    body = {"top": 3, "confidenceScoreThreshold": THRESHOLD}
    if qna_id is not None:
        body["qnaId"] = int(qna_id)
    else:
        body["question"] = question
    if prev_id is not None:
        body["context"] = {"previousQnaId": int(prev_id)}

    try:
        result = ask_cqa(body)
    except requests.RequestException as e:
        app.logger.error("CQA error: %s", e)
        return jsonify(error="The answer service is temporarily unavailable"), 502

    answers = result.get("answers", [])
    best = answers[0] if answers else None
    if (not best or best.get("id", -1) < 0
            or best.get("confidenceScore", 0) < THRESHOLD):
        return jsonify(found=False, message=FALLBACK)

    prompts = sorted((best.get("dialog") or {}).get("prompts") or [],
                     key=lambda p: p.get("displayOrder", 0))
    return jsonify(
        found=True,
        answer=best["answer"],
        source=best.get("source", ""),
        score=round(best.get("confidenceScore", 0), 2),
        qnaId=best["id"],
        prompts=[{"qnaId": p["qnaId"], "text": p["displayText"]} for p in prompts],
    )
