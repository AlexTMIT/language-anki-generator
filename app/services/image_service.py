"""Google CSE image search abstraction."""
from typing import List
import requests

from ..config import settings

CSE_URL = "https://customsearch.googleapis.com/customsearch/v1"


def google_thumbs(query: str, k: int = 8) -> List[str]:
    params = {
        "key": settings.GOOGLE_CSE_KEY.get_secret_value(),
        "cx": settings.GOOGLE_CSE_CX,
        "searchType": "image",
        "safe": "off",
        "q": query,
        "num": k,
    }
    try:
        res = requests.get(CSE_URL, params=params, timeout=20)
        res.raise_for_status()
        data = res.json()
        return [it["link"] for it in data.get("items", [])][:k]
    except requests.RequestException as err:
        # keep the app running even if Google CSE flakes out
        print(f"Google CSE request failed: {err}")
        return []