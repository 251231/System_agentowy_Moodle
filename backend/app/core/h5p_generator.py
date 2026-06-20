"""
H5P Generator – pełna wersja produkcyjna.

Generuje plik H5P na podstawie danych JSON zwróconych przez LLM.
Obsługuje typy: multichoice, dialogcard, dragtext, truefalse.
Jeżeli wybrano tylko fiszki (dialogcard) – generuje czysty H5P.Dialogcards jako mainLibrary.
Jeżeli mix lub pytania – generuje H5P.Column z zagnieżdżonymi blokami.
"""
import json
import zipfile
import re
import uuid
from pathlib import Path

def generate_h5p_quiz_json(texts, api_type, api_key, config=None):
    """
    Wywołuje LLM i zwraca listę obiektów – surowych danych dla create_h5p_archive().
    """
    if config is None:
        config = {}

    amount = config.get("h5p_amount", 5)
    types  = config.get("h5p_types", ["Quiz (ABCD)"])
    level  = config.get("h5p_level", "Mieszany (auto)")
    focus  = config.get("h5p_focus", [])
    instructions = config.get("h5p_instructions", "")

    type_instructions = []
    if "Quiz (ABCD)" in types:
        type_instructions.append(
            "- {\"type\": \"multichoice\", \"question\": \"<string>\", \"options\": [\"<A>\",\"<B>\",\"<C>\",\"<D>\"], "
            "\"correctIndex\": <0-based int>, \"feedback\": \"<string>\"}"
        )
    if "Fiszki" in types:
        type_instructions.append(
            "- {\"type\": \"dialogcard\", \"front\": \"<pojęcie/termin>\", \"back\": \"<definicja/wyjaśnienie>\"}"
        )
    if "Uzupełnianie luk" in types:
        type_instructions.append(
            "- {\"type\": \"dragtext\", \"text\": \"<zdanie z 1-2 słowami otoczonymi gwiazdkami, np. Moodle is an *LMS* system.>\"}"
        )
    if "Prawda / Fałsz" in types:
        type_instructions.append(
            "- {\"type\": \"truefalse\", \"question\": \"<string>\", \"correctAnswer\": <true|false>, "
            "\"feedback\": \"<string>\"}"
        )

    if not type_instructions:

        type_instructions.append(
            "- {\"type\": \"multichoice\", \"question\": \"<string>\", \"options\": [\"<A>\",\"<B>\",\"<C>\",\"<D>\"], "
            "\"correctIndex\": <0-based int>, \"feedback\": \"<string>\"}"
        )

    schema_prompt = "\n".join(type_instructions)
    focus_str     = ", ".join(focus) if focus else "brak"
    combined_text = "\n\n".join(texts)

    if len(combined_text) > 20000:
        combined_text = combined_text[:20000]

    prompt = (
        f"You are an experienced teacher creating educational H5P content in Polish.\n"
        f"Based on the following course content, create EXACTLY {amount} H5P learning items.\n"
        f"Difficulty: {level}\n"
        f"Thematic focus: {focus_str}\n"
        f"Additional instructions: {instructions}\n\n"
        f"IMPORTANT – you must generate items ONLY of these types (use the exact JSON format shown):\n"
        f"{schema_prompt}\n\n"
        f"Rules:\n"
        f"- Spread items evenly across the requested types.\n"
        f"- All text must be in POLISH.\n"
        f"- Return ONLY a raw JSON array (no markdown fences, no extra text).\n"
        f"- For 'multichoice' correctIndex must point to the truly correct answer.\n"
        f"- For 'dragtext' wrap exactly 1 or 2 key words per sentence with *asterisks*. DO NOT use any HTML tags like <p> in the text.\n\n"
        f"Course content:\n{combined_text}"
    )

    result_text = "[]"

    if api_type == "openai" and api_key:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key)
            resp = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.6,
            )
            result_text = resp.choices[0].message.content.strip()
            print("[H5P] OpenAI OK")
        except Exception as e:
            print(f"[H5P] OpenAI error: {e}")

    elif api_type == "gemini" and api_key:
        import time
        try:
            from google import genai
            client = genai.Client(api_key=api_key)
            gemini_models = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
            for model in gemini_models:
                for attempt in range(3):
                    try:
                        resp = client.models.generate_content(model=model, contents=prompt)
                        result_text = resp.text.strip()
                        print(f"[H5P] Gemini OK ({model})")
                        break
                    except Exception as e:
                        err = str(e)
                        if any(kw in err.upper() for kw in ["503", "UNAVAILABLE", "OVERLOADED", "RATE"]):
                            wait = 5 * (attempt + 1)
                            print(f"[H5P] Gemini {model} overloaded, retry in {wait}s... ({err[:80]})")
                            time.sleep(wait)
                        else:
                            print(f"[H5P] Gemini {model} error: {err[:120]}")
                            break
                if result_text != "[]":
                    break
            if result_text == "[]":
                print("[H5P] All Gemini models failed")
        except Exception as e:
            print(f"[H5P] Gemini init error: {e}")

    elif api_type == "openrouter" and api_key:
        try:
            from openai import OpenAI
            client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
            free_models = [
                "google/gemini-2.5-flash:free",
                "openai/gpt-4o-mini",
                "openai/gpt-oss-20b:free",
            ]
            for model in free_models:
                try:
                    resp = client.chat.completions.create(
                        model=model,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.6,
                        extra_headers={
                            "HTTP-Referer": "https://moodle.agent.local",
                            "X-Title": "Moodle AI Agent",
                        },
                    )
                    if resp.choices and resp.choices[0].message.content:
                        result_text = resp.choices[0].message.content.strip()
                        print(f"[H5P] OpenRouter OK ({model})")
                        break
                except Exception as e:
                    print(f"[H5P] OpenRouter fail ({model}): {str(e)[:120]}")
        except Exception as e:
            print(f"[H5P] OpenRouter init error: {e}")

    else:

        print("[H5P] No API key – returning mock data")
        return _mock_data(types)

    result_text = re.sub(r"^```(?:json)?", "", result_text, flags=re.MULTILINE).strip()
    result_text = re.sub(r"```$", "", result_text, flags=re.MULTILINE).strip()

    try:
        items = json.loads(result_text)
        if not isinstance(items, list):
            print("[H5P] LLM returned non-list JSON – falling back to mock")
            return _mock_data(types)
        print(f"[H5P] Parsed {len(items)} items from LLM")
        return items
    except json.JSONDecodeError as e:
        print(f"[H5P] JSON parse error: {e}\nRaw response:\n{result_text[:500]}")
        return []

def _mock_data(types):
    items = []
    if "Quiz (ABCD)" in types or not types:
        items.append({
            "type": "multichoice",
            "question": "Przykładowe pytanie testowe (tryb bez API)?",
            "options": ["Odpowiedź A", "Odpowiedź B", "Odpowiedź C", "Odpowiedź D"],
            "correctIndex": 0,
            "tip": "To podpowiedź demonstracyjna.",
            "feedback": "Odpowiedź A jest poprawna w trybie demonstracyjnym.",
        })
    if "Fiszki" in types:
        items.append({"type": "dialogcard", "front": "Fiszka demonstracyjna", "back": "Definicja demonstracyjna"})
    if "Uzupełnianie luk" in types:
        items.append({"type": "dragtext", "text": "Moodle jest przykładowym *systemem LMS*."})
    if "Prawda / Fałsz" in types:
        items.append({"type": "truefalse", "question": "Ziemia krąży wokół Słońca.", "correctAnswer": True,
                      "tip": "Wskazówka: astronomia.", "feedback": "Tak, Ziemia obraca się wokół Słońca."})
    return items

def create_h5p_archive(items, output_path: str, title: str = "Treści H5P"):
    """
    Buduje plik .h5p z listy itemów zwróconych przez LLM.

    Strategia:
    - Tylko dialogcards → mainLibrary = H5P.Dialogcards (najprostszy, najbardziej kompatybilny)
    - Tylko jeden typ quiz/dragtext/truefalse → mainLibrary = H5P.QuestionSet
    - Mieszane → mainLibrary = H5P.Column
    """
    dialogs   = []
    qs_items  = []
    drag_items = []

    for item in items:
        t = item.get("type", "multichoice")

        if t == "dialogcard":
            dialogs.append({
                "text":   f"<p>{item.get('front', '')}</p>",
                "answer": f"<p>{item.get('back', '')}</p>",
            })

        elif t == "dragtext":
            raw_text = item.get("text", "")

            raw_text = re.sub(r"<[^>]+>", " ", raw_text).strip()

            if not raw_text or not re.search(r"\*[^*]+\*", raw_text):
                print(f"[H5P] Skipping invalid dragtext (no asterisked words): {raw_text[:60]!r}")
                continue
            drag_items.append({
                "library": "H5P.DragText 1.10",
                "subContentId": str(uuid.uuid4()),
                "metadata": {"title": "Uzupełnianie luk", "license": "U"},
                "params": {
                    "taskDescription": "<p>Przeciągnij słowa w odpowiednie miejsca.</p>",
                    "textField": f"<p>{raw_text}</p>",
                    "behaviour": {
                        "enableRetry": True,
                        "enableSolutionsButton": True,
                        "instantFeedback": False,
                    },
                    "checkAnswer": "Sprawdź",
                    "tryAgain": "Spróbuj ponownie",
                    "showSolution": "Pokaż rozwiązanie",
                },
            })

        elif t == "truefalse":
            correct_ans = item.get("correctAnswer", True)
            is_true = correct_ans if isinstance(correct_ans, bool) else str(correct_ans).lower() == "true"
            feedback_text = item.get('feedback', '')
            qs_items.append({
                "library": "H5P.TrueFalse 1.8",
                "subContentId": str(uuid.uuid4()),
                "metadata": {"title": "Prawda / Fałsz", "license": "U"},
                "params": {
                    "question": f"<p>{item.get('question', '')}</p>",
                    "correct": "true" if is_true else "false",
                    "behaviour": {"enableRetry": True, "enableSolutionsButton": True},
                    "feedbackText": f"<p>{feedback_text}</p>" if feedback_text else "",
                    "l10n": {"trueText": "Prawda", "falseText": "Fałsz"},
                },
            })

        else:

            if not item.get("question", "").strip():
                print("[H5P] Skipping multichoice with empty question")
                continue
            options = item.get("options", [])
            if len(options) < 2:
                print(f"[H5P] Skipping multichoice with fewer than 2 options: {item.get('question','')[:50]}")
                continue
            answers = []
            feedback_text = item.get('feedback', '')
            for idx, opt in enumerate(options):
                is_correct = (idx == item.get("correctIndex", 0))
                answers.append({
                    "text": f"<div>{opt}</div>",
                    "correct": is_correct,
                    "tipsAndFeedback": {
                        "tip": "",
                        "chosenFeedback": (
                            f"<div>✓ Poprawnie! {feedback_text}</div>" if is_correct
                            else f"<div>✗ Niepoprawnie. {feedback_text}</div>"
                        ),
                        "notChosenFeedback": "",
                    },
                })
            qs_items.append({
                "library": "H5P.MultiChoice 1.16",
                "subContentId": str(uuid.uuid4()),
                "metadata": {"title": "Pytanie wielokrotnego wyboru", "license": "U"},
                "params": {
                    "question": f"<p>{item.get('question', '')}</p>",
                    "answers": answers,
                    "behaviour": {
                        "enableRetry": True,
                        "enableSolutionsButton": True,
                        "singlePoint": False,
                        "randomAnswers": True,
                        "showSolutionsRequiresInput": True,
                        "type": "auto",
                        "confirmCheckDialog": False,
                        "confirmRetryDialog": False,
                        "autoCheck": False,
                        "passPercentage": 100,
                        "showScorePoint": True,
                    },
                    "UI": {
                        "checkAnswerButton": "Sprawdź",
                        "showSolutionButton": "Pokaż rozwiązanie",
                        "tryAgainButton": "Spróbuj ponownie",
                        "tipsLabel": "Podpowiedź",
                        "scoreBarLabel": "Otrzymałeś :num punktów z :total możliwych",
                        "tipAvailable": "Dostępna podpowiedź",
                        "feedbackAvailable": "Dostępna informacja zwrotna",
                        "readFeedback": "Przeczytaj informację zwrotną",
                        "wrongAnswer": "Błędna odpowiedź",
                        "correctAnswer": "Prawidłowa odpowiedź",
                        "shouldCheck": "Należy zaznaczyć",
                        "shouldNotCheck": "Nie należy zaznaczać",
                        "noHint": "Brak podpowiedzi",
                        "a11yCheck": "Sprawdź odpowiedzi. Zostaną zliczone punkty.",
                    },
                    "media": {"disableImageZooming": False},
                },
            })

    only_dialogs   = bool(dialogs) and not qs_items and not drag_items
    only_qs        = bool(qs_items) and not dialogs and not drag_items
    only_drag      = bool(drag_items) and not dialogs and not qs_items
    mixed          = not (only_dialogs or only_qs or only_drag)

    if only_dialogs:
        _build_dialogcards(dialogs, output_path, title)
    elif only_qs:

        _build_quiz_as_column(qs_items, output_path, title)
    elif only_drag:

        _build_column([("drag", d) for d in drag_items], output_path, title)
    else:
        _build_column_mixed(dialogs, qs_items, drag_items, output_path, title)

def _build_quiz_as_column(qs_items, output_path, title):
    """Pakuje pytania quizu bezpośrednio w H5P.Column.

    Każde pytanie (MultiChoice / TrueFalse) jest osobnym elementem kolumny.
    Brak przycisków nawigacji QuestionSet (które mają problemy z CSS w Moodle).
    Każde pytanie ma własny przycisk 'Sprawdź'.
    """
    column_items = []
    for q in qs_items:
        column_items.append({
            "content": {
                "library": q["library"],
                "subContentId": q["subContentId"],
                "metadata": q.get("metadata", {"title": "Pytanie", "license": "U"}),
                "params": q["params"],
            },
            "useSeparator": "auto",
        })

    content_json = {"content": column_items}

    h5p_json = {
        "title": title,
        "language": "pl",
        "mainLibrary": "H5P.Column",
        "embedTypes": ["div"],
        "license": "U",
        "preloadedDependencies": [
            {"machineName": "H5P.Column",      "majorVersion": 1, "minorVersion": 15},
            {"machineName": "H5P.MultiChoice", "majorVersion": 1, "minorVersion": 16},
            {"machineName": "H5P.TrueFalse",   "majorVersion": 1, "minorVersion": 8},
            {"machineName": "FontAwesome",      "majorVersion": 4, "minorVersion": 5},
            {"machineName": "H5P.JoubelUI",    "majorVersion": 1, "minorVersion": 3},
        ],
    }
    _write_archive(output_path, h5p_json, content_json)

def _qs_texts():
    return {
        "prevButton": "◀ Poprzednie",
        "nextButton": "Następne ▶",
        "finishButton": "Zakończ quiz",
        "submitButton": "Zatwierdź",
        "textualProgress": "Pytanie @current z @total",
        "jumpToQuestion": "Pytanie %d",
        "questionLabel": "Pytanie",
        "readSpeakerProgress": "Pytanie @current z @total",
        "unansweredText": "Bez odpowiedzi",
        "answeredText": "Udzielono odpowiedzi",
        "emptyText": "Puste",
    }

def _qs_end():
    return {
        "showResultPage": True,
        "showSolutionButton": True,
        "showRetryButton": True,
        "noResultMessage": "Zakończono quiz",
        "message": "Twój wynik to @score z @total punktów",
        "scoreBarLabel": "Zdobyłeś :num na :total punktów",
        "actionString": "Przejdź dalej",
        "solutionButtonText": "Pokaż rozwiązania",
        "retryButtonText": "Spróbuj ponownie",
        "requiresInput": "Odpowiedz na pytania zanim sprawdzisz wynik.",
    }

def _build_dialogcards(dialogs, output_path, title):
    content_json = {
        "dialogs": dialogs,
        "title": title,
        "behaviour": {
            "enableRetry": True,
            "disableBackwardsNavigation": False,
            "scaleTextNotCard": False,
            "randomCards": True,
        },
        "l10n": {
            "cardFront": "Przód karty",
            "cardBack": "Tył karty",
            "next": "Następna",
            "prev": "Poprzednia",
            "previous": "Poprzednia",
            "retry": "Powtórz",
            "answer": "Pokaż odpowiedź",
            "goodButton": "Wiedziałem",
            "notGoodButton": "Nie wiedziałem",
            "round": "Runda @round",
            "cardsLeft": "Pozostało kart: @number",
            "nextRound": "Przejdź do rundy @round",
            "showSummary": "Pokaż podsumowanie",
            "summaryHeader": "Podsumowanie",
            "summaryCardsRight": "Poprawnie oznaczone karty:",
            "summaryCardsWrong": "Niepoprawnie oznaczone karty:",
            "summaryCardsNotShown": "Pozostałe karty:",
            "summaryOverallScore": "Ogólny wynik",
            "summaryCardsCompleted": "Ukończone karty:",
            "summaryCompletedRounds": "Ukończone rundy:",
            "summaryAllDone": "Brawo! Wszystkie karty zaliczone!",
        },
        "mode": "normal",
    }

    h5p_json = {
        "title": title,
        "language": "pl",
        "mainLibrary": "H5P.Dialogcards",
        "embedTypes": ["div"],
        "license": "U",
        "preloadedDependencies": [
            {"machineName": "H5P.Dialogcards", "majorVersion": 1, "minorVersion": 9},
            {"machineName": "FontAwesome",       "majorVersion": 4, "minorVersion": 5},
        ],
    }
    _write_archive(output_path, h5p_json, content_json)

def _build_questionset(qs_items, output_path, title):
    content_json = {
        "introPage": {
            "showIntroPage": False,
            "startButtonText": "Rozpocznij",
            "introduction": f"<p>{title}</p>",
        },
        "progressType": "textual",
        "passPercentage": 50,
        "questions": qs_items,
        "disableBackwardsNavigation": False,
        "randomQuestions": False,
        "endGame": _qs_end(),
        "override": {"checkButton": True},
        "texts": _qs_texts(),
    }

    h5p_json = {
        "title": title,
        "language": "pl",
        "mainLibrary": "H5P.QuestionSet",
        "embedTypes": ["div"],
        "license": "U",
        "preloadedDependencies": [
            {"machineName": "H5P.QuestionSet",  "majorVersion": 1, "minorVersion": 20},
            {"machineName": "H5P.MultiChoice",  "majorVersion": 1, "minorVersion": 16},
            {"machineName": "H5P.TrueFalse",    "majorVersion": 1, "minorVersion": 8},
            {"machineName": "FontAwesome",       "majorVersion": 4, "minorVersion": 5},
            {"machineName": "H5P.JoubelUI",     "majorVersion": 1, "minorVersion": 3},
        ],
    }
    _write_archive(output_path, h5p_json, content_json)

def _build_column_mixed(dialogs, qs_items, drag_items, output_path, title):
    """Pakuje mieszane typy w H5P.Column."""
    column_items = []

    if dialogs:
        column_items.append({
            "content": {
                "library": "H5P.Dialogcards 1.9",
                "subContentId": str(uuid.uuid4()),
                "metadata": {"title": "Fiszki", "license": "U"},
                "params": {
                    "dialogs": dialogs,
                    "title": "Fiszki edukacyjne",
                    "mode": "normal",
                    "behaviour": {
                        "enableRetry": True,
                        "disableBackwardsNavigation": False,
                        "scaleTextNotCard": False,
                        "randomCards": True,
                    },
                },
            },
            "useSeparator": "auto",
        })

    if qs_items:

        for q in qs_items:
            column_items.append({
                "content": {
                    "library": q["library"],
                    "subContentId": q["subContentId"],
                    "metadata": q.get("metadata", {"title": "Pytanie", "license": "U"}),
                    "params": q["params"],
                },
                "useSeparator": "auto",
            })

    for drag in drag_items:
        column_items.append({
            "content": {
                "library": drag["library"],
                "subContentId": drag["subContentId"],
                "metadata": drag.get("metadata", {"title": "Uzupełnianie luk", "license": "U"}),
                "params": drag["params"],
            },
            "useSeparator": "auto",
        })

    content_json = {"content": column_items}

    h5p_json = {
        "title": title,
        "language": "pl",
        "mainLibrary": "H5P.Column",
        "embedTypes": ["div"],
        "license": "U",
        "preloadedDependencies": [
            {"machineName": "H5P.Column",       "majorVersion": 1, "minorVersion": 15},
            {"machineName": "H5P.Dialogcards",  "majorVersion": 1, "minorVersion": 9},
            {"machineName": "H5P.QuestionSet",  "majorVersion": 1, "minorVersion": 20},
            {"machineName": "H5P.MultiChoice",  "majorVersion": 1, "minorVersion": 16},
            {"machineName": "H5P.TrueFalse",    "majorVersion": 1, "minorVersion": 8},
            {"machineName": "H5P.DragText",     "majorVersion": 1, "minorVersion": 10},
            {"machineName": "FontAwesome",       "majorVersion": 4, "minorVersion": 5},
            {"machineName": "H5P.JoubelUI",     "majorVersion": 1, "minorVersion": 3},
        ],
    }
    _write_archive(output_path, h5p_json, content_json)

def _build_column(drag_list, output_path, title):
    """Tylko DragText – pakujemy w Column."""
    column_items = []
    for _, drag in drag_list:
        column_items.append({
            "content": {
                "library": drag["library"],
                "subContentId": drag["subContentId"],
                "metadata": drag.get("metadata", {"title": "Uzupełnianie luk", "license": "U"}),
                "params": drag["params"],
            },
            "useSeparator": "auto",
        })

    content_json = {"content": column_items}

    h5p_json = {
        "title": title,
        "language": "pl",
        "mainLibrary": "H5P.Column",
        "embedTypes": ["div"],
        "license": "U",
        "preloadedDependencies": [
            {"machineName": "H5P.Column",   "majorVersion": 1, "minorVersion": 15},
            {"machineName": "H5P.DragText", "majorVersion": 1, "minorVersion": 10},
            {"machineName": "FontAwesome",   "majorVersion": 4, "minorVersion": 5},
        ],
    }
    _write_archive(output_path, h5p_json, content_json)

def _write_archive(output_path, h5p_json, content_json):
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        zipf.writestr("h5p.json",              json.dumps(h5p_json,     ensure_ascii=False, indent=2))
        zipf.writestr("content/content.json",  json.dumps(content_json, ensure_ascii=False, indent=2))
    print(f"[H5P] Archive written -> {output_path}")
