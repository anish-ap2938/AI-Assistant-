import re
from fastapi import HTTPException

banned_terms = ["classified", "confidential"]

async def check_query(q: str):
    for term in banned_terms:
        if re.search(rf"\b{term}\b", q, re.IGNORECASE):
            raise HTTPException(400, f"Query contains banned term: {term}")