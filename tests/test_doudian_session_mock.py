import unittest
from unittest.mock import patch

from doudian.DouDian import DouDian


class FakeTitleElement:
    def __init__(self, title):
        self.title = title

    def get_attribute(self, attr):
        if attr == "title":
            return self.title
        return ""


class FakeConversationItem:
    def __init__(self, page, row):
        self.page = page
        self.row = row

    def inner_text(self):
        return self.row.get("text", "")

    def get_attribute(self, attr):
        if attr == "aria-selected":
            selected = self.page.current_conversation_id == self.row.get("biz_id")
            return "true" if selected else "false"
        return self.row.get(attr, "")

    def query_selector(self, selector):
        if selector in ("[title]", '[class*="name"][title]', '[class*="nick"][title]'):
            title = self.row.get("title", "")
            if title:
                return FakeTitleElement(title)
        return None

    def click(self):
        self.page.current_conversation_id = self.row.get("biz_id", "")
        self.page.current_buyer_id = self.row.get("buyer_id", "")


class FakeLocator:
    def __init__(self, page, selector):
        self.page = page
        self.selector = selector

    def click(self, timeout=None):
        if self.selector == '[data-qa-id="qa-active-chat-tab"]':
            self.page.active_tab = "current"
            return
        if self.selector == '[data-qa-id="qa-last-chat-tab"]':
            self.page.active_tab = "recent"
            return
        raise AssertionError(f"unexpected locator click: {self.selector}")


class FakePage:
    def __init__(self, rows, current_conversation_id="", current_buyer_id="", active_tab="recent"):
        self.rows = list(rows)
        self.current_conversation_id = current_conversation_id
        self.current_buyer_id = current_buyer_id
        self.active_tab = active_tab
        self.runtime_wait_reply_buyers = []
        self.runtime_over_three_buyers = []
        self.runtime_servicing_buyers = []
        self.runtime_conversations = []

    def _visible_rows(self):
        if self.active_tab == "recent":
            return [row for row in self.rows if "recent" in row.get("btm", "") or "systemConv" in row.get("btm", "")]
        return [row for row in self.rows if "recent" not in row.get("btm", "")]

    def locator(self, selector):
        return FakeLocator(self, selector)

    def query_selector_all(self, selector):
        if selector != '[data-kora="conversation"][data-qa-id="qa-conversation-chat-item"]':
            return []
        return [FakeConversationItem(self, row) for row in self._visible_rows()]

    def query_selector(self, selector):
        return None

    def evaluate(self, script, arg=None):
        if "item.unreplied" in script or ".filter((item) => item.session_key !== 'conv::biz:' && item.buyer_id && item.unreplied)" in script:
            wait_reply = {str(v).strip() for v in self.runtime_wait_reply_buyers}
            over_three = {str(v).strip() for v in self.runtime_over_three_buyers}
            servicing = {str(v).strip() for v in self.runtime_servicing_buyers}
            rows = []
            for conv in self.runtime_conversations:
                buyer_id = str(conv.get("buyerId", "")).strip()
                unread_count = int(conv.get("unreadCount", 0) or 0)
                countdown = bool(conv.get("countdown"))
                countdown_time = int(conv.get("countdownTime", 0) or 0)
                in_wait_reply = buyer_id in wait_reply if buyer_id else False
                in_over_three = buyer_id in over_three if buyer_id else False
                in_servicing = buyer_id in servicing if buyer_id else False
                unreplied = unread_count > 0 or in_wait_reply or in_over_three or countdown
                if conv.get("id") and buyer_id and not conv.get("closed") and unreplied:
                    rows.append({
                        "session_key": f"conv::biz:{str(conv.get('id', '')).strip()}",
                        "buyer_id": buyer_id,
                        "unread_count": unread_count,
                        "countdown": countdown,
                        "countdown_time": countdown_time,
                        "in_wait_reply": in_wait_reply,
                        "in_over_three": in_over_three,
                        "in_servicing": in_servicing,
                        "unreplied": unreplied,
                    })
            rows.sort(key=lambda item: (
                -(3 if item["in_over_three"] else (2 if item["in_wait_reply"] or item["countdown"] else 1)),
                item["countdown_time"] if item["countdown_time"] else 10**12,
                -item["unread_count"],
                item["session_key"],
            ))
            return rows
        if "__monaGlobalStore" in script:
            buyer_conversation_id = ""
            if self.current_buyer_id:
                for row in self.rows:
                    if row.get("buyer_id") == self.current_buyer_id:
                        buyer_conversation_id = row.get("biz_id", "")
                        break
            return {
                "currentConversationId": self.current_conversation_id,
                "currentBuyerId": self.current_buyer_id,
                "currentBuyerConversationId": buyer_conversation_id,
                "historyBuyers": [row["buyer_id"] for row in self.rows if "recent" in row.get("btm", "")],
                "recentSystemConvList": [row["buyer_id"] for row in self.rows if "systemConv" in row.get("btm", "")],
                "servicingBuyers": list(self.runtime_servicing_buyers),
                "waitReplyBuyers": list(self.runtime_wait_reply_buyers),
                "overThreeBuyers": list(self.runtime_over_three_buyers),
                "aiServerBuyers": [],
                "autoReplyBuyers": [],
                "humanReplyBuyers": [],
                "systemConvList": [],
                "activeTab": self.active_tab,
            }
        if "target.click()" in script:
            target_index = int(arg)
            for row in self._visible_rows():
                if int(row.get("index", -1)) == target_index:
                    self.current_conversation_id = row.get("biz_id", "")
                    self.current_buyer_id = row.get("buyer_id", "")
                    return None
            raise AssertionError(f"row index not found: {target_index}")
        if "document.querySelectorAll('[data-kora=\"conversation\"][data-qa-id=\"qa-conversation-chat-item\"]')).map" in script:
            return [
                {
                    "index": row.get("index"),
                    "btm": row.get("btm", ""),
                    "title": row.get("title", ""),
                    "text": row.get("text", ""),
                    "className": "active" if self.current_conversation_id == row.get("biz_id", "") else "",
                }
                for row in self._visible_rows()
            ]
        if "aria-selected" in script:
            return ""
        raise AssertionError(f"unexpected evaluate call: {script[:80]}")


class DouDianSessionMockTests(unittest.TestCase):
    def setUp(self):
        self.cookie_biz = "61555749413:245038407::2:1:pigeon"
        self.cookie_buyer = "61555749413"
        self.fish_biz = "10516066758:245038407::2:1:pigeon"
        self.fish_buyer = "10516066758"
        self.rows = [
            {
                "index": 0,
                "btm": "conversation_recent_0",
                "title": "叫Cookie",
                "text": "叫Cookie 重复来访 这是什么",
                "biz_id": self.cookie_biz,
                "buyer_id": self.cookie_buyer,
            },
            {
                "index": 1,
                "btm": "conversation_recent_1",
                "title": "酸菜菜菜鱼",
                "text": "酸菜菜菜鱼 商品标题是什么",
                "biz_id": self.fish_biz,
                "buyer_id": self.fish_buyer,
            },
            {
                "index": 2,
                "btm": "conversation_current_0",
                "title": "处理中会话",
                "text": "处理中会话",
                "biz_id": "999:245038407::2:1:pigeon",
                "buyer_id": "999",
            },
        ]
        self.dd = DouDian(headless=True)
        self.dd.page = FakePage(
            rows=self.rows,
            current_conversation_id=self.cookie_biz,
            current_buyer_id=self.cookie_buyer,
            active_tab="recent",
        )
        self.dd.conversation_cache = {
            self.cookie_biz: {
                "bizConversationId": self.cookie_biz,
                "pigeonUid": self.cookie_buyer,
                "nickname": "叫Cookie",
                "preview": "这是什么",
                "dom_text": "叫Cookie 重复来访 这是什么",
            },
            self.fish_biz: {
                "bizConversationId": self.fish_biz,
                "pigeonUid": self.fish_buyer,
                "nickname": "酸菜菜菜鱼",
                "preview": "商品标题是什么",
                "dom_text": "酸菜菜菜鱼 商品标题是什么",
            },
        }
        self.dd._rebuild_conversation_indexes()

    @patch("doudian.DouDian.time.sleep", return_value=None)
    def test_get_current_session_key_prefers_runtime_biz_id(self, _sleep):
        self.assertEqual(
            self.dd.get_current_session_key(),
            f"conv::biz:{self.cookie_biz}",
        )

    @patch("doudian.DouDian.time.sleep", return_value=None)
    def test_get_current_session_key_uses_current_buyer_conversation_fallback(self, _sleep):
        self.dd.page.current_conversation_id = ""
        self.dd.page.current_buyer_id = self.cookie_buyer
        self.assertEqual(
            self.dd.get_current_session_key(),
            f"conv::biz:{self.cookie_biz}",
        )

    @patch("doudian.DouDian.time.sleep", return_value=None)
    def test_switch_to_session_uses_recent_order_mapping(self, _sleep):
        self.dd.page.current_conversation_id = self.cookie_biz
        self.dd.page.current_buyer_id = self.cookie_buyer
        switched = self.dd._switch_to_session(f"conv::biz:{self.fish_biz}")
        self.assertTrue(switched)
        self.assertEqual(self.dd.page.current_conversation_id, self.fish_biz)
        self.assertIn(self.fish_biz, self.dd.conversation_row_cache)
        self.assertEqual(self.dd.conversation_row_cache[self.fish_biz]["tab"], "recent")
        self.assertEqual(self.dd.conversation_row_cache[self.fish_biz]["index"], 1)

    @patch("doudian.DouDian.time.sleep", return_value=None)
    def test_switch_to_session_can_reuse_cached_row_mapping(self, _sleep):
        self.dd.conversation_row_cache[self.cookie_biz] = {
            "tab": "recent",
            "index": 0,
            "btm": "conversation_recent_0",
            "title": "叫Cookie",
            "text": "叫Cookie 重复来访 这是什么",
            "ts": 0,
        }
        self.dd.page.current_conversation_id = self.fish_biz
        self.dd.page.current_buyer_id = self.fish_buyer
        switched = self.dd._switch_to_session(f"conv::biz:{self.cookie_biz}")
        self.assertTrue(switched)
        self.assertEqual(self.dd.page.current_conversation_id, self.cookie_biz)

    @patch("doudian.DouDian.time.sleep", return_value=None)
    def test_send_msg_to_session_rejects_non_biz_session_key(self, _sleep):
        self.dd.sendMsg = lambda msg: self.fail("sendMsg should not be called for non-biz keys")
        sent = self.dd.sendMsgToSession("name::叫Cookie", "hello", switch_back=True)
        self.assertFalse(sent)

    @patch("doudian.DouDian.time.sleep", return_value=None)
    def test_send_msg_to_session_does_not_switch_back_with_nickname_fallback(self, _sleep):
        calls = []

        def fake_send(msg):
            calls.append(("send", msg))

        self.dd.sendMsg = fake_send
        original_get_current_session_key = self.dd.get_current_session_key
        state = {"first": True}

        def fake_get_current_session_key():
            if state["first"]:
                state["first"] = False
                return "name::叫Cookie"
            return original_get_current_session_key()

        self.dd.get_current_session_key = fake_get_current_session_key
        sent = self.dd.sendMsgToSession(f"conv::biz:{self.fish_biz}", "hello", switch_back=True)
        self.assertTrue(sent)
        self.assertEqual(calls, [("send", "hello")])
        self.assertEqual(self.dd.page.current_conversation_id, self.fish_biz)

    @patch("doudian.DouDian.time.sleep", return_value=None)
    def test_get_next_new_message_prefetches_other_unread_sessions_while_returning_current(self, _sleep):
        current_batch = [{
            "index": "101",
            "who": "叫Cookie",
            "type": "text",
            "content": "这是什么",
        }]
        other_batch = [{
            "index": "201",
            "who": "酸菜菜菜鱼",
            "type": "text",
            "content": "商品标题是什么",
        }]

        def fake_read_current_unread(*args, **kwargs):
            if self.dd.get_current_session_key() == f"conv::biz:{self.cookie_biz}":
                return list(current_batch)
            return []

        def fake_get_after_switch(*args, **kwargs):
            if self.dd.get_current_session_key() == f"conv::biz:{self.fish_biz}":
                return list(other_batch)
            return []

        self.dd.readCurrentUnread = fake_read_current_unread
        self.dd._getAfterSwitchMsg = fake_get_after_switch
        self.dd._get_visible_unread_conversation_rows = lambda: [
            {
                "index": 0,
                "btm": "conversation_recent_0",
                "title": "叫Cookie",
                "text": "叫Cookie 重复来访 这是什么",
                "selected": True,
                "isUnread": True,
            },
            {
                "index": 1,
                "btm": "conversation_recent_1",
                "title": "酸菜菜菜鱼",
                "text": "酸菜菜菜鱼 商品标题是什么",
                "selected": False,
                "isUnread": True,
            },
        ]

        first_batch = self.dd.getNextNewMessage()
        self.assertEqual(first_batch, current_batch)
        self.assertEqual(len(self.dd.prefetched_session_batches), 1)
        self.assertIn(f"conv::biz:{self.fish_biz}", self.dd.prefetched_session_batch_keys)
        self.assertEqual(self.dd.page.current_conversation_id, self.cookie_biz)

        second_batch = self.dd.getNextNewMessage()
        self.assertEqual(second_batch, other_batch)
        self.assertEqual(self.dd.page.current_conversation_id, self.fish_biz)
        self.assertEqual(len(self.dd.prefetched_session_batches), 0)
        self.assertNotIn(f"conv::biz:{self.fish_biz}", self.dd.prefetched_session_batch_keys)

    @patch("doudian.DouDian.time.sleep", return_value=None)
    def test_get_next_new_message_prefetches_runtime_priority_sessions_without_unread_badge(self, _sleep):
        current_batch = [{
            "index": "101",
            "who": "叫Cookie",
            "type": "text",
            "content": "这是什么",
        }]
        other_batch = [{
            "index": "201",
            "who": "酸菜菜菜鱼",
            "type": "text",
            "content": "材质是什么",
        }]

        def fake_read_current_unread(*args, **kwargs):
            if self.dd.get_current_session_key() == f"conv::biz:{self.cookie_biz}":
                return list(current_batch)
            return []

        def fake_get_after_switch(*args, **kwargs):
            if self.dd.get_current_session_key() == f"conv::biz:{self.fish_biz}":
                return list(other_batch)
            return []

        self.dd.readCurrentUnread = fake_read_current_unread
        self.dd._getAfterSwitchMsg = fake_get_after_switch
        self.dd._get_visible_unread_conversation_rows = lambda: []
        self.dd._get_runtime_priority_session_candidates = lambda: [
            {
                "session_key": f"conv::biz:{self.fish_biz}",
                "buyer_id": self.fish_buyer,
                "countdown_time": 1,
                "unread_count": 1,
                "priority": 2,
            }
        ]

        first_batch = self.dd.getNextNewMessage()
        self.assertEqual(first_batch, current_batch)
        self.assertEqual(len(self.dd.prefetched_session_batches), 1)
        self.assertIn(f"conv::biz:{self.fish_biz}", self.dd.prefetched_session_batch_keys)
        self.assertEqual(self.dd.page.current_conversation_id, self.cookie_biz)

        second_batch = self.dd.getNextNewMessage()
        self.assertEqual(second_batch, other_batch)
        self.assertEqual(self.dd.page.current_conversation_id, self.fish_biz)
        self.assertEqual(len(self.dd.prefetched_session_batches), 0)
        self.assertNotIn(f"conv::biz:{self.fish_biz}", self.dd.prefetched_session_batch_keys)

    @patch("doudian.DouDian.time.sleep", return_value=None)
    def test_get_runtime_unreplied_sessions_prefers_wait_reply_and_countdown(self, _sleep):
        self.dd.page.runtime_wait_reply_buyers = [self.fish_buyer]
        self.dd.page.runtime_servicing_buyers = [self.cookie_buyer, self.fish_buyer]
        self.dd.page.runtime_conversations = [
            {
                "id": self.cookie_biz,
                "buyerId": self.cookie_buyer,
                "unreadCount": 1,
                "countdown": False,
                "countdownTime": 0,
                "closed": False,
            },
            {
                "id": self.fish_biz,
                "buyerId": self.fish_buyer,
                "unreadCount": 0,
                "countdown": True,
                "countdownTime": 12,
                "closed": False,
            },
        ]

        rows = self.dd.get_runtime_unreplied_sessions()
        self.assertEqual(rows[0]["session_key"], f"conv::biz:{self.fish_biz}")
        self.assertTrue(rows[0]["in_wait_reply"])
        self.assertTrue(rows[0]["countdown"])
        self.assertEqual(rows[1]["session_key"], f"conv::biz:{self.cookie_biz}")
        self.assertEqual(rows[1]["unread_count"], 1)


if __name__ == "__main__":
    unittest.main()
