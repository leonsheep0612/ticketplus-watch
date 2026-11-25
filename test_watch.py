import unittest
from unittest.mock import patch

import watch


EVENT_ID = "a" * 32
URL = f"https://ticketplus.com.tw/activity/{EVENT_ID}"


def catalog():
    return {
        "sessions": [{"sessionId": "s1", "name": "台北場", "date": "2027-01-01"},
                     {"sessionId": "s2", "name": "隱藏場", "hidden": True}],
        "ticketAreas": [{"ticketAreaId": "a1", "sessionId": "s1", "name": "A區"}],
        "products": [{"productId": "p1", "ticketAreaId": "a1", "name": "全票"},
                     {"productId": "p2", "sessionId": "s1", "name": "站票"},
                     {"productId": "p3", "sessionId": "s2", "name": "隱藏票"}],
    }


def statuses(area_count=1, product_count=0):
    return {"errCode": "00", "result": {
        "product": [{"id": "p1", "status": "onsale", "productLimit": False, "count": 0},
                    {"id": "p2", "status": "onsale", "productLimit": True, "count": product_count}],
        "ticketArea": [{"id": "a1", "status": "onsale", "ticketAreaLimit": True,
                        "count": area_count}],
    }}


class WatchTests(unittest.TestCase):
    def test_validate_event_url(self):
        self.assertEqual(watch.event_id_from_url(URL + "?foo=bar"), EVENT_ID)
        for url in ("http://ticketplus.com.tw/activity/" + EVENT_ID,
                    "https://ticketplus.com.tw.evil.test/activity/" + EVENT_ID,
                    "https://ticketplus.com.tw/activity/not-an-id"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                watch.event_id_from_url(url)

    @patch("watch.request_json")
    @patch("watch.catalog", side_effect=lambda _: catalog())
    def test_stock_requires_product_and_area(self, _catalog, request):
        request.return_value = statuses()
        self.assertEqual(watch.available_tickets(EVENT_ID), {"p1": "台北場 / 2027-01-01 / A區 / 全票"})
        request.return_value = statuses(area_count=0, product_count=2)
        self.assertEqual(watch.available_tickets(EVENT_ID), {"p2": "台北場 / 2027-01-01 / 站票"})

    @patch("watch.request_json")
    @patch("watch.catalog", side_effect=lambda _: catalog())
    def test_partial_status_is_an_error_not_sold_out(self, _catalog, request):
        request.return_value = statuses()
        request.return_value["result"]["product"].pop()
        with self.assertRaises(watch.WatchError):
            watch.available_tickets(EVENT_ID)

    def test_limited_unknown_count_is_an_error(self):
        with self.assertRaises(watch.WatchError):
            watch.ready({"status": "onsale", "productLimit": True}, "productLimit")
        self.assertFalse(watch.ready({"status": "soldout"}, "productLimit"))

    @patch("watch.request_json")
    def test_telegram_post_and_failure(self, request):
        request.return_value = {"ok": True}
        watch.notify("123:abc", "456", URL, {"p1": "A區"})
        self.assertIn(b"chat_id=456", request.call_args.args[1])
        request.return_value = {"ok": False}
        with self.assertRaises(watch.WatchError):
            watch.notify("123:abc", "456", URL, {"p1": "A區"})

    @patch("watch.time.sleep")
    @patch("watch.notify")
    @patch("watch.available_tickets")
    def test_retry_and_notify_only_on_new_availability(self, available, notify, sleep):
        available.side_effect = [
            {"p1": "A"}, {"p1": "A"}, watch.WatchError("暫時失敗"),
            {}, {"p1": "A"}, KeyboardInterrupt,
        ]
        notify.side_effect = [watch.WatchError("通知失敗"), None, None]
        with self.assertRaises(KeyboardInterrupt):
            watch.watch(EVENT_ID, URL, "123:abc", "456", 60)
        self.assertEqual(notify.call_count, 3)
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [60, 60, 60, 60, 60])


if __name__ == "__main__":
    unittest.main()
