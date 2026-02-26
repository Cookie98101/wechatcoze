import sys
import os
import time
# from llm import GPT
from wechatauto.wxauto import WeChat
from cozepy import Coze, TokenAuth, Message, ChatStatus
from  utils.tools import *
from  utils.store import *
# from dotenv import load_dotenv


import os
from http import HTTPStatus
from dashscope import Application
def call_with_session():
    kwargs = {
        'api_key':'sk-aa1556b1b7b94a308f7dd25988d9a7dc',
        'app_id':'da7f6c89876a4749a803c95f86afeb18',
        'prompt':'你是谁？'
    }
    response = Application.call(**kwargs)

    if response.status_code != HTTPStatus.OK:
        print(f'request_id={response.request_id}')
        print(f'code={response.status_code}')
        print(f'message={response.message}')
        print(f'请参考文档：https://help.aliyun.com/zh/model-studio/developer-reference/error-code')
        return response
    kwargs1 = {
        'api_key':'sk-aa1556b1b7b94a308f7dd25988d9a7dc',
        'app_id':'da7f6c89876a4749a803c95f86afeb18',
        'prompt':'你是谁？',
        'session_id':response.output.session_id
    }
    responseNext = Application.call(**kwargs1)  # 上一轮response的session_id

    if responseNext.status_code != HTTPStatus.OK:
        print(f'request_id={responseNext.request_id}')
        print(f'code={responseNext.status_code}')
        print(f'message={responseNext.message}')
        print(f'请参考文档：https://help.aliyun.com/zh/model-studio/developer-reference/error-code')
    else:
        print('%s\n session_id=%s\n' % (responseNext.output.text, responseNext.output.session_id))
        # print('%s\n' % (response.usage))

if __name__ == '__main__':
    call_with_session()

# 读取相关环境变量
# load_dotenv()

# gpt = GPT(
#     api_key = os.getenv('OPENAI_API_KEY'),
#     base_url = os.getenv('OPENAI_BASE_URL'),
#     prompt="你是一个智能助手，用于回复人们的各种问题"
# )
# token = 'pat_oRHv4QFrCEwL0fnEBX9nDMKt7ATO9uQzLBJIO3m1TOOLNxIlIdUuaYNvvME1T3mG'
# coze_api_base = "https://api.coze.cn"
# bot_id = "7473757213119578147"
#
# coze = Coze(auth=TokenAuth(token), base_url=coze_api_base)
#
# user_id = generate_stable_id('Acy🤗返11返小dd能手')
#
# try:
#     while True:
#         # 获取用户输入
#         msg = input("请输入消息 ('exit'退出): ")
#
#         if msg.lower() == 'exit':
#             print("程序结束.")
#             break
#
#         # 尝试获取已有的conversation_id
#         conversation_id = get_conversation_id(user_id)
#         print(conversation_id)
#
#         # 动态构建kwargs字典，根据conversation_id是否存在决定是否包含它
#         kwargs = {
#             "bot_id": bot_id,
#             "user_id": user_id,
#             "additional_messages": [Message.build_user_question_text(msg)]
#         }
#         if conversation_id:
#             kwargs["conversation_id"] = conversation_id
#         # 发送消息并轮询结果
#         chat_poll = coze.chat.create_and_poll(**kwargs)
#
#         # 输出机器人的回复
#         for message in chat_poll.messages:
#             if message.type == 'answer':
#                 print('==========')
#                 print(f"Conversation ID: {message.conversation_id}")
#                 print(f"Content: {message.content}")
#                 if not conversation_id:
#                     save_conversation_id(user_id, message.conversation_id)
# except Exception as e:
#     print('error========')
#     print(e)
#     # 检查'e'是否有'code'属性
#     if hasattr(e, 'code'):
#         if e.code == 4200:
#             delete_conversation_id(user_id)
#     else:
#         print("No 'code' attribute in the exception.")
