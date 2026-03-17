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
                "servicingBuyers": [],
                "waitReplyBuyers": [],
                "overThreeBuyers": [],
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


if __name__ == "__main__":
    unittest.main()
