from datetime import datetime, timezone
import unittest
from unittest.mock import patch

from weekend_briefing import parse_articles, deduplicate, build_messages, news_window

UTC = timezone.utc


class WeekendTests(unittest.TestCase):
    def test_window_includes_only_after_latest_completed_market_close(self):
        start, end = news_window(datetime(2026, 11, 15, 22, tzinfo=UTC))
        self.assertEqual(start, datetime(2026, 11, 13, 21, tzinfo=UTC))
        # Holiday Friday: Thursday is the last actual trading session.
        start, _ = news_window(datetime(2026, 4, 5, 22, tzinfo=UTC))
        self.assertEqual(start, datetime(2026, 4, 2, 20, tzinfo=UTC))

    def test_timestamp_window_not_search_query_controls_inclusion(self):
        raw = b'''<rss version="2.0"><channel><title>News</title>
        <item><title>Old</title><link>https://example.com/old</link><pubDate>Fri, 13 Nov 2026 20:00:00 GMT</pubDate></item>
        <item><title>Weekend</title><link>https://example.com/weekend</link><pubDate>Sat, 14 Nov 2026 12:00:00 GMT</pubDate></item>
        <item><title>Future</title><link>https://example.com/future</link><pubDate>Mon, 16 Nov 2026 03:00:00 GMT</pubDate></item>
        <item><title>No date</title><link>https://example.com/missing</link></item>
        </channel></rss>'''
        rows = parse_articles(raw, datetime(2026, 11, 13, 21, tzinfo=UTC), datetime(2026, 11, 15, 22, tzinfo=UTC))
        self.assertEqual([r['title'] for r in rows], ['Weekend'])
        self.assertEqual(len(deduplicate(rows + rows)), 1)

    def test_five_korean_cards_with_links_and_no_internal_ids(self):
        rows = [{'id': 'n' + str(i), 'title': 'Title', 'url': 'https://example.com/' + str(i)} for i in range(1, 7)]
        summary = {'news': [{'id': r['id'], 'title_ko': '주말 주요 기사', 'summary': '확인된 내용입니다 [n2, n10]', 'impact': '해석: 다음 거래일에 주목합니다.'} for r in rows]}
        messages = build_messages(rows, summary, datetime(2026, 11, 13, 21, tzinfo=UTC), datetime(2026, 11, 15, 22, tzinfo=UTC))
        self.assertEqual(len(messages), 7)
        self.assertIn('주말 이슈로 본 시장 요약', messages[-1][0])
        self.assertIsNone(messages[-1][1])
        self.assertTrue(all('[n' not in m for m, _ in messages))
        self.assertTrue(all(url is not None for _, url in messages[1:-1]))
        self.assertTrue(all(len(m.encode('utf-16-le')) // 2 <= 3800 for m, _ in messages))

    def test_shortfall_disclosed_and_no_english_only_summary_broadcast(self):
        now = datetime(2026, 11, 15, 22, tzinfo=UTC)
        rows = [{'id': 'n1', 'title': 'Title', 'url': 'https://example.com'}]
        messages = build_messages(rows, {'news': [{'id': 'n1', 'title_ko': '한국어 제목', 'summary': '한국어 요약'}]}, now, now)
        self.assertIn('5개 미만', messages[0][0])
        with self.assertRaises(ValueError):
            build_messages(rows, {'news': [{'id': 'n1', 'title_ko': 'English', 'summary': 'English'}]}, now, now)


if __name__ == '__main__':
    unittest.main()
