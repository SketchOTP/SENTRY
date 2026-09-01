import socket
import unittest
from datetime import datetime, timezone

from tools.sentry_conversation_tools import ConversationToolHost
from tools.sentry_web import PublicWeather, WebDocument, WebResearchClient, WebResearchError, validate_public_url


def public_resolver(*_args, **_kwargs):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]


def private_resolver(*_args, **_kwargs):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))]


class FixtureSearchClient(WebResearchClient):
    def __init__(self):
        self._resolver = public_resolver

    def read(self, url, *, excerpt_limit=4_000):
        timestamp = datetime.now(timezone.utc).isoformat()
        if "bing.com" in url:
            return WebDocument(
                url=url,
                title="search",
                content_type="text/xml",
                text="<?xml version='1.0'?><rss><channel><item><title>Source A</title><link>https://example.com/a</link><description>Snippet A</description></item><item><title>Source B</title><link>https://example.com/b</link><description>Snippet B</description></item></channel></rss>",
                retrieved_at=timestamp,
            )
        return WebDocument(url=url, title=f"source {url[-1]}", content_type="text/html", text="public source text", retrieved_at=timestamp)


class FakeWebClient:
    def __init__(self):
        self.calls = []

    def search(self, query, *, max_results):
        self.calls.append(("search", query, max_results))
        return [WebDocument("https://example.com/search", "Search source", "text/html", "safe public excerpt", "2026-09-01T12:00:00+00:00")]

    def read(self, url):
        self.calls.append(("read", url))
        return WebDocument(url, "Page source", "text/html", "safe page excerpt", "2026-09-01T12:00:00+00:00")


class FakePublicWeatherClient:
    def __init__(self):
        self.calls = []

    def get_weather(self, location, *, when):
        self.calls.append((location, when))
        return PublicWeather(
            location="Boston, Massachusetts, United States",
            local_date="2026-09-02",
            timezone="America/New_York",
            summary="clear",
            temperature_min_f=54.0,
            temperature_max_f=68.0,
            precipitation_probability_max=5,
            retrieved_at="2026-09-01T12:00:00+00:00",
        )


class WebResearchTests(unittest.TestCase):
    def test_public_url_validation_rejects_private_and_non_http_targets(self):
        self.assertEqual(validate_public_url("https://example.com/path", resolver=public_resolver), "https://example.com/path")
        with self.assertRaises(WebResearchError):
            validate_public_url("https://example.com", resolver=private_resolver)
        for url in ("file:///etc/passwd", "http://127.0.0.1/", "https://user:password@example.com/", "https://example.com:8443/"):
            with self.subTest(url=url), self.assertRaises(WebResearchError):
                validate_public_url(url, resolver=public_resolver)

    def test_search_parses_bounded_sources_without_model_visible_transport(self):
        documents = FixtureSearchClient().search("public research", max_results=2)
        self.assertEqual([document.url for document in documents], ["https://example.com/a", "https://example.com/b"])
        self.assertTrue(all(document.text == "public source text" for document in documents))

    def test_search_keeps_explicit_search_snippet_when_destination_is_blocked(self):
        class BlockedFixture(FixtureSearchClient):
            def read(self, url, *, excerpt_limit=4_000):
                if "bing.com" in url:
                    return super().read(url, excerpt_limit=excerpt_limit)
                raise WebResearchError("blocked")

        documents = BlockedFixture().search("public research", max_results=1)
        self.assertEqual(documents[0].retrieval_method, "search_snippet")
        self.assertEqual(documents[0].text, "Snippet A")

    def test_search_drops_invalid_destination_before_snippet_fallback(self):
        class PrivateResultFixture(FixtureSearchClient):
            def _validate(self, url):
                if "example.com/a" in url:
                    raise WebResearchError("private target")
                return url

        with self.assertRaisesRegex(WebResearchError, "could not be read"):
            PrivateResultFixture().search("public research", max_results=1)

    def test_host_exposes_read_only_web_facts_and_rejects_bad_arguments(self):
        client = FakeWebClient()
        weather_client = FakePublicWeatherClient()
        host = ConversationToolHost(base_url="http://127.0.0.1:48174", web_client=client, public_weather_client=weather_client)
        searched = host.execute("search_web", {"query": "weather in Boston tomorrow", "max_results": 1})
        self.assertEqual(searched["status"], "supported")
        self.assertEqual(searched["facts"][0]["fact_id"], "web:search:1")
        self.assertNotIn("instructions", searched["facts"][0]["data"])
        self.assertEqual(searched["facts"][0]["data"]["retrieval_method"], "page")
        page = host.execute("read_web_page", {"url": "https://example.com/page"})
        self.assertEqual(page["facts"][0]["fact_id"], "web:page:1")
        self.assertEqual(client.calls, [("search", "weather in Boston tomorrow", 1), ("read", "https://example.com/page")])
        weather = host.execute("get_public_weather", {"location": "Boston", "when": "tomorrow"})
        self.assertEqual(weather["status"], "supported")
        self.assertEqual(weather["facts"][0]["fact_id"], "public-weather:forecast:1")
        self.assertNotIn("latitude", weather["facts"][0]["data"])
        self.assertEqual(weather_client.calls, [("Boston", "tomorrow")])
        self.assertIn("invalid tool call", host.execute("search_web", {"query": "x\nmalformed"})["limitations"][0])
        self.assertIn("invalid tool call", host.execute("read_web_page", {"url": "file:///etc/passwd"})["limitations"][0])
        self.assertIn("invalid tool call", host.execute("get_public_weather", {"location": "Boston", "when": "later"})["limitations"][0])


if __name__ == "__main__":
    unittest.main()
