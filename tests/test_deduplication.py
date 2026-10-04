from types import SimpleNamespace

from app.deduplication.deduplicator import content_hash, similarity


def test_same_normalized_content_hashes_identically():
    a = SimpleNamespace(
        company_name="Acme",
        title="Backend Engineer",
        location="Nairobi",
        description="Python APIs",
        normalized_title=None,
    )
    b = SimpleNamespace(
        company_name="Acme",
        title="Backend  Engineer",
        location="Nairobi",
        description="Python APIs",
        normalized_title=None,
    )
    assert content_hash(a) == content_hash(b)
    assert similarity(a, b) > 0.9
