import requests
from typing import Dict, List, Optional
from  utils.store import *
from  utils.tools import *

class FastGPTAPIError(Exception):
    """FastGPT API错误基类"""
    pass

class FastGPTClient:
    def __init__(
            self,
            api_url: str,
            token: str,
    ):
        """
        FastGPT客户端初始化

        :param api_url: API基础URL
        :param token: 访问令牌
        :param default_chat_id: 默认对话ID（可选）
        :param default_response_chat_item_id: 默认响应项ID（可选）
        """
        self.api_url = api_url
        self.token = token


    def send_chat_completion(
            self,
            user_name, receive_msg, message_handler,
            # messages: List[Dict[str, str]],
            # # variables: Dict[str, str],
            # chat_id: Optional[str] = None,
            response_chat_item_id: Optional[str] = None,
            stream: bool = False,
            detail: bool = False
    ) -> Dict:
        """
        发送聊天完成请求

        :param messages: 消息列表，格式为[{"role": "user", "content": "内容"}, ...]
        :param variables: 上下文变量字典
        :param chat_id: 对话ID（优先使用传入值，否则使用默认值）
        :param response_chat_item_id: 响应项ID（优先使用传入值，否则使用默认值）
        :param stream: 是否启用流式传输
        :param detail: 是否返回详细信息
        :return: API响应结果
        :raises FastGPTAPIError: 当API请求失败或返回错误时抛出
        """
        # # 生成hash userid
        print(f'用户名:{user_name}')
        user_id = generate_stable_id(user_name)
        # # 尝试获取已有的conversation_id
        conversation_id = get_conversation_id(user_id)
        print(conversation_id)
        if not conversation_id:
            conversation_id = user_id
            save_conversation_id(user_id, conversation_id)
        # 构建请求头
        headers = {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json'
        }

        # 构建请求体
        payload = {
            "chatId": conversation_id,
            "stream": stream,
            "detail": detail,
            "responseChatItemId": response_chat_item_id,
            # "variables": variables,
            "messages": [{"role": "user", "content": receive_msg}]
        }

        # 参数校验
        if not payload["chatId"]:
            raise ValueError("chatId必须提供，或在初始化时设置默认值")

        try:
            # 发送POST请求
            response = requests.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()  # 检查HTTP状态码

            # 解析响应
            result = response.json()
            replay_msg = result['choices'][0]['message']['content']
            js_replay_msg = '回复消息::' + replay_msg
            # 使用传入的回调函数处理回复消息
            message_handler(replay_msg, js_replay_msg)  # 处理并回复
            return result

        except requests.exceptions.RequestException as e:
            # 网络请求异常处理
            error_msg = f"请求失败: {str(e)}"
            if response := getattr(e, 'response', None):
                error_msg += f"\n状态码: {response.status_code}\n错误详情: {response.text}"
            raise FastGPTAPIError(error_msg) from e

        except ValueError as ve:
            # 参数校验错误
            raise FastGPTAPIError(str(ve)) from ve

# 使用示例
if __name__ == "__main__":
    try:
        client = FastGPTClient(
            api_url='https://cloud.fastgpt.cn/api/v1/chat/completions',
            token='fastgpt-wO3ThYWtwzharTxO91q54YVfLTV2ZlDPN8EDghJ38RQM1dcQ9ZihO4ynnlJ',
        )

        def message_handler(reply,js_reply):
            print('huidiao=========='+reply+']]]'+js_reply)

        response = client.send_chat_completion('www','我的上个问题是什么',message_handler)

        print("API响应：")
        print(f"ID: {response.get('id')}")
        print(f"模型: {response.get('model')}")
        print("使用情况:")
        print(f"  提示词tokens: {response['usage'].get('prompt_tokens')}")
        print(f"  回复tokens: {response['usage'].get('completion_tokens')}")
        print(f"  总tokens: {response['usage'].get('total_tokens')}")
        print("回复内容:")
        print(response['choices'][0]['message']['content'])

    except FastGPTAPIError as e:
        print(f"发生错误: {str(e)}")