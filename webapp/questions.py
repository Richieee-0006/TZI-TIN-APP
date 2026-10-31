"""Cache otázek v paměti a ověřování odpovědí na serveru (anti-spoofing)."""
import unicodedata
from typing import Dict, Any
import tzi_trener


# --- Question Caching & Anti-Spoofing Verification ---
ALL_QUESTIONS: Dict[str, Dict[str, Any]] = {}


def refresh_questions():
    global ALL_QUESTIONS
    try:
        qs = tzi_trener.load_questions(tzi_trener.ALL) + tzi_trener.load_recall()
        ALL_QUESTIONS = {str(q["id"]): q for q in qs}
    except Exception as e:
        print(f"[Warning] Failed to pre-cache questions: {e}")


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", str(s)) if unicodedata.category(c) != "Mn")


def norm_input_val(s: str) -> str:
    cleaned = "".join(c.upper() for c in str(s) if ord(c) > 32 and ord(c) != 0xA0 and c != "_")
    i = 0
    while i < len(cleaned) - 1 and cleaned[i] == "0":
        i += 1
    return cleaned[i:]


def norm_str(s: str) -> str:
    cleaned = strip_accents(str(s).lower())
    return " ".join("".join(c if c.isalnum() else " " for c in cleaned).split())


def lev1(a: str, b: str) -> bool:
    if abs(len(a) - len(b)) > 1: return False
    if len(a) == len(b): return sum(1 for x, y in zip(a, b) if x != y) == 1
    if len(a) > len(b): a, b = b, a
    for i in range(len(b)):
        if b[:i] + b[i+1:] == a: return True
    return False


def verify_answer(q: Dict[str, Any], user_answer: Any) -> bool:
    if not q or user_answer is None:
        return False
    q_type = q.get("type", "choice")
    if q_type == "choice":
        correct = set(str(k) for k in q.get("correct", []))
        if isinstance(user_answer, list):
            u_set = set(str(k) for k in user_answer)
        else:
            u_set = {str(user_answer)}
        return len(correct) > 0 and u_set == correct
    elif q_type == "input":
        raw_exp = q.get("answer", "")
        val = user_answer[0] if isinstance(user_answer, list) and user_answer else user_answer
        # Shoda buď přes norm_input_val (identická s WASM normInput včetně ořezu úvodních nul)
        # nebo fallback přes norm_str
        if norm_input_val(val) == norm_input_val(raw_exp):
            return True
        expected = norm_str(raw_exp)
        given = norm_str(val)
        return given == expected or given.replace(" ", "") == expected.replace(" ", "")
    elif q_type == "recall":
        val = user_answer[0] if isinstance(user_answer, list) and user_answer else user_answer
        given = norm_str(val)
        if not given:
            return False
        for acc in q.get("accept", []):
            exp = norm_str(acc)
            if given == exp:
                return True
            gw = given.split()
            ew = exp.split()
            if len(gw) == len(ew) and all(x == y or (len(y) > 5 and x[0] == y[0] and lev1(x, y)) for x, y in zip(gw, ew)):
                return True
        return False
    return False
