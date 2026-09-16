# MODULE: Promotion AI Guide — optional OpenAI-first / Groq-fallback assistance for student imports and promotion explanations

import json
import os
import re
from dotenv import load_dotenv

load_dotenv()

CANONICAL_FIELDS = ["Admission_number", "Last_name", "First_name", "Other_names", "Phone", "Sex", "Class", "Class_category"]


def clean(value): return str(value or "").strip()


def _json_object(raw):
    raw = clean(raw).replace("```json", "").replace("```", "")
    if not raw: return {}
    try: return json.loads(raw)
    except Exception: pass
    match = re.search(r"\{[\s\S]*\}", raw)
    if not match: return {}
    try: return json.loads(match.group(0))
    except Exception: return {}


def _openai_client():
    key = clean(os.getenv("OPENAI_API_KEY"))
    if not key: return None
    try:
        from openai import OpenAI
        return OpenAI(api_key=key)
    except Exception: return None


def _groq_clients():
    try: from groq import Groq
    except Exception: return []
    clients = []
    for name in ["GROQ_API_KEY", "GROQ_API_KEY2", "GROQ_API_KEY3", "GROQ_API_KEY4", "GROQ_API_KEY5"]:
        key = clean(os.getenv(name))
        if key:
            try: clients.append((name, Groq(api_key=key)))
            except Exception: pass
    return clients


def _call_json(system_prompt, user_prompt, max_tokens=1800):
    errors = []
    openai_client = _openai_client()
    if openai_client:
        model = clean(os.getenv("OPENAI_MODEL_SOLVER")) or "gpt-5.4"
        try:
            response = openai_client.chat.completions.create(model=model, temperature=0, response_format={"type":"json_object"}, messages=[{"role":"system","content":system_prompt},{"role":"user","content":user_prompt}])
            data = _json_object(response.choices[0].message.content)
            if data: return data, {"provider":"OpenAI", "model":model, "fallback":False}
        except Exception as error: errors.append(f"OpenAI: {error}")
    model = clean(os.getenv("GROQ_MODEL")) or "openai/gpt-oss-120b"
    for key_name, client in _groq_clients():
        try:
            response = client.chat.completions.create(model=model, temperature=0, messages=[{"role":"system","content":system_prompt},{"role":"user","content":user_prompt}], max_tokens=max_tokens, response_format={"type":"json_object"})
            data = _json_object(response.choices[0].message.content)
            if data: return data, {"provider":"Groq", "model":model, "fallback":True, "key_slot":key_name}
        except Exception as error: errors.append(f"{key_name}: {error}")
    return {}, {"provider":"Rules only", "model":"", "fallback":False, "errors":errors[-3:]}


def ai_status():
    return {"openai_configured": bool(clean(os.getenv("OPENAI_API_KEY"))), "groq_configured": bool(_groq_clients()), "openai_model": clean(os.getenv("OPENAI_MODEL_SOLVER")) or "gpt-5.4", "groq_model": clean(os.getenv("GROQ_MODEL")) or "openai/gpt-oss-120b"}


def map_student_headers(headers, sample_rows=None):
    headers = [clean(item) for item in headers if clean(item)]
    if not headers: return {"mapping":{}, "provider":"Rules only", "note":"No source headers were available for AI mapping."}
    system_prompt = """You assist a school student-database import tool. Map source column headers to the exact canonical EMIS fields. Return JSON only. Canonical fields: Admission_number, Last_name, First_name, Other_names, Phone, Sex, Class, Class_category. Do not invent columns. Do not infer a student's sex/gender from their name. Do not alter student values. A source column may map to at most one canonical field. Return {\"mapping\": {\"Canonical\": \"Source Header\"}, \"note\": \"short explanation\"}."""
    payload = {"source_headers":headers, "sample_rows":(sample_rows or [])[:5], "rules":["Last_name and First_name are required for import", "Sex must be explicit or later assigned by an administrator", "Class/Class_category may be assigned by an administrator when absent"]}
    data, meta = _call_json(system_prompt, json.dumps(payload, ensure_ascii=False))
    mapping = data.get("mapping") if isinstance(data.get("mapping"), dict) else {}
    valid = {}
    for canonical, source in mapping.items():
        if canonical in CANONICAL_FIELDS and clean(source) in headers and clean(source) not in valid.values(): valid[canonical] = clean(source)
    return {"mapping":valid, "provider":meta.get("provider","Rules only"), "model":meta.get("model",""), "note":clean(data.get("note")) or "AI mapping completed."}


def parse_unstructured_student_text(text):
    text = clean(text)
    if not text: return {"rows":[], "provider":"Rules only", "note":"No text was available for AI parsing."}
    text = text[:70000]
    system_prompt = """Extract student records from messy school text into JSON. Return JSON only as {\"rows\":[...],\"note\":\"...\"}. Each row may contain only: Admission_number, Last_name, First_name, Other_names, Phone, Sex, Class, Class_category. IMPORTANT: never infer Sex from a person's name; leave Sex blank unless Male/Female/M/F is explicitly written. Never guess missing class or admission numbers. Preserve explicit phone text. Last_name and First_name should only be filled when supported by the source text."""
    data, meta = _call_json(system_prompt, text, max_tokens=5000)
    rows = data.get("rows") if isinstance(data.get("rows"), list) else []
    cleaned_rows = []
    for row in rows[:2000]:
        if not isinstance(row, dict): continue
        cleaned_rows.append({field:clean(row.get(field)) for field in CANONICAL_FIELDS})
    return {"rows":cleaned_rows, "provider":meta.get("provider","Rules only"), "model":meta.get("model",""), "note":clean(data.get("note")) or "AI text extraction completed."}


def explain_promotion_guard(context):
    system_prompt = """You are an EMIS promotion assistant. Explain an already-computed deterministic promotion warning in simple school-admin language. You do NOT decide whether students may be promoted and must never override the supplied path. Keep the response under 90 words. Return JSON only: {\"guidance\":\"...\"}."""
    data, meta = _call_json(system_prompt, json.dumps(context, ensure_ascii=False), max_tokens=300)
    return {"guidance":clean(data.get("guidance")), "provider":meta.get("provider","Rules only"), "model":meta.get("model","")}
