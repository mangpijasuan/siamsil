from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api_schemas import AskResponse
from rate_limit import rate_limited
from services.bible_lookup import BibleLookup
from services.bible_versions import get_bible_versions
from services.language_engine import entry_zomi, get_engine

router = APIRouter(prefix="/ai", tags=["ai"], dependencies=[Depends(rate_limited("assistant"))])

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


@router.post("/ask", response_model=AskResponse)
def ask(request: AskRequest):
    engine = get_engine()
    if not engine.available:
        raise HTTPException(status_code=503, detail="Language database is not built yet.")

    intent = _intent(request.message)
    lookup = lookup_query(request.message)
    found, verses = BibleLookup(get_bible_versions()).passage(request.message, search=intent == "bible")
    if found == "reference":
        intent = "bible"
    # A named passage is answered from the Bible alone; a word or phrase also gets the dictionary and corpus.
    dictionary = [] if found == "reference" else engine.search_dictionary(lookup, limit=5)
    corpus = [] if intent == "bible" else engine.search_parallel(lookup, limit=5)

    sources: list[dict] = []
    if dictionary:
        top = dictionary[0]
        sources.append(
            {
                "type": "dictionary",
                "id": top["id"],
                "english": top["english"],
                "zomi": entry_zomi(top),
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
    for verse in verses:
        sources.append(
            {
                "type": "bible",
                "reference": verse["reference"],
                "english": verse["english"],
                "zomi": verse["zomi"],
                "source": verse["source"],
                "label": "Bible",
            }
        )

    if not sources:
        answer = (
            "I could not find this in the Siamsil dictionary, parallel corpus, or Bible text. "
            "I will not invent a Zomi translation."
        )
        confidence = "none"
    elif verses and (found == "reference" or not dictionary):
        how = "" if found == "reference" else "Verses containing those words: "
        answer = f"{how}{', '.join(v['reference'] for v in verses)}, from the {verses[0]['source']}."
        confidence = "high"
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
