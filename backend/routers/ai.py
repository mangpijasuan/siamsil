from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services.data_loader import get_store
from services.language_engine import get_engine

router = APIRouter(prefix="/ai", tags=["ai"])

STOPWORDS = {
    "what", "whats", "does", "do", "did", "mean", "meaning", "the", "a", "an", "in",
    "to", "of", "is", "how", "you", "say", "please", "translate", "translation",
    "word", "for", "me", "my", "this", "that", "and", "or", "zomi", "english",
}


def lookup_query(message: str) -> str:
    tokens = [token for token in re.findall(r"[A-Za-z']+", message.lower()) if token not in STOPWORDS]
    return " ".join(tokens) if tokens else message.strip()


class AskRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)


def _intent(message: str) -> str:
    text = message.lower()
    if any(token in text for token in ("translate", "lehkhawn", "in zomi", "in english")):
        return "translate"
    if any(token in text for token in ("verse", "bible", "laisiangtho")):
        return "bible"
    return "dictionary"


@router.post("/ask")
def ask(request: AskRequest):
    engine = get_engine()
    if not engine.available:
        raise HTTPException(status_code=503, detail="Language database is not built yet.")

    store = get_store()
    intent = _intent(request.message)
    lookup = lookup_query(request.message)
    dictionary = engine.search_dictionary(lookup, limit=5)
    corpus = engine.search_parallel(lookup, limit=5)
    bible = store.search_bible(lookup if intent == "bible" else request.message, limit=3) if intent == "bible" else []

    sources: list[dict] = []
    if dictionary:
        top = dictionary[0]
        sources.append(
            {
                "type": "dictionary",
                "id": top["id"],
                "english": top["english"],
                "zomi": top["definition"],
                "verified": top["verified"],
                "verification_status": top["verification_status"],
                "source": top["source"],
            }
        )
    for pair in corpus[:3]:
        sources.append(
            {
                "type": "parallel_corpus",
                "english": pair["english"],
                "zomi": pair["zomi"],
                "verified": False,
                "label": pair["label"],
            }
        )
    for verse in bible[:2]:
        sources.append(
            {
                "type": "bible",
                "reference": verse.get("reference"),
                "english": verse.get("english"),
                "zomi": verse.get("zomi_iso"),
                "verified": True,
            }
        )

    if not sources:
        answer = (
            "I could not find this in the Siamsil dictionary, parallel corpus, or Bible text. "
            "I will not invent a Zomi translation."
        )
        confidence = "none"
    elif dictionary:
        top = dictionary[0]
        status = "verified dictionary entry" if top["verified"] else "dictionary entry that still needs review"
        answer = (
            f"{top['english']}: {top['definition'] or 'No definition stored.'} "
            f"This is a {status} from {top['source']}."
        )
        if corpus:
            answer += " Related sentence examples below are machine-translated and unverified."
        confidence = "high" if top["verified"] else "medium"
    else:
        answer = (
            "No dictionary headword matched. Showing the closest sentence examples from the "
            "machine-translated corpus. These are unverified."
        )
        confidence = "low"

    return {
        "mode": "retrieval",
        "intent": intent,
        "confidence": confidence,
        "answer": answer,
        "sources": sources,
        "note": "Siamsil AI Release 1 only retrieves approved or flagged Siamsil data. It does not generate new Zomi.",
    }
