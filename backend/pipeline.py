import tarfile
import zipfile
import tempfile
from pathlib import Path

from agents.translation_agent import TranslationAgent
from agents.h5p_agent import H5PAgent


class PipelineManager:
    """
    Rozpakowuje plik MBZ, uruchamia wybrane agenty kolejno,
    po czym pakuje wynik z powrotem do archiwum tar.gz.
    """

    def __init__(self, config: dict):
        self.config = config
        self.agents = []
        if config.get("translate"):
            self.agents.append(TranslationAgent(config))
        if config.get("generate_h5p"):
            self.agents.append(H5PAgent(config))

    def execute(
        self,
        input_path: str,
        output_path: str,
        on_agent_start=None,
        on_agent_done=None,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)

            # ── Wypakowanie ────────────────────────────────────────────────
            if input_path.endswith(".zip"):
                with zipfile.ZipFile(input_path, "r") as z:
                    z.extractall(tmp_path)
            else:
                with tarfile.open(input_path, "r:gz") as t:
                    t.extractall(tmp_path)

            # ── Uruchomienie agentów ───────────────────────────────────────
            for agent in self.agents:
                name = agent.__class__.__name__
                if on_agent_start:
                    on_agent_start(name)
                try:
                    success, log = agent.process(str(tmp_path))
                except Exception as e:
                    success, log = False, str(e)
                if on_agent_done:
                    on_agent_done(name, success, log)

            # ── Pakowanie ────────────────────────────────────────────────
            # WAŻNE: Katalog h5p_generated/ NIE wchodzi do archiwum MBZ!
            # Moodle przyjmuje wyłącznie oryginalną strukturę backupu.
            # H5P jest generowane jako osobny output/log, nie wstrzykiwane do MBZ.
            EXCLUDE = {"h5p_generated"}

            with tarfile.open(output_path, "w:gz") as tar:
                for f in tmp_path.rglob("*"):
                    # Pomijaj katalogi i pliki w wykluczonych folderach
                    relative = f.relative_to(tmp_path)
                    if any(part in EXCLUDE for part in relative.parts):
                        continue
                    if f.is_file():
                        tar.add(f, arcname=relative)
