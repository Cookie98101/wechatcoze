import os
from http import HTTPStatus
from dashscope import Application
from  utils.store import *
from  utils.tools import *

class BalianUtil():

    def __init__(self, api_key, app_id) -> None:
        self.app_id = app_id
        self.api_key = api_key

    def send_message_and_poll(self, user_name, receive_msg, message_handler):
        try:
            # # 生成hash userid
            print(f'用户名:{user_name}')
            user_id = generate_stable_id(user_name)
            # # 尝试获取已有的conversation_id
            conversation_id = get_conversation_id(user_id)
            print(conversation_id)

            kwargs = {
                "api_key": self.api_key,
                "app_id": self.app_id,
                "prompt": receive_msg
            }
            if conversation_id:
                kwargs["session_id"] = conversation_id

            response = Application.call(**kwargs)
            if response.status_code != HTTPStatus.OK:
                raise Exception('百炼调用错误')
            else:
                replay_msg = response.output.text.strip()
                js_replay_msg = '回复消息::' + replay_msg

                # 使用传入的回调函数处理回复消息
                message_handler(replay_msg, js_replay_msg)  # 处理并回复
                # 如果没有conversation_id，则保存
                if not conversation_id:
                    save_conversation_id(user_id, response.output.session_id)

        except Exception as e:
            print(e)
            delete_conversation_id(user_id)
            raise