from playwright.sync_api import sync_playwright
import os,time,random
from .sph_elements import *

class ShiPinHao():
    # 登录地址
    login_url = 'https://channels.weixin.qq.com/login.html'
    chat_url =  'https://channels.weixin.qq.com/platform/private_msg'

    def __init__(self,headless: bool = False,storage_state_path:str='state_sph.json') -> None:
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
            self.page.goto('https://channels.weixin.qq.com/platform/private_msg')
            try:
                # 例如：等待互动管理菜单项变得可交互
                self.page.wait_for_selector('.finder-ui-desktop-menu__name', state='visible', timeout=60000)
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

    def getAllNewUnreadUserMsg(self):
        """
        返回示例 [{'name': '小能手', 'count': 2}, {'name': '一个程序', 'count': 1}]
        :return:
        """
        # 查找所有用户会话项
        session_wraps = self.page.locator('.session-wrap')
        users_with_new_messages = []

        for index in range(session_wraps.count()):
            session_wrap = session_wraps.nth(index)

            # 获取 .dot 元素（如果有），这代表了未读消息的数量
            dot_locator = session_wrap.locator('.dot')
            if dot_locator.count() > 0:
                unread_count_text = dot_locator.first.text_content().strip()
                if unread_count_text.isdigit():  # 确保是数字
                    unread_count = int(unread_count_text)

                    # 获取用户名
                    name_locator = session_wrap.locator('.name')
                    user_name = name_locator.first.text_content().strip()

                    # 将用户名和未读消息数添加到列表中
                    users_with_new_messages.append({"name": user_name, "count": unread_count})

        return users_with_new_messages
    # 发送信息
    def sendMsg(self,msg):
        if not msg:
            return
        # 使用更具体的选择器找到<footer>下的<textarea>
        self.page.fill('.footer .content textarea[name="textarea"]', msg)
        time.sleep(random.uniform(1, 2))
        # 找到发送按钮并点击
        self.page.click('.footer .weui-desktop-btn_wrp button:has-text("发送")')

    # 获取下一条最新消息
    def getNextNewMessage(self,checkRedMessage = True):
        # 如果停留在当前对话框 先判断当前对话框是否有新消息
        new_msgs = self.readCurrentUnread()
        if  new_msgs:
            return new_msgs

        if not checkRedMessage:
            return []
        # 查找所有用户会话项
        session_wraps = self.page.locator('.session-wrap')
        # 判断对话列表是否有新消息 有的话 取第一个
        for index in range(session_wraps.count()):
            session_wrap = session_wraps.nth(index)

            # 获取 .dot 元素（如果有），这代表了未读消息的数量
            dot_locator = session_wrap.locator('.dot')
            if dot_locator.count() > 0:
                unread_count_text = dot_locator.first.text_content().strip()
                if unread_count_text.isdigit():  # 确保是数字
                    unread_count = int(unread_count_text)
                    # 获取用户名
                    name_locator = session_wrap.locator('.name')
                    user_name = name_locator.first.text_content().strip()
                    # 如果找到有未读消息的用户，点击其头像
                    avatar_locator = session_wrap.locator('.avatar')
                    avatar_locator.click()
                    time.sleep(2)
                    # 将用户名和未读消息数添加到列表中
                    friend_msg= self._getCurrentFriendMsg()
                    #这一步一定有 不然进来之后 模型在回复的时候 查看不了同时发送过来的消息了
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
        user_nickname_element = self.page.query_selector('.session-dialog .header .left span')
        user_nickname = ''
        if user_nickname_element:
            user_nickname = user_nickname_element.text_content().strip()
            # print(f"用户昵称: {user_nickname}")

        return user_nickname


    def _getCurrentFriendMsg(self):
        # 定位唯一一个聊天会话内容包裹器
        session_wrapper = self.page.locator('.session-content-wrapper')

        if session_wrapper.count() == 0:
            print("未找到任何聊天会话内容包裹器。")
            return

        session_wrapper = session_wrapper.first

        # 查找所有朋友消息并存入列表
        friend_messages = []
        # 获取所有的内容块
        content_blocks = self.page.query_selector_all('.content-left.content')
        username = self._getCurrentUserName()

        for block in content_blocks:
            # 尝试获取图片信息
            img_element = block.query_selector('.msg-img')
            if img_element:
                img_src = img_element.get_attribute('src')
                friend_messages.append(Message('img','[图片]',username))

            # 尝试获取文本信息
            text_content = block.query_selector('.message-plain')
            if text_content:
                friend_messages.append(Message('text',text_content.text_content().strip(),username))

        return  friend_messages

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

    def clickAutoSwitchTabs(self):
        # 查找当前激活的选项卡
        current_tab = self.page.query_selector('.weui-desktop-tab__nav.weui-desktop-tab__nav_current a')

        if not current_tab:
            print("无法找到当前激活的选项卡")

        current_tab_text = current_tab.text_content().strip()
        # print(f"当前激活的选项卡: {current_tab_text}")

        if "私信" in current_tab_text:
            # 当前激活的是“私信”，接下来点击“打招呼消息”
            target_tab_text = "打招呼消息"
        else:
            # 当前激活的是“打招呼消息”，接下来点击“私信”
            target_tab_text = "私信"

        # 点击目标选项卡
        target_tab = self.page.query_selector(f'.weui-desktop-tab__nav a:has-text("{target_tab_text}")')
        if target_tab:
            target_tab.click()
            # print(f"点击了 {target_tab_text}")

    def clickPrivateLetter(self):
        private_message_tab = self.page.query_selector('.weui-desktop-tab__nav a:has-text("私信")')
        if private_message_tab:
            private_message_tab.click()
            print("Clicked on 私信")

    def clickGreet(self):
        greeting_message_tab = self.page.query_selector('.weui-desktop-tab__nav a:has-text("打招呼消息")')
        if greeting_message_tab:
            greeting_message_tab.click()
            print("Clicked on 打招呼消息")

    #刷新页面
    def pageReload(self):
        self.page.reload()
        # 确保页面加载完成
        self.page.wait_for_load_state('load')
        self.page.evaluate(f"window.scrollBy(0, {random.randint(-10, 10)})")