import json
import uuid
from pathlib import Path
import lxml.etree as ET
from pydantic import BaseModel, Field
from typing import List
from agents.base_agent import BaseAgent


# ── Pydantic schema dla LLM ────────────────────────────────────────────────
class Flashcard(BaseModel):
    question: str = Field(description="Krótkie pytanie edukacyjne")
    answer:   str = Field(description="Odpowiedź do pytania")

class FlashcardDeck(BaseModel):
    cards: List[Flashcard] = Field(description="Lista fiszek edukacyjnych (3-6 sztuk)")


class H5PAgent(BaseAgent):
    """
    Wyodrębnia treść z XML-i kursu, wysyła ją do LLM (LangChain + GPT-4o)
    z prośbą o wygenerowanie fiszek, a następnie buduje katalog zgodny
    ze standardem H5P.Dialogcards i umieszcza go w workspace.
    """

    CONTENT_TAGS = {"intro", "content", "description", "summary"}

    def __init__(self, config: dict):
        super().__init__(config)
        self.api_key = config.get("api_key", "")

    # ── ekstrakcja tekstu ──────────────────────────────────────────────────
    def _extract_corpus(self, workspace: Path) -> str:
        chunks = []
        parser = ET.XMLParser(strip_cdata=False, recover=True)
        for xml_file in workspace.rglob("*.xml"):
            try:
                root = ET.parse(str(xml_file), parser).getroot()
                for tag in self.CONTENT_TAGS:
                    for elem in root.iter(tag):
                        if elem.text and len(elem.text.strip()) > 60:
                            chunks.append(elem.text.strip())
            except Exception:
                pass
        # maksymalnie ~4 000 znaków żeby zmieścić się w oknie kontekstu
        corpus = "\n\n".join(chunks)
        return corpus[:4000] if len(corpus) > 4000 else corpus

    # ── LangChain + LLM ───────────────────────────────────────────────────
    def _generate_flashcards(self, corpus: str) -> FlashcardDeck:
        if not self.api_key or not corpus.strip():
            # fallback bez AI
            return FlashcardDeck(cards=[
                Flashcard(question="Czym jest Moodle?",
                          answer="Platforma do zarządzania kursami e-learninowymi."),
                Flashcard(question="Co to jest H5P?",
                          answer="Standard tworzenia interaktywnych treści edukacyjnych."),
            ])
        try:
            from langchain_core.prompts import PromptTemplate
            from langchain_openai import ChatOpenAI
            from langchain_core.output_parsers import PydanticOutputParser

            parser = PydanticOutputParser(pydantic_object=FlashcardDeck)

            prompt = PromptTemplate(
                template=(
                    "Jesteś ekspertem dydaktycznym. Na podstawie poniższego materiału kursu "
                    "wygeneruj od 3 do 6 fiszek edukacyjnych (pytanie + odpowiedź).\n\n"
                    "{format_instructions}\n\n"
                    "Materiał:\n{corpus}\n"
                ),
                input_variables=["corpus"],
                partial_variables={"format_instructions": parser.get_format_instructions()},
            )

            llm = ChatOpenAI(model="gpt-4o", temperature=0.5, openai_api_key=self.api_key)
            chain = prompt | llm | parser
            return chain.invoke({"corpus": corpus})
        except Exception as e:
            print(f"[H5PAgent] LLM error: {e}")
            return FlashcardDeck(cards=[
                Flashcard(question="Przykładowe pytanie (brak AI)", answer="Przykładowa odpowiedź.")
            ])

    # ── budowanie struktury H5P ────────────────────────────────────────────
    def _build_h5p(self, workspace: Path, deck: FlashcardDeck):
        """
        Tworzy katalog h5p_generated/<uuid>/
          ├── h5p.json
          └── content/
                └── content.json
        Zgodny z H5P.Dialogcards 1.9
        """
        if not deck.cards:
            return

        out_dir = workspace / "h5p_generated" / uuid.uuid4().hex[:8]
        (out_dir / "content").mkdir(parents=True, exist_ok=True)

        h5p_meta = {
            "title": "Fiszki wygenerowane przez AI",
            "language": "pl",
            "mainLibrary": "H5P.Dialogcards",
            "preloadedDependencies": [
                {"machineName": "H5P.Dialogcards", "majorVersion": 1, "minorVersion": 9}
            ]
        }
        (out_dir / "h5p.json").write_text(
            json.dumps(h5p_meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        content = {
            "title": "Fiszki edukacyjne",
            "mode": "normal",
            "dialogs": [
                {"text": c.question, "answer": c.answer}
                for c in deck.cards
            ]
        }
        (out_dir / "content" / "content.json").write_text(
            json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # ── entry-point ────────────────────────────────────────────────────────
    def process(self, workspace_path: str) -> tuple[bool, str]:
        workspace = Path(workspace_path)
        corpus = self._extract_corpus(workspace)
        deck   = self._generate_flashcards(corpus)
        self._build_h5p(workspace, deck)
        return True, f"Wygenerowano {len(deck.cards)} fiszek H5P."
