import requests
import json

def send_feishu_message(url,msg):
    # url = "https://open.feishu.cn/open-apis/bot/v2/hook/add0223d-864d-46e3-b5fe-75acb65e8204"

    # 消息内容
    data = {
        "msg_type": "text",
        "content": {
            "text": msg
        }
    }

    # 设置请求头
    headers = {
        "Content-Type": "application/json"
    }

    try:
        # 发送 POST 请求
        response = requests.post(url, headers=headers, data=json.dumps(data))

        # 检查响应
        if response.status_code == 200:
            result = response.json()
            print("消息发送成功！")
            print(f"响应: {result}")
        else:
            print(f"请求失败，状态码: {response.status_code}")
            print(f"响应内容: {response.text}")

    except requests.exceptions.RequestException as e:
        print(f"请求异常: {e}")
