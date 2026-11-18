import unittest
from datetime import date

from app.job_monitor import extract_application_links


class JobMonitorTests(unittest.TestCase):
    source_url = "https://ssc.gov.in/"

    def test_application_link_with_labeled_dates_is_publishable(self):
        html = """
        <h2>Junior Clerk Recruitment 2099</h2>
        <p>Application start date: 01 Nov 2099</p>
        <p>Last date: 30 Nov 2099</p>
        <a href="/apply">Apply Online</a>
        """

        candidates = extract_application_links("SSC", self.source_url, html)

        self.assertEqual(len(candidates), 1)
        candidate = candidates[0]
        self.assertEqual(candidate["skip_reason"], "")
        self.assertEqual(candidate["title"], "Junior Clerk Recruitment 2099")
        self.assertEqual(candidate["apply_url"], "https://ssc.gov.in/apply")
        self.assertEqual(candidate["start_date"], date(2099, 11, 1))
        self.assertEqual(candidate["end_date"], date(2099, 11, 30))

    def test_missing_dates_are_marked_to_skip_without_review_queue(self):
        html = """
        <h2>Junior Clerk Recruitment 2026</h2>
        <a href="/apply">Apply Online</a>
        """

        candidate = extract_application_links("SSC", self.source_url, html)[0]

        self.assertTrue(candidate["skip_reason"])
        self.assertIsNone(candidate["start_date"])
        self.assertIn("date could not be confirmed", candidate["skip_reason"])

    def test_external_application_domains_are_marked_to_skip(self):
        html = """
        <h2>Junior Clerk Recruitment 2099</h2>
        <p>Application start date: 01 Nov 2099</p>
        <p>Last date: 30 Nov 2099</p>
        <a href="https://apply.example.com/form">Apply Online</a>
        """

        candidate = extract_application_links("SSC", self.source_url, html)[0]

        self.assertTrue(candidate["skip_reason"])
        self.assertIn("outside the monitored official domains", candidate["skip_reason"])

    def test_expired_application_links_are_marked_to_skip(self):
        html = """
        <h2>Junior Clerk Recruitment 2020</h2>
        <p>Application start date: 01 Nov 2020</p>
        <p>Last date: 30 Nov 2020</p>
        <a href="/apply">Apply Online</a>
        """

        candidate = extract_application_links("SSC", self.source_url, html)[0]

        self.assertIn("Application period has already ended", candidate["skip_reason"])

    def test_notification_links_are_not_published_as_application_links(self):
        html = '<a href="/notice.pdf">Recruitment Notification</a>'

        self.assertEqual(extract_application_links("SSC", self.source_url, html), [])


if __name__ == "__main__":
    unittest.main()
