from playwright.sync_api import sync_playwright
import os,time,random
from .wxxd_elements import *

class WeiXiaoDian():
    # 登录地址
    chat_url =  'https://store.weixin.qq.com/shop/kf/'

    def __init__(self,headless: bool = False,storage_state_path:str='state_wxxd.json') -> None:
        self.headless = headless
        self.storage_state_path = storage_state_path
        self.viewport={ "width": 1600, "height": 900 }
        self.login_state = False
        # 记录当前聊天框最后的消息 用于下次匹配最新消息的开始点
        self.last_messages = []

    # 启动
    def launchChat(self):
        try:
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(headless=self.headless,  # 无头模式更易被检测，建议调试时关闭
                                                           args=[
                                                               '--disable-blink-features=AutomationControlled',
                                                               '--disable-infobars',  # 禁用信息栏提示
                                                               '--no-sandbox',
                                                               '--disable-setuid-sandbox',
                                                               '--disable-dev-shm-usage',
                                                               '--disable-web-security',
                                                               '--disable-features=IsolateOrigins,site-per-process',
                                                           ],
                                                           # 隐藏 "Chrome is being controlled by automated software" 提示
                                                           ignore_default_args=['--enable-automation'])
            user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36 Edg/133.0.0.0"
            kwargs = {
                "viewport": self.viewport,
                "user_agent":user_agent
            }
            if  os.path.exists(self.storage_state_path):
                kwargs["storage_state"] = self.storage_state_path

            self.context = self.browser.new_context(**kwargs)
            self.page = self.context.new_page()
            self.page.set_default_timeout(5000)
            # 修改navigator.webdriver属性以规避检测
            self.page.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                    window.navigator.chrome = {runtime: {}};
                    const originalQuery = window.navigator.permissions.query;
                    window.navigator.permissions.query = parameters => (
                        parameters.name === 'notifications' ?
                            Promise.resolve({ state: Notification.permission }) :
                            originalQuery(parameters)
                    );
                """)
            # 对WebGL指纹和Canvas输出进行干扰
            self.page.add_init_script("""
                    const originalGetParameter = WebGLRenderingContext.prototype.getParameter;
                    WebGLRenderingContext.prototype.getParameter = function(parameter) {
                        if (parameter === 37445) return 'Intel Inc.'; // UNMASKED_VENDOR_WEBGL
                        if (parameter === 37446) return 'Intel Iris OpenGL Engine'; // UNMASKED_RENDERER_WEBGL
                        return originalGetParameter.call(this, parameter);
                    };
                    
                    const canvasProto = HTMLCanvasElement.prototype;
                    const originalToDataURL = canvasProto.toDataURL;
                    canvasProto.toDataURL = function(type, quality) {
                        return originalToDataURL.call(this, type, 0.8); // 修改压缩质量干扰哈希
                    };
                """)
            # 设置随机 User-Agent
            # user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36 Edg/133.0.0.0"
            # self.page.set_extra_http_headers({"User-Agent": user_agent})
            # 导航到登录页面并执行登录逻辑
            self.page.goto(self.chat_url)
            try:
                # 例如：等待互动管理菜单项变得可交互
                self.page.wait_for_selector('.menu-list-tab', state='visible', timeout=60000)
                self.login_state = True
                print("登录成功，正在跳转...")
                # 保存当前状态（cookies, local storage等）
                self.context.storage_state(path=self.storage_state_path)
            except Exception as e:
                print("超时：未能在指定时间内找到目标元素，可能是已登录状态或页面加载出现问题。")
                self.login_state = False
                self.stopLaunch()
                # 同样地，在这里也可以选择清空 storage_state
                if os.path.exists(self.storage_state_path):
                    os.remove(self.storage_state_path)
                    print(f"由于其他异常，已删除存储状态文件: {self.storage_state_path}")

        except Exception as e:
            print('Exception exe')

    # 关闭
    def stopLaunch(self):
        # 关闭浏览器（必须先执行）
        if self.browser:
            self.browser.close()
            self.browser = None  # 清理引用

        # 安全关闭 Playwright
        if self.playwright:
            try:
                # 检查是否已停止（避免重复调用）
                if hasattr(self.playwright, "is_stopped") and self.playwright.is_stopped():
                    return

                self.playwright.stop()
            except Exception as e:
                # 仅忽略 "Event loop is closed" 错误
                if "Event loop is closed" not in str(e):
                    raise
            finally:
                self.playwright = None  # 确保清理

    # 发送信息
    def sendMsg(self,msg):
        if not msg:
            return
        # 从最外层的 .chat-input 开始定位到 textarea 输入框
        chat_input = self.page.query_selector('.chat-input')
        if chat_input:
            text_area = chat_input.query_selector('textarea.text-area')
            if text_area:
                # 在输入框中输入"谢谢"
                text_area.fill(msg)
                time.sleep(random.uniform(1, 2))
                # 模拟按下回车键发送消息
                text_area.press("Enter")

    # 获取下一条最新消息
    def getNextNewMessage(self,checkRedMessage = True):
        # 如果停留在当前对话框 先判断当前对话框是否有新消息
        new_msgs = self.readCurrentUnread()
        if  new_msgs:
            return new_msgs

        if not checkRedMessage:
            return []
        # 查找所有用户会话项
        session_wraps = self.page.locator('.session-item-container')
        # 判断对话列表是否有新消息 有的话 取第一个
        for index in range(session_wraps.count()):
            session_wrap = session_wraps.nth(index)

            # 获取 .dot 元素（如果有），这代表了未读消息的数量
            dot_locator = session_wrap.locator('.unread-badge.bold')
            if dot_locator.count() > 0:
                unread_count_text = dot_locator.first.text_content().strip()
                if unread_count_text.isdigit():  # 确保是数字
                    unread_count = int(unread_count_text)
                    # 获取用户名
                    name_locator = session_wrap.locator('.user-nickname')
                    user_name = name_locator.first.text_content().strip()
                    # 如果找到有未读消息的用户，点击其头像
                    avatar_locator = session_wrap.locator('.user-avatar')
                    avatar_locator.click()
                    time.sleep(2)
                    # 将用户名和未读消息数添加到列表中
                    friend_msg= self._getCurrentFriendMsg()
                    # #这一步一定有 不然进来之后 模型在回复的时候 查看不了同时发送过来的消息了
                    self.last_messages = self._getLastMessages(friend_msg)
                    return friend_msg[-unread_count:]
        return []

    def _getLastMessages(self, messages, count=5):
        """获取最后所有的朋友消息"""
        last_messages =  messages[-count:]  # 返回最后最多五条消息，如果是空列表则返回空列表
        # 提取每条消息的 content 字段值
        contents = [msg.content for msg in last_messages if 'content' in msg]
        return contents

    def _getCurrentUserName(self):
        # 等待页面加载完成并找到包含用户昵称的元素
        user_nickname_element = self.page.query_selector('.chat-title .left .chat-customer-name.bold')
        user_nickname = ''
        if user_nickname_element:
            user_nickname = user_nickname_element.text_content().strip()
            # print(f"用户昵称: {user_nickname}")

        return user_nickname


    def _getCurrentFriendMsg(self):
        try:
            # # 查找所有朋友消息并存入列表
            friend_messages = []
            # 查找所有可能包含消息的容器
            msg_containers = self.page.query_selector_all('div.msg, div.msg.show-date')

            for container in msg_containers:
                # 在每个容器中查找用户的消息项
                user_msg_items = container.query_selector_all('div.message-item.flex.items-center:not(.justify-end)')
                username = self._getCurrentUserName()
                for msg_item in user_msg_items:
                    # 检查是否为商品卡片信息
                    order_msg_block = msg_item.query_selector('a.order-msg-block')
                    if order_msg_block:
                        product_name_element = order_msg_block.query_selector('p')
                        if product_name_element:
                            product_name = product_name_element.text_content()
                            friend_messages.append(Message('card',f'我想咨询产品:[{product_name}]',username))
                            # print(f'商品名称: 我想咨询产品:[{product_name}]')
                            continue
                    # 检查是否为图片消息
                    img_element = msg_item.query_selector('img[data-type="image"]')
                    if img_element:
                        img_src = img_element.get_attribute('src')
                        friend_messages.append(Message('image', img_src, username))
                        # print(f'图片: {img_src}')
                        continue
                    # 如果不是商品卡片，则尝试获取纯文本消息
                    text_msg = msg_item.query_selector('.text-msg.bg-user')
                    if text_msg:
                        message_text = text_msg.text_content().strip()
                        friend_messages.append(Message('text',message_text,username))
                        # print(f'用户消息: {message_text}')

            return  friend_messages
        except:
            pass


    def readCurrentUnread(self):
        new_messages = []
        # 获取当前对话框所有朋友消息
        friend_messages = self._getCurrentFriendMsg()

        if not friend_messages:
            return  new_messages
        # 获取当前最后的朋友消息（最多五条）
        current_last_messages = self._getLastMessages(friend_messages)

        if not self.last_messages:
            self.last_messages = self._getLastMessages(friend_messages)

        if current_last_messages != self.last_messages:
            print("\n检测到新的消息:")
            # 如果 last_messages 非空，则尝试从 friend_messages 末尾开始匹配
            if self.last_messages:
                # 计算需要比较的起始索引，确保不会出现负数索引
                start_index = len(friend_messages) - len(self.last_messages)
                # 确保 start_index 不为负数，避免列表索引越界错误
                if start_index >= 0:
                    # 检查从 friend_messages 末尾开始是否有与 self.last_messages 匹配的部分
                    for i in range(start_index, -1, -1):
                        # 提取可能匹配的子列表
                        friend_messages_content = [msg.content for msg in friend_messages if 'content' in msg]
                        sub_messages = friend_messages_content[i:i + len(self.last_messages)]

                        # 检查是否匹配
                        if sub_messages == self.last_messages:
                            #收集在匹配部分之后的所有消息作为新消息
                            for k in range(i + len(self.last_messages), len(friend_messages)):
                                new_messages.append(friend_messages[k])

                            break

            # 更新最后的消息为当前的最后消息
            self.last_messages = current_last_messages
        else:
            print("\n没有新的消息。")
        # print('# =============')
        # print(f" - {new_messages}")  # 打印每条朋友消息
        return new_messages

    #刷新页面
    def pageReload(self):
        self.page.reload()
        # 确保页面加载完成
        self.page.wait_for_load_state('load')
        self.page.evaluate(f"window.scrollBy(0, {random.randint(-10, 10)})")