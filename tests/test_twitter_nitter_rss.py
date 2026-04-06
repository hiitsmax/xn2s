from __future__ import annotations

from datetime import UTC, datetime

import feedparser

import xs2n.utils.twitter as twitter_nitter_rss
from xs2n.utils.twitter import _build_thread_from_entry


_SINCE = datetime(2026, 3, 29, 0, 0, tzinfo=UTC)


def _parse_entry(item_xml: str):  # noqa: ANN202
    feed = feedparser.parse(
        (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<rss xmlns:atom="http://www.w3.org/2005/Atom" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/" version="2.0">'
            "<channel>"
            f"{item_xml}"
            "</channel>"
            "</rss>"
        )
    )
    return feed["entries"][0]


def test_build_thread_from_retweet_entry_keeps_feed_actor_and_extracts_reference() -> None:
    entry = _parse_entry(
        """
        <item>
          <title>RT by @elonmusk: Here&apos;s how fast the internet is using Starlink while flying over the Gulf of America.</title>
          <dc:creator>@cremieuxrecueil</dc:creator>
          <description><![CDATA[<p>Here&apos;s how fast the internet is using Starlink while flying over the Gulf of America.</p>]]></description>
          <pubDate>Sun, 29 Mar 2026 20:10:07 GMT</pubDate>
          <guid isPermaLink="false">2038347996941709505</guid>
          <link>https://nitter.net/cremieuxrecueil/status/2038347996941709505#m</link>
        </item>
        """
    )

    thread = _build_thread_from_entry("elonmusk", entry)

    assert thread is not None
    assert thread.account_handle == "elonmusk"
    assert thread.primary_post.author_handle == "elonmusk"
    assert thread.primary_post.entry_type == "retweet"
    assert thread.primary_post.text == (
        "Here's how fast the internet is using Starlink while flying over the Gulf of America."
    )
    assert thread.primary_post.url == "https://x.com/cremieuxrecueil/status/2038347996941709505"
    assert thread.primary_post.referenced_author_handle == "cremieuxrecueil"
    assert thread.primary_post.referenced_text == thread.primary_post.text
    assert thread.primary_post.referenced_url == thread.primary_post.url


def test_build_thread_from_quote_entry_splits_comment_from_quoted_tweet() -> None:
    entry = _parse_entry(
        """
        <item>
          <title>Yes</title>
          <dc:creator>@elonmusk</dc:creator>
          <description><![CDATA[<p>Yes</p>
          <hr/>
          <blockquote>
          <b>C3 (@C_3C_3)</b>
          <p>
          <p>This.👇</p>
          <img src="https://nitter.net/pic/media%2FHElka6BWgAEuavg.jpg" style="max-width:250px;" />
          </p>
          <footer>
          — <cite><a href="https://nitter.net/C_3C_3/status/2038270726994526646#m">https://nitter.net/C_3C_3/status/2038270726994526646#m</a>
          </footer>
          </blockquote>]]></description>
          <pubDate>Sun, 29 Mar 2026 21:30:05 GMT</pubDate>
          <guid isPermaLink="false">2038368121241960877</guid>
          <link>https://nitter.net/elonmusk/status/2038368121241960877#m</link>
        </item>
        """
    )

    thread = _build_thread_from_entry("elonmusk", entry)

    assert thread is not None
    assert thread.account_handle == "elonmusk"
    assert thread.primary_post.author_handle == "elonmusk"
    assert thread.primary_post.entry_type == "quote"
    assert thread.primary_post.text == "Yes"
    assert thread.primary_post.url == "https://x.com/elonmusk/status/2038368121241960877"
    assert thread.primary_post.referenced_author_handle == "C_3C_3"
    assert thread.primary_post.referenced_text == "This.👇"
    assert thread.primary_post.referenced_url == "https://x.com/C_3C_3/status/2038270726994526646"


def test_build_thread_from_retweet_entry_matches_feed_handle_case_insensitively() -> None:
    entry = _parse_entry(
        """
        <item>
          <title>RT by @ElonMusk: Example retweet text</title>
          <dc:creator>@sourceauthor</dc:creator>
          <description><![CDATA[<p>Example retweet text</p>]]></description>
          <pubDate>Sun, 29 Mar 2026 20:10:07 GMT</pubDate>
          <guid isPermaLink="false">2038347996941709505</guid>
          <link>https://nitter.net/sourceauthor/status/2038347996941709505#m</link>
        </item>
        """
    )

    thread = _build_thread_from_entry("elonmusk", entry)

    assert thread is not None
    assert thread.primary_post.entry_type == "retweet"


def test_nitter_instances_prefers_nitter_net_first() -> None:
    assert twitter_nitter_rss.NITTER_INSTANCES[0] == "nitter.net"


def test_get_threads_for_handle_skips_placeholder_feed_and_reports_attempts(
    monkeypatch,  # noqa: ANN001
) -> None:
    placeholder_entry = feedparser.FeedParserDict(
        {
            "title": "RSS reader not yet whitelisted!",
            "link": "https://rss.xcancel.com/elonmusk/rss",
            "summary": "placeholder",
            "published": "Mon, 01 January 1971 00:00:00 GMT",
        }
    )
    valid_entry = _parse_entry(
        """
        <item>
          <title>Normal post</title>
          <dc:creator>@elonmusk</dc:creator>
          <description><![CDATA[<p>Normal post</p>]]></description>
          <pubDate>Sun, 29 Mar 2026 21:30:05 GMT</pubDate>
          <guid isPermaLink="false">2038368121241960877</guid>
          <link>https://nitter.net/elonmusk/status/2038368121241960877#m</link>
        </item>
        """
    )
    attempts: list[str] = []
    feeds = {
        "xcancel.com": feedparser.FeedParserDict(entries=[placeholder_entry]),
        "nitter.net": feedparser.FeedParserDict(entries=[valid_entry]),
    }

    monkeypatch.setattr(
        twitter_nitter_rss,
        "NITTER_INSTANCES",
        ["xcancel.com", "nitter.net"],
    )
    monkeypatch.setattr(
        twitter_nitter_rss,
        "_fetch_feed",
        lambda handle, instance: feeds[instance],
    )

    threads = twitter_nitter_rss._get_threads_for_handle(
        "elonmusk",
        _SINCE,
        report_progress=attempts.append,
    )

    assert len(threads) == 1
    assert any("trying xcancel.com" in message for message in attempts)
    assert any("skipping placeholder or unsupported RSS feed" in message for message in attempts)
    assert any("using nitter.net" in message for message in attempts)
