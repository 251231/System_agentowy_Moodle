from pydantic import BaseModel
from typing import List

class LinkReplacement(BaseModel):
    url: str
    suggested_url: str
    archive_path: str

class ReplaceLinksRequest(BaseModel):
    replacements: List[LinkReplacement]
