# app.py — RealtyCheck / IntegriBot (LLM7 compatible, crash-proof)

import os, json, re
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from openai import OpenAI

print(">>> RealtyCheck AI Chatbot loaded successfully (LIVE FILE) <<<")

# -----------------------------
# Role hints for RealtyCheck
# -----------------------------
ROLE_HINTS = {
    "Supervisor": "oversees on-site teams, vendor staff, and contractors. Integrity dilemmas often involve safety, attendance, or material misuse reporting.",
    "Sr. Supervisor": "supervises multiple teams and ensures compliance with on-site SOPs—dilemmas can include quality checks, vendor favoritism, or reporting underperformance.",
    "Officer": "handles documentation, data entry, and coordination. Integrity issues may include falsifying records, overlooking policy steps, or miscommunication between departments.",
    "Sr. Officer": "responsible for quality control, approvals, and maintaining accuracy in reports. Integrity dilemmas may include pressure to adjust data or skip verifications.",
    "Trainee Executive": "a new entrant learning processes—dilemmas may include reporting errors, ownership, or peer influence to take shortcuts.",
    "Assistant Executive": "supports daily operations and vendor follow-ups—dilemmas can involve accepting small favors or overlooking discrepancies.",
    "Deputy Executive": "works across teams to track deliverables and approvals—dilemmas could involve escalation of mistakes or miscommunication.",
    "Executive": "executes operational tasks and ensures compliance—dilemmas often include deadline pressure versus policy adherence.",
    "Assistant Senior Executive": "handles sensitive tasks like procurement tracking and data accuracy—dilemmas may include loyalty versus honesty conflicts.",
    "Deputy Senior Executive": "manages cross-functional tasks with autonomy—dilemmas often include confronting unethical practices or speaking up.",
    "Senior Executive": "leads smaller teams and coordinates reporting—dilemmas might involve accountability and transparency under performance stress.",
    "Management Trainee": "rotates across departments to learn—dilemmas often test courage to question irregularities or take responsibility for mistakes.",
    "Assistant Manager": "leads small teams and ensures delivery—dilemmas include favoritism, transparency, and fair recognition of efforts.",
    "Deputy Manager": "balances team goals and compliance—dilemmas could involve manipulating reports or covering errors.",
    "Manager": "ensures performance and team ethics—dilemmas may include owning up to project issues or ensuring unbiased decisions.",
    "Assistant Senior Manager": "bridges management and leadership—dilemmas might involve prioritizing integrity over delivery pressure.",
    "Deputy Senior Manager": "responsible for enforcing ethics and reviewing team behavior—dilemmas can include standing against manipulation.",
    "Senior Manager": "guides multiple teams and sets culture—dilemmas might involve handling conflicts, transparency in escalations, and fair practices.",
    "Assistant General Manager": "oversees multiple projects and ensures adherence to company policies—dilemmas may include vendor ethics or internal pressure.",
    "Deputy General Manager": "monitors large-scale operations—dilemmas often include whistleblowing, compliance, or risk-taking ethics.",
    "General Manager": "leads strategic operations and sets tone for governance—dilemmas may include disclosure of financial irregularities or tough ethical calls.",
    "Senior General Manager": "maintains organizational integrity and policy adherence—dilemmas may involve courage to report senior misconduct or resist external influence.",
    "Assistant Vice President": "drives business units and influences culture—dilemmas often include loyalty versus ethics in decision-making.",
    "Deputy Vice President": "handles cross-functional leadership and ensures compliance—dilemmas may include strategic transparency or ethical negotiations.",
    "Vice President": "represents leadership in execution—dilemmas may involve tough client decisions or handling conflict of interest.",
    "Sr. Vice President": "sets tone for ethical leadership—dilemmas often involve accountability for subordinate actions or integrity in reporting to the board.",
    "Executive Vice President": "oversees entire divisions—dilemmas could include reporting governance issues or transparency under stakeholder pressure.",
    "Sr. Executive Vice President": "leads strategic governance—dilemmas involve truth-telling to the board, ethical compliance, or integrity in financial disclosures.",
    "COO": "balances operational excellence with ethics—dilemmas can include whistleblowing, transparent crisis management, or resisting undue pressure.",
    "President": "responsible for overall integrity culture—dilemmas may include policy enforcement and owning organization-wide decisions.",
    "CEO": "sets ethical vision—dilemmas might involve transparency in corporate governance or addressing compliance failures openly.",
    "Director": "provides oversight at the board level—dilemmas may include conflicts of interest, disclosure of violations, and ensuring governance integrity."
}

from datetime import datetime

SCORE_FILE = "scores.jsonl"


# --- env & client ---
load_dotenv()
print("✅ .env loaded | OPENAI_API_KEY starts with:", (os.getenv("OPENAI_API_KEY") or "")[:8])

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "unused")
MODEL = os.getenv("OPENAI_MODEL", "mistral-small-3.1-24b-instruct-2503")  # LLM7 default
BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.llm7.io/v1")
STORE_LOGS = os.getenv("STORE_LOGS", "false").lower() == "true"
LOG_FILE = "logs.jsonl"

app = Flask(__name__)

def openai_client():
    """
    OpenAI-compatible client (LLM7 via base_url).
    Treat placeholder keys as 'no key' → offline mode.
    """
    if not OPENAI_API_KEY or OPENAI_API_KEY.strip().lower() in {"unused", "none", "your_key_here"}:
        return None
    return OpenAI(base_url=BASE_URL, api_key=OPENAI_API_KEY)

# ---------- prompts (Mistral-optimized) ----------
PROMPT_SCENARIO_SYSTEM = (
    "You are IntegriBot hosting RealtyCheck. Generate realistic, role-tailored, **non-repetitive** integrity dilemmas "
    "in a real-estate/corporate context using SJT (situational judgement test) style. "
    "Vary stakeholders, constraints (time/cost/legal), and ethical tensions (gift/COI/safety/data/whistleblowing). "
    "Write in 60–110 words, professional tone, no real names or confidential data. "
    "Prefer Indian corporate nuance when relevant."
)

# role_text will be “<Role>. <Hint>”
PROMPT_SCENARIO_USER = (
    "RANDOMIZER: {rand_tag}\n"
    "Role: {role_text}\n"
    "Using the attached Integrity Corpus (if any), propose **3 distinct** dilemmas of **different patterns**.\n"
    "Respond as JSON ONLY (no markdown fences):\n"
    "{{\"candidates\":[{{\"scenario\":\"<60-110 words>\",\"difficulty\":\"easy|medium|hard\"}},"
    "{{\"scenario\":\"...\",\"difficulty\":\"...\"}},{{\"scenario\":\"...\",\"difficulty\":\"...\"}}]}}"
)

PROMPT_EVAL_SYSTEM = (
    "You are IntegriBot, the evaluator for RealtyCheck. "
    "Evaluate the participant's response to the integrity scenario strictly on: honesty, transparency, fairness, "
    "compliance with policy/law, accountability (owning mistakes, documenting), and courage (escalation/refusing undue pressure). "
    "Reward actions like reporting issues, refusing gifts/bribes, documenting decisions, correcting errors, "
    "seeking guidance, and escalating appropriately. Be encouraging but clear."
    "Return JSON ONLY."
)

PROMPT_EVAL_USER = (
    "Role: {role}\n"
    "Scenario: {scenario}\n"
    "Participant response: {response}\n"
    "If the response is empty or evades the issue, give a low score.\n"
    "Output JSON EXACTLY:\n"
    '{{"score":<integer 0-10>,"feedback":"1-3 short sentences","criteria":"short bullet-like string"}}'
)

# ---------- utils ----------

from collections import deque
import random
import time

# RAM-only recent picks to reduce immediate repeats (not written to disk)
RECENT = { "default": deque(maxlen=30) }

def load_corpus_text(path="integrity_corpus.md", max_chars=12000):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                txt = f.read()[:max_chars]
            return txt
        except Exception:
            return ""
    return ""


def save_score(entry: dict):
    os.makedirs(os.path.dirname(SCORE_FILE) or ".", exist_ok=True)
    with open(SCORE_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


import re

def extract_json(s: str) -> str:
    # pulls out the first {...} block even if wrapped in ```json ... ```
    m = re.search(r"\{.*\}", s, flags=re.S)
    return m.group(0) if m else s

def try_parse_json(s: str) -> dict:
    try:
        return json.loads(extract_json(s))
    except Exception:
        return {}


# ---------- AI: scenario ----------

def ai_generate_scenario(role: str):
    client = openai_client()

    def _fallback():
        text = (
            f"As a {role}, a vendor hints at a personal favor to fast-track an approval. Your manager is under deadline "
            "pressure. Reporting it could slow work, but ignoring it risks violating anti-bribery policy. What would you do and why?"
        )
        return {"scenario": text, "difficulty": "medium"}

    if client is None:
        return _fallback()

    try:
        # Build messages with optional corpus
        hint = ROLE_HINTS.get(role, "")
        role_text = f"{role}. {hint}" if hint else role
        rand_tag = f"{int(time.time()*1000)}-{random.randint(1000,9999)}"
        corpus = load_corpus_text()  # empty if file not present

        messages = [{"role": "system", "content": PROMPT_SCENARIO_SYSTEM}]
        if corpus:
            messages.append({"role": "system", "content": f"Integrity Corpus (internal reference):\n{corpus}"})
        messages.append({"role": "user", "content": PROMPT_SCENARIO_USER.format(role_text=role_text, rand_tag=rand_tag)})

        resp = client.chat.completions.create(
            model=MODEL,
            temperature=0.95,     # ↑ variety
            top_p=0.95,
            presence_penalty=0.4, # nudge novelty
            frequency_penalty=0.4,
            max_tokens=420,
            messages=messages,
        )
        raw = (resp.choices[0].message.content or "").strip()
        data = try_parse_json(raw)
        cands = data.get("candidates") or []

        # Pick one at random; minimal RAM-only repeat guard
        if not cands:
            return _fallback()

        # Normalize and try to avoid immediate repeats in this process only
        bucket = RECENT.setdefault(role, deque(maxlen=30))
        random.shuffle(cands)
        chosen = None
        for c in cands:
            s = (c.get("scenario") or "").strip()
            key = s.lower()[:180]
            if s and key not in bucket:
                chosen = c
                bucket.append(key)
                break
        if not chosen:
            chosen = cands[0]  # all were similar; still return something

        scenario = (chosen.get("scenario") or "").strip()
        difficulty = (chosen.get("difficulty") or "medium").strip()
        return {"scenario": scenario[:900], "difficulty": difficulty}

    except Exception as e:
        print("❌ Scenario gen error -> fallback:", repr(e))
        return _fallback()


# ---------- AI: evaluation ----------
def ai_evaluate(role: str, scenario: str, response_text: str):
    client = openai_client()

    def _heuristic():
        good = ["report","escalate","refuse","policy","compliance","transparency",
                "document","own","accountable","apologize","correct","no gift","conflict of interest"]
        bad  = ["hide","ignore","cover","bribe","kickback","lie","fake","adjust numbers","delay reporting"]
        score = 5
        t = response_text.lower()
        score += sum(1 for w in good if w in t)
        score -= sum(1 for w in bad  if w in t)
        score = max(0, min(10, score))
        feedback = ("(Offline) Choose honesty, follow policy, refuse gifts/bribes, "
                    "document actions, correct mistakes, and escalate appropriately.")
        return {"score": score, "feedback": feedback,
                "criteria": "Honesty • Transparency • Fairness • Compliance • Accountability • Courage"}

    if client is None:
        return _heuristic()

    try:
        resp = client.chat.completions.create(
            model=MODEL,
            temperature=0.2,
            max_tokens=250,
            messages=[
                {"role": "system", "content": PROMPT_EVAL_SYSTEM + " Return JSON only. Do NOT use Markdown or code fences."},
                {"role": "user", "content": PROMPT_EVAL_USER.format(
                    role=role, scenario=scenario, response=response_text
                )},
            ],
        )
        text = (resp.choices[0].message.content or "").strip()
        data = try_parse_json(text)

        score = int(data.get("score", 0))
        feedback = (data.get("feedback") or data.get("message") or text[:400]).strip()
        criteria = data.get("criteria") or "Honesty • Transparency • Fairness • Compliance • Accountability • Courage"

        return {"score": score, "feedback": feedback, "criteria": criteria}
    except Exception as e:
        print("❌ Evaluation error -> heuristic:", repr(e))
        return _heuristic()

# ---------- routes ----------

@app.get("/_llm_diag")
def _llm_diag():
    try:
        client = openai_client()
        if client is None:
            return jsonify({"online": False, "why": "no/placeholder API key"}), 200

        r = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role":"system","content":"You are a concise bot."},
                {"role":"user","content":"Return ONLY JSON: {\"ok\":true,\"model\":\"<id>\"}"}
            ],
            temperature=0
        )
        text = (r.choices[0].message.content or "").strip()
        return jsonify({"online": True, "model": MODEL, "raw": text}), 200
    except Exception as e:
        import traceback
        return jsonify({"online": False, "error": repr(e), "trace": traceback.format_exc()}), 500


@app.route("/")
def home():
    return render_template("index.html")

@app.post("/generate_scenario")
def generate_scenario():
    payload = request.get_json(force=True)
    role = (payload.get("role") or "").strip() or "Employee"
    data = ai_generate_scenario(role)
    if STORE_LOGS:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps({"event": "scenario", "role": role, "data": data}, ensure_ascii=False) + "\n")
    return jsonify(data)

@app.post("/evaluate")
def evaluate():
    payload = request.get_json(force=True)
    role = (payload.get("role") or "Employee").strip()
    scenario = (payload.get("scenario") or "").strip()
    response_text = (payload.get("response_text") or "").strip()
    data = ai_evaluate(role, scenario, response_text)
    if STORE_LOGS:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "event": "evaluate", "role": role, "scenario": scenario,
                "response": response_text, "result": data
            }, ensure_ascii=False) + "\n")
    return jsonify(data)

@app.post("/submit_score")
def submit_score():
    payload = request.get_json(force=True)
    name = (payload.get("name") or "").strip()
    role = (payload.get("role") or "").strip()
    score = int(payload.get("score") or 0)
    consent = bool(payload.get("consent") or False)

    # Only store if user gave consent and score is valid
    if consent and 0 <= score <= 10 and name and role:
        entry = {
            "name": name[:50],
            "role": role[:80],
            "score": score,
            "ts": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        }
        save_score(entry)
        return jsonify({"ok": True})
    return jsonify({"ok": False})

@app.get("/leaderboard")
def leaderboard():
    rows = []
    if os.path.exists(SCORE_FILE):
        with open(SCORE_FILE, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    rows.append(json.loads(line))
                except Exception:
                    pass
    # Sort by score desc, then newest first
    rows.sort(key=lambda r: (r.get("score", 0), r.get("ts", "")), reverse=True)
    top = rows[:10]
    return jsonify({"items": top})


if __name__ == "__main__":
    app.run(debug=True)
