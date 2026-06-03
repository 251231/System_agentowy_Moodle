import json
import zipfile
import re
from pathlib import Path

def generate_h5p_quiz_json(texts, api_type, api_key, config=None):
    """
    Generate H5P quiz questions using the specified LLM.
    `texts` is a list of strings extracted from the course.
    """
    if config is None:
        config = {}
        
    amount = config.get("h5p_amount", 5)
    types = config.get("h5p_types", ["Pytanie / Odpowiedź"])
    level = config.get("h5p_level", "Mieszany (auto)")
    focus = config.get("h5p_focus", [])
    instructions = config.get("h5p_instructions", "")

    types_str = ", ".join(types) if types else "dowolne"
    focus_str = ", ".join(focus) if focus else "brak"

    combined_text = "\n\n".join(texts)
    # Truncate text to avoid exceeding token limits (rough approximation)
    if len(combined_text) > 20000:
        combined_text = combined_text[:20000]

    prompt = (
        f"You are a teacher. Based on the following course content, create a multiple-choice quiz with EXACTLY {amount} questions.\n"
        f"Difficulty level: {level}\n"
        f"Question types/styles: {types_str}\n"
        f"Thematic focus: {focus_str}\n"
        f"Additional instructions: {instructions}\n\n"
        "Return ONLY a valid JSON array where each object has the following keys:\n"
        "- 'question' (string): the question text.\n"
        "- 'options' (array of strings): exactly 4 possible answers.\n"
        "- 'correctIndex' (integer): the 0-based index of the correct answer in the 'options' array.\n"
        "- 'tip' (string): an optional short tip for the question.\n"
        "- 'feedback' (string): an explanation of why the correct answer is correct.\n\n"
        "Do not wrap the response in markdown blocks. Just output raw JSON.\n\n"
        f"Course content:\n{combined_text}"
    )

    result_text = "[]"
    
    if api_type == 'openai' and api_key:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key)
            resp = client.chat.completions.create(
                model='gpt-4o',
                messages=[{'role': 'user', 'content': prompt}],
                temperature=0.7
            )
            result_text = resp.choices[0].message.content.strip()
        except Exception as e:
            print(f"[!] OpenAI H5P Generation error: {e}")

    elif api_type == 'gemini' and api_key:
        try:
            from google import genai
            client = genai.Client(api_key=api_key)
            resp = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
            result_text = resp.text.strip()
        except Exception as e:
            print(f"[!] Gemini H5P Generation error: {e}")

    elif api_type == 'openrouter' and api_key:
        try:
            from openai import OpenAI
            client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
            
            free_models = [
                "google/gemini-2.5-flash:free",
                "openrouter/free",
                "openai/gpt-oss-20b:free"
            ]
            
            for model in free_models:
                try:
                    resp = client.chat.completions.create(
                        model=model,
                        messages=[{'role': 'user', 'content': prompt}],
                        temperature=0.7,
                        extra_headers={"HTTP-Referer": "https://moodle.agent.local", "X-Title": "Moodle Translator Agent"}
                    )
                    if resp.choices and resp.choices[0].message.content:
                        result_text = resp.choices[0].message.content.strip()
                        print(f"  [✓] OpenRouter H5P OK ({model})")
                        break
                except Exception as e:
                    print(f"  [!] OpenRouter H5P fail ({model}): {str(e)[:100]}")
                    continue
        except Exception as e:
            print(f"[!] OpenRouter H5P Generation error: {e}")
    else:
        # Mock / Fallback
        return [
            {
                "question": "Przykładowe pytanie wygenerowane (brak klucza API/AI)?",
                "options": ["Odpowiedź A", "Odpowiedź B", "Odpowiedź C", "Odpowiedź D"],
                "correctIndex": 0,
                "tip": "To jest podpowiedź mockowa.",
                "feedback": "Odpowiedź A jest prawidłowa, ponieważ to mock."
            }
        ]

    # Clean up markdown JSON wrappers if LLM still added them
    if result_text.startswith("```json"):
        result_text = result_text[7:]
    if result_text.startswith("```"):
        result_text = result_text[3:]
    if result_text.endswith("```"):
        result_text = result_text[:-3]

    try:
        questions = json.loads(result_text.strip())
        if not isinstance(questions, list):
            questions = []
        return questions
    except json.JSONDecodeError as e:
        print(f"[!] Failed to parse H5P JSON: {e}")
        return []

def create_h5p_archive(questions, output_path: str, title="Wygenerowany Quiz H5P"):
    """
    Create a .h5p ZIP archive containing h5p.json and content/content.json
    for a Question Set.
    """
    # Build content.json for H5P.QuestionSet
    h5p_questions = []
    for q in questions:
        answers = []
        for idx, opt in enumerate(q.get("options", [])):
            is_correct = (idx == q.get("correctIndex", 0))
            answers.append({
                "text": f"<div>{opt}</div>",
                "correct": is_correct,
                "tipsAndFeedback": {
                    "tip": q.get("tip", "") if is_correct else "",
                    "chosenFeedback": f"<div>{q.get('feedback', '')}</div>" if is_correct else f"<div>Niepoprawnie. {q.get('feedback', '')}</div>",
                    "notChosenFeedback": ""
                }
            })
            
        h5p_questions.append({
            "library": "H5P.MultiChoice 1.16",
            "params": {
                "question": f"<p>{q.get('question', '')}</p>",
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
                    "showScorePoint": True
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
                    "a11yCheck": "Sprawdź odpowiedzi. Zostaną zliczone punkty."
                },
                "media": {"disableImageZooming": False}
            }
        })

    content_json = {
        "introPage": {
            "showIntroPage": False,
            "startButtonText": "Rozpocznij Quiz",
            "introduction": f"<p>{title}</p>"
        },
        "progressType": "dots",
        "passPercentage": 50,
        "questions": h5p_questions,
        "disableBackwardsNavigation": False,
        "randomQuestions": False,
        "endGame": {
            "showResultPage": True,
            "showSolutionButton": True,
            "showRetryButton": True,
            "noResultMessage": "Zakończono quiz",
            "message": "Twój wynik to @score z @total punktów",
            "scoreBarLabel": "Zdobyłeś :num na :total punktów",
            "actionString": "Przejdź dalej",
            "solutionButtonText": "Pokaż rozwiązania",
            "retryButtonText": "Spróbuj ponownie"
        },
        "override": {
            "checkButton": True
        },
        "texts": {
            "prevButton": "Poprzednie",
            "nextButton": "Następne",
            "finishButton": "Zakończ",
            "submitButton": "Zatwierdź",
            "textualProgress": "Pytanie: @current z @total",
            "jumpToQuestion": "Pytanie %d",
            "questionLabel": "Pytanie",
            "readSpeakerProgress": "Pytanie @current z @total",
            "unansweredText": "Bez odpowiedzi",
            "answeredText": "Odpowiedziano",
            "emptyText": "Puste"
        }
    }

    h5p_json = {
        "title": title,
        "language": "pl",
        "mainLibrary": "H5P.QuestionSet",
        "embedTypes": ["div"],
        "preloadedDependencies": [
            {
                "machineName": "H5P.QuestionSet",
                "majorVersion": 1,
                "minorVersion": 20
            },
            {
                "machineName": "H5P.MultiChoice",
                "majorVersion": 1,
                "minorVersion": 16
            }
        ]
    }

    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        zipf.writestr("h5p.json", json.dumps(h5p_json, ensure_ascii=False, indent=2))
        zipf.writestr("content/content.json", json.dumps(content_json, ensure_ascii=False, indent=2))
