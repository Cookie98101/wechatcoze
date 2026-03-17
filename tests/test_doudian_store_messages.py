import unittest

from doudian.DouDian import DouDian


class DouDianStoreMessageTests(unittest.TestCase):
    def setUp(self):
        self.dd = DouDian(headless=True)
        self.dd._getCurrentUserName = lambda: "叫Cookie"

    def test_convert_store_messages_extracts_product_card_without_rights_noise(self):
        snapshot = {
            "conversationId": "61555749413:245038407::2:1:pigeon",
            "buyerId": "61555749413",
            "selfId": "195060773692439",
            "serviceEntityId": "245038407",
            "serviceReadIndex": "1773640928271198",
            "messages": [
                {
                    "id": "template-card",
                    "serverId": "1859797310735418",
                    "indexInConversation": "1773640929735718",
                    "sender": "61555749413",
                    "content": "[商品]",
                    "ext": {
                        "type": "template_card",
                        "sender_role": "1",
                        "goods_id": "3790684689153523789",
                        "static_data": (
                            '{"sale_goods":[{"product_id":"3790684689153523789",'
                            '"product_name":"新中式吸水餐垫茶垫硅藻泥沥水中国风桌垫厨房台面防滑茶水茶杯垫",'
                            '"current_price":{"price":"5.80"},'
                            '"price":"10.80"}],'
                            '"rights_v3":{"multi_rights":{"rights":[{"content":"7天无理由退货"},{"content":"极速退款"}]}}}'
                        ),
                    },
                    "type": 1000,
                }
            ],
        }

        all_msgs = self.dd._convert_store_messages(snapshot)
        self.assertEqual(len(all_msgs["customer_messages"]), 1)
        card_msg = all_msgs["customer_messages"][0]
        self.assertEqual(card_msg["type"], "card")
        self.assertIn("我要咨询商品名称:新中式吸水餐垫茶垫硅藻泥沥水中国风桌垫厨房台面防滑茶水茶杯垫", card_msg["content"])
        self.assertIn("价格:5.80", card_msg["content"])
        self.assertIn("商品ID:3790684689153523789", card_msg["content"])
        self.assertNotIn("7天无理由退货", card_msg["content"])
        self.assertNotIn("极速退款", card_msg["content"])

    def test_convert_store_messages_extracts_user_enter_product_name(self):
        snapshot = {
            "conversationId": "61555749413:245038407::2:1:pigeon",
            "buyerId": "61555749413",
            "selfId": "195060773692439",
            "serviceEntityId": "245038407",
            "serviceReadIndex": "0",
            "messages": [
                {
                    "id": "system-enter",
                    "serverId": "1859797308747851",
                    "indexInConversation": "1773640928271198",
                    "sender": "61555749413",
                    "content": "用户正在查看商品",
                    "ext": {
                        "type": "user_enter_from_goods",
                        "sender_role": "1",
                        "goods_id": "3790684689153523789",
                    },
                    "type": 1000,
                },
                {
                    "id": "template-enter",
                    "serverId": "1859797309848604",
                    "indexInConversation": "1773640929163225",
                    "sender": "245038407",
                    "content": "用户正在查看商品",
                    "ext": {
                        "type": "template_card",
                        "sender_role": "2",
                        "goods_id": "3790684689153523789",
                        "static_data": (
                            '{"b_goods":[{"product_id":"3790684689153523789",'
                            '"product_name":"新中式吸水餐垫茶垫硅藻泥沥水中国风桌垫厨房台面防滑茶水茶杯垫",'
                            '"current_price":{"price":"5.80"}}]}'
                        ),
                    },
                    "type": 1000,
                },
            ],
        }

        all_msgs = self.dd._convert_store_messages(snapshot)
        self.assertEqual(len(all_msgs["customer_messages"]), 1)
        system_msg = all_msgs["customer_messages"][0]
        self.assertEqual(system_msg["type"], "from_info")
        self.assertEqual(system_msg["source"], "system")
        self.assertIn("新中式吸水餐垫茶垫硅藻泥沥水中国风桌垫厨房台面防滑茶水茶杯垫", system_msg["content"])

    def test_convert_store_messages_filters_system_access_notice(self):
        snapshot = {
            "conversationId": "61555749413:245038407::2:1:pigeon",
            "buyerId": "61555749413",
            "selfId": "195060773692439",
            "serviceEntityId": "245038407",
            "serviceReadIndex": "0",
            "messages": [
                {
                    "id": "system-access",
                    "serverId": "1859797308747851",
                    "indexInConversation": "1773640928271198",
                    "sender": "61555749413",
                    "content": "客服王德华时尚好货店接入",
                    "ext": {
                        "sender_role": "1",
                    },
                    "type": 1000,
                },
                {
                    "id": "customer-text",
                    "serverId": "1859797308747852",
                    "indexInConversation": "1773640928271199",
                    "sender": "61555749413",
                    "content": "这是什么",
                    "ext": {
                        "sender_role": "1",
                    },
                    "type": 1000,
                },
            ],
        }

        all_msgs = self.dd._convert_store_messages(snapshot)
        self.assertEqual(len(all_msgs["customer_messages"]), 1)
        self.assertEqual(all_msgs["customer_messages"][0]["content"], "这是什么")


if __name__ == "__main__":
    unittest.main()
