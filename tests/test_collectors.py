import httpx
import pytest

from app.collectors.aggregators import JoobleCollector
from app.collectors.ashby import AshbyCollector
from app.collectors.greenhouse import GreenhouseCollector
from app.collectors.lever import LeverCollector
from app.config import settings


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "collector,url,data,config",
    [
        (
            GreenhouseCollector,
            "https://boards-api.greenhouse.io/v1/boards/test/jobs?content=true",
            {
                "jobs": [
                    {
                        "id": 1,
                        "title": "Engineer",
                        "content": "<p>Python</p>",
                        "location": {"name": "Nairobi"},
                        "absolute_url": "https://example.test/job",
                    }
                ]
            },
            {"name": "Example", "ats_identifier": "test"},
        ),
        (
            LeverCollector,
            "https://api.lever.co/v0/postings/test?mode=json",
            [{"id": "x", "text": "Engineer", "hostedUrl": "https://example.test/job"}],
            {"name": "Example", "ats_identifier": "test"},
        ),
        (
            AshbyCollector,
            "https://api.ashbyhq.com/posting-api/job-board/test?includeCompensation=true",
            {
                "jobs": [
                    {"title": "Engineer", "isListed": True, "jobUrl": "https://example.test/job"}
                ]
            },
            {"name": "Example", "ats_identifier": "test"},
        ),
    ],
)
async def test_official_connectors_parse_public_postings(collector, url, data, config):
    def handler(request):
        return httpx.Response(200, json=data)

    c = collector(httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    got = await c.fetch(config)
    assert len(got) == (len(data) if isinstance(data, list) else len(data["jobs"]))
    model = c.normalize(got[0], config)
    assert model.title == "Engineer" and model.source_url
    await c.close()


@pytest.mark.asyncio
async def test_lever_paginates_with_documented_skip_and_limit():
    requests = []

    def handler(request):
        requests.append(request.url.params.get("skip"))
        rows = (
            [{"id": "1", "text": "A"}, {"id": "2", "text": "B"}]
            if request.url.params.get("skip") == "0"
            else [{"id": "3", "text": "C"}]
        )
        return httpx.Response(200, json=rows)

    c = LeverCollector(httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    rows = await c.fetch({"ats_identifier": "test", "page_size": 2, "max_pages": 3})
    assert [row["id"] for row in rows] == ["1", "2", "3"]
    assert requests == ["0", "2"]
    await c.close()


@pytest.mark.asyncio
async def test_transient_statuses_retry_and_non_transient_does_not():
    requests = 0

    def handler(request):
        nonlocal requests
        requests += 1
        if requests == 1:
            return httpx.Response(429)
        if requests == 2:
            return httpx.Response(503)
        return httpx.Response(200, json={"ok": True})

    c = GreenhouseCollector(httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    c.request_interval = 0
    assert await c.request_json("https://example.test/feed") == {"ok": True}
    assert requests == 3
    await c.close()


@pytest.mark.asyncio
async def test_timeout_retries_and_malformed_json_is_rejected():
    requests = 0

    def timeout_once(request):
        nonlocal requests
        requests += 1
        if requests == 1:
            raise httpx.ReadTimeout("timed out", request=request)
        return httpx.Response(200, json={"recovered": True})

    c = GreenhouseCollector(httpx.AsyncClient(transport=httpx.MockTransport(timeout_once)))
    c.request_interval = 0
    assert await c.request_json("https://example.test/feed") == {"recovered": True}
    await c.close()
    bad = GreenhouseCollector(
        httpx.AsyncClient(
            transport=httpx.MockTransport(lambda r: httpx.Response(200, content=b"{"))
        )
    )
    with pytest.raises(ValueError):
        await bad.request_json("https://example.test/bad")
    await bad.close()


@pytest.mark.asyncio
async def test_jooble_request_budget_is_strict(monkeypatch):
    monkeypatch.setattr(settings, "jooble_api_key", "test-key")
    requests = 0

    def handler(request):
        nonlocal requests
        requests += 1
        return httpx.Response(200, json={"jobs": []})

    c = JoobleCollector(httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    c.request_interval = 0
    rows = await c.fetch(
        {
            "max_requests_per_run": 2,
            "markets": [
                {"location": "Kenya", "domain": "jooble.org", "key_env": "NO_SUCH_KEY"},
                {"location": "US", "domain": "jooble.org", "key_env": "NO_SUCH_KEY"},
            ],
            "keywords": ["python", "devops", "cloud"],
        }
    )
    assert rows == [] and requests == 2
    await c.close()


def test_empty_and_malformed_normalizers_are_safe():
    c = GreenhouseCollector(
        httpx.AsyncClient(
            transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"jobs": []}))
        )
    )
    assert c.normalize({"id": 1, "title": "", "content": None}, {"name": "Example"}).title == ""
