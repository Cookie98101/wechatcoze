import unittest
from unittest.mock import patch

from doudian.DouDian import DouDian


class DouDianMessageDiffTests(unittest.TestCase):
    def setUp(self):
        self.dd = DouDian(headless=True)
        self.dd._get_chat_cache_key = lambda: "conv::biz:test-conv"
        self.dd._get_greeting_key = lambda: "conv::biz:test-conv"
        self.dd._should_send_greeting = lambda *args, **kwargs: False
        self.dd.sendBtnMsg = lambda *_args, **_kwargs: None
        self.dd._append_link_info_messages = lambda msgs: list(msgs)
        self.dd._append_product_panel_message = lambda msgs: list(msgs)

    @patch("doudian.DouDian.time.sleep", return_value=None)
    def test_read_current_unread_uses_monotonic_index_cursor(self, _sleep):
        first_snapshot = {
            "customer_messages": [
                {"index": 0, "who": "A", "type": "text", "content": "您好"},
            ],
            "my_messages": [],
            "session_key": "conv::biz:test-conv",
        }
        second_snapshot = {
            "customer_messages": [
                {"index": 0, "who": "A", "type": "text", "content": "您好"},
                {"index": 1, "who": "A", "type": "text", "content": "材质是什么"},
            ],
            "my_messages": [],
            "session_key": "conv::biz:test-conv",
        }
        snapshots = [first_snapshot, second_snapshot]
        self.dd._getAllCurrentMsg = lambda: snapshots.pop(0)

        first = self.dd.readCurrentUnread()
        second = self.dd.readCurrentUnread()

        self.assertEqual(first, [])
        self.assertEqual(len(second), 1)
        self.assertEqual(second[0]["content"], "材质是什么")

    @patch("doudian.DouDian.time.sleep", return_value=None)
    def test_read_current_unread_allows_same_text_to_arrive_twice(self, _sleep):
        first_snapshot = {
            "customer_messages": [
                {"index": 0, "who": "A", "type": "text", "content": "您好"},
            ],
            "my_messages": [],
            "session_key": "conv::biz:test-conv",
        }
        second_snapshot = {
            "customer_messages": [
                {"index": 0, "who": "A", "type": "text", "content": "您好"},
                {"index": 1, "who": "A", "type": "text", "content": "您好"},
            ],
            "my_messages": [],
            "session_key": "conv::biz:test-conv",
        }
        snapshots = [first_snapshot, second_snapshot]
        self.dd._getAllCurrentMsg = lambda: snapshots.pop(0)

        self.dd.readCurrentUnread()
        second = self.dd.readCurrentUnread()

        self.assertEqual(len(second), 1)
        self.assertEqual(second[0]["content"], "您好")

    @patch("doudian.DouDian.time.sleep", return_value=None)
    def test_after_switch_msg_does_not_replay_service_read_when_cursor_exists(self, _sleep):
        self.dd.chat_last_message_cursor["conv::biz:test-conv"] = 10
        self.dd._getAllCurrentMsg = lambda: {
            "customer_messages": [
                {"index": 10, "who": "A", "type": "text", "content": "这个大概有多大啊"},
            ],
            "my_messages": [],
            "session_key": "conv::biz:test-conv",
            "service_read_index": "0",
        }

        result = self.dd._getAfterSwitchMsg()

        self.assertEqual(result, [])

    @patch("doudian.DouDian.time.sleep", return_value=None)
    def test_after_switch_msg_does_not_replay_same_raw_message_when_cursor_missing(self, _sleep):
        snapshot = {
            "customer_messages": [
                {
                    "index": 1,
                    "who": "A",
                    "type": "text",
                    "content": "材质是什么",
                    "message_id": "msg-1",
                    "server_id": "server-1",
                },
            ],
            "my_messages": [],
            "session_key": "conv::biz:test-conv",
            "service_read_index": "0",
        }
        self.dd._getAllCurrentMsg = lambda: snapshot

        first = self.dd._getAfterSwitchMsg()
        self.dd.chat_last_message_cursor.pop("conv::biz:test-conv", None)
        second = self.dd._getAfterSwitchMsg()

        self.assertEqual(len(first), 1)
        self.assertEqual(first[0]["content"], "材质是什么")
        self.assertEqual(second, [])

    @patch("doudian.DouDian.time.sleep", return_value=None)
    def test_after_switch_msg_allows_same_text_with_new_message_id(self, _sleep):
        first_snapshot = {
            "customer_messages": [
                {
                    "index": 1,
                    "who": "A",
                    "type": "text",
                    "content": "您好",
                    "message_id": "msg-1",
                    "server_id": "server-1",
                },
            ],
            "my_messages": [],
            "session_key": "conv::biz:test-conv",
            "service_read_index": "0",
        }
        second_snapshot = {
            "customer_messages": [
                {
                    "index": 1,
                    "who": "A",
                    "type": "text",
                    "content": "您好",
                    "message_id": "msg-1",
                    "server_id": "server-1",
                },
                {
                    "index": 2,
                    "who": "A",
                    "type": "text",
                    "content": "您好",
                    "message_id": "msg-2",
                    "server_id": "server-2",
                },
            ],
            "my_messages": [],
            "session_key": "conv::biz:test-conv",
            "service_read_index": "0",
        }
        snapshots = [first_snapshot, second_snapshot]
        self.dd._getAllCurrentMsg = lambda: snapshots.pop(0)

        first = self.dd._getAfterSwitchMsg()
        second = self.dd._getAfterSwitchMsg()

        self.assertEqual(len(first), 1)
        self.assertEqual(first[0]["message_id"], "msg-1")
        self.assertEqual(len(second), 1)
        self.assertEqual(second[0]["message_id"], "msg-2")


if __name__ == "__main__":
    unittest.main()
