import os
import re
import time
from flask import Flask, request, Response
from google import genai

app = Flask(__name__)

MODELS_TO_TRY = [
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-3.7-flash",
    "gemini-3.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
]

PAIR_TO_LETTER = {
    "01": "א",
    "02": "ב",
    "03": "ג",
    "04": "ד",
    "05": "ה",
    "06": "ו",
    "07": "ז",
    "08": "ח",
    "09": "ט",
    "10": "י",
    "11": "כ",
    "12": "ל",
    "13": "מ",
    "14": "נ",
    "15": "ס",
    "16": "ע",
    "17": "פ",
    "18": "צ",
    "19": "ק",
    "20": "ר",
    "21": "ש",
    "22": "ת",
    "00": " ",
}


def decode_number_pairs(digits: str) -> str:
    """מתרגם מחרוזת ספרות בזוגות (01-22, 00=רווח) לטקסט בעברית."""
    only_digits = re.sub(r"\D", "", digits or "")
    if not only_digits:
        return ""

    chars = []
    i = 0
    while i < len(only_digits):
        if i + 1 < len(only_digits):
            pair = only_digits[i : i + 2]
            if pair in PAIR_TO_LETTER:
                chars.append(PAIR_TO_LETTER[pair])
                i += 2
                continue
        # אם נשארה ספרה בודדת או זוג לא מוכר – שומרים את הספרה
        chars.append(only_digits[i])
        i += 1

    return re.sub(r"\s+", " ", "".join(chars)).strip()


def clean_for_yemot(text: str, max_len: int = 240) -> str:
    """מנקה תווים שעלולים לשבור פקודת read בימות המשיח."""
    cleaned = re.sub(r"[^0-9א-תa-zA-Z\s]", " ", text or "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:max_len].strip()


def ask_gemini(decoded_text: str, raw_digits: str) -> str:
    """שולח את הטקסט המתורגם ל-Gemini ומחזיר תשובה קצרה ונקייה להקראה."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("שגיאה: GEMINI_API_KEY אינו מוגדר בסביבה", flush=True)
        return "חסר מפתח גישה"

    client = genai.Client(api_key=api_key)
    prompt = (
        "ענה בעברית ברורה, פשוטה ותמציתית המתאימה להקראה בטלפון. "
        "בלי סימני פיסוק, בלי כוכביות, בלי ירידות שורה ובלי קישורים.\n"
        f"המשתמש הקליד במקשים את הקוד {raw_digits} שתורגם לטקסט: {decoded_text}. "
        "התייחס לנושא או לשאלה שהטקסט מרמז עליה ותן תשובה קצרה ומועילה."
    )

    for model_name in MODELS_TO_TRY:
        try:
            print(f"פנייה ל-{model_name}...", flush=True)
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
            )
            raw_text = (response.text or "").strip()
            print(f"תשובה גולמית מ-{model_name}: {raw_text}", flush=True)
            cleaned = clean_for_yemot(raw_text)
            if cleaned:
                return cleaned
        except Exception as e:
            err_str = repr(e)
            print(f"שגיאה ב-{model_name}: {err_str}", flush=True)
            if "503" in err_str or "UNAVAILABLE" in err_str:
                time.sleep(0.5)
            continue

    return "השרת עמוס כרגע נסה שוב"


@app.route("/yemot", methods=["GET", "POST"])
def yemot():
    params = dict(request.values)
    print("פרמטרים:", params, flush=True)

    if params.get("hangup") == "yes":
        return Response("ok", mimetype="text/plain; charset=utf-8")

    raw_input = (request.values.get("question") or "").strip()

    if not raw_input:
        reply = (
            "read=t-הקש זוגות ספרות לפי האותיות ולחץ סולמית"
            "=question,tap,7,1,30,no,no,no"
        )
        print("שולח:", reply, flush=True)
        return Response(reply, mimetype="text/plain; charset=utf-8")

    decoded = decode_number_pairs(raw_input)
    print(f"קלט גולמי: {raw_input} -> תרגום: {decoded}", flush=True)

    answer = ask_gemini(decoded or raw_input, raw_input)

    if request.values.get("hangup") == "yes":
        return Response("ok", mimetype="text/plain; charset=utf-8")

    reply = (
        f"read=t-{answer} להמשך הקש זוגות ספרות ולחץ סולמית"
        f"=question,tap,7,1,30,no,no,no"
    )
    print("שולח:", reply, flush=True)
    return Response(reply, mimetype="text/plain; charset=utf-8")


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)