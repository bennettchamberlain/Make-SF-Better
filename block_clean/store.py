import os

from dotenv import load_dotenv

from paths import ROOT


class CaseNotFound(Exception):
    pass


class AlreadySolved(Exception):
    pass


def elastic_configured():
    endpoint = os.getenv("ELASTIC_ENDPOINT", "").strip()
    key = os.getenv("ELASTIC_API_KEY", "").strip()
    if not endpoint or not key:
        return False
    placeholders = ("your-project", "your-elastic", "your-elastic-api-key")
    blob = f"{endpoint} {key}"
    return not any(item in blob for item in placeholders)


def get_store():
    load_dotenv(ROOT / ".env")
    load_dotenv(ROOT.parent / ".env")
    if elastic_configured():
        from elastic_store import ElasticStore
        return ElasticStore()
    from local_store import LocalStore
    return LocalStore()
