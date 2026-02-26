from cozepy import Coze, TokenAuth, Message, ChatStatus
from utils.store import *
from utils.tools import *

CONVERSATION_TTL_SECONDS = 30 * 60

class CozeUtil():

    def __init__(self, token, base_url, bot_id) -> None:
        self.coze = Coze(auth=TokenAuth(token), base_url=base_url)
        self.bot_id = bot_id

    def send_message_and_poll(self, user_name, receive_msg, message_handler):
        """
        发送消息给Coze API，并轮询获取回复。

        :param user_id: 用户ID
        :param receive_msg: 接收到的消息内容
        :param message_handler: 回调函数，用于处理回复消息（包括发送消息和更新UI）
        :param conversation_id: 会话ID（可选）
        :return: None
        """
        try:
            # # 生成hash userid
            print(f'用户名:{user_name}')
            user_id = generate_stable_id(user_name)
            # # 尝试获取已有的conversation_id
            conversation_id = get_conversation_id(user_id, ttl_seconds=CONVERSATION_TTL_SECONDS)
            print(conversation_id)

            kwargs = {
                "bot_id": self.bot_id,
                "user_id": user_id,
                "additional_messages": [Message.build_user_question_text(receive_msg)]
            }
            if conversation_id:
                kwargs["conversation_id"] = conversation_id

            chat_poll = self.coze.chat.create_and_poll(**kwargs)

            # Coze 在部分场景会返回多个 answer，统一只取最后一个，避免同一轮重复回复。
            answers = [m for m in chat_poll.messages if m.type == 'answer' and (m.content or '').strip()]
            if answers:
                final_answer = answers[-1]
                replay_msg = final_answer.content.strip()
                js_replay_msg = '回复消息::' + replay_msg

                # 使用传入的回调函数处理回复消息
                message_handler(replay_msg, js_replay_msg)  # 处理并回复

                # 更新会话存活时间
                save_conversation_id(user_id, final_answer.conversation_id)
        except Exception as e:
            print(e)
            # 检查'e'是否有'code'属性
            if hasattr(e, 'code'):
                if e.code == 4200:
                    delete_conversation_id(user_id)
            raise
