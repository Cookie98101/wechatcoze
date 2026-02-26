from playwright.sync_api import sync_playwright
import os,time,random
from utils.tools import *

class PinDuoDuo():
    # 登录地址
    chat_url =  'https://mms.pinduoduo.com/chat-merchant/'

    def __init__(self,headless: bool = False,storage_state_path:str='state_pdd.json') -> None:
        self.headless = headless
        self.storage_state_path = storage_state_path
        self.viewport={ "width": 1280, "height": 600 }
        self.login_state = False
        # 记录当前聊天框最后的消息 用于下次匹配最新消息的开始点
        self.last_messages = []

    # 启动
    def launchChat(self,config_checked_pwd_login,config_username,config_pwd):
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
            self.page.goto(self.chat_url, wait_until="domcontentloaded")
            try:
                # 立即检查元素是否存在
                element = self.page.wait_for_selector('.conv-tab-wrapper', timeout=3000)
                if element:
                    print("已登录状态，直接找到元素")
                    self.login_state = True
                    self.context.storage_state(path=self.storage_state_path)
            except Exception as e:
                if config_checked_pwd_login==1 and config_username and config_pwd:
                    print('用户名密码登录==================')
                    self.login_by_pwd(config_username,config_pwd)
                    self.page.wait_for_selector('.conv-tab-wrapper', state='visible', timeout=120000)
                    self.login_state = True
                    self.context.storage_state(path=self.storage_state_path)
                else:
                    # 例如：等待互动管理菜单项变得可交互
                    self.page.wait_for_selector('.conv-tab-wrapper', state='visible', timeout=120000)
                    self.login_state = True
                    print("登录成功，正在跳转...")
                    # 保存当前状态（cookies, local storage等）
                    self.context.storage_state(path=self.storage_state_path)

        except Exception as e:
            print('Exception exe')

    def login_by_pwd(self,config_username,config_pwd):
        try:
            # 使用精确文本定位，避免误匹配
            self.page.get_by_text("账号登录", exact=True).click(timeout=10000)
            print("✅ 已切换到账号登录模式")
        except Exception as e:
            print("⚠️ 切换账号登录失败，尝试通过class定位")
            # 备用方案：通过class定位（当文本定位失败时）
            self.page.locator('div.Common_item__3diIn.Common_checked__1oLdj').click()

        # 4. 输入用户名（使用ID定位，最可靠）
        self.page.fill("#usernameId", config_username)  # 替换为实际用户名

        # 5. 输入密码（使用ID定位）
        self.page.fill("#passwordId", config_pwd)  # 替换为实际密码

        # 6. 点击登录按钮（使用精确文本定位）
        self.page.get_by_text("登录", exact=True).click()

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

    # 转接其他人
    def transferOther(self,other,single_transfer):
        # 定位并点击“转移会话”按钮
        # 根据提供的HTML结构，“转移会话”按钮位于包含特定类名的div内
        transfer_session_button = self.page.locator('.transfer-chat-wrap')
        transfer_session_button.click()
        # 等待对话框加载完成
        self.page.wait_for_selector('.el-dialog__body', state='visible')

        is_find_transfer = False

        for name in other:
            single_transfer(name)
            # 定位搜索框并输入'wjy'
            search_box = self.page.locator('.el-dialog__body .search-box .el-input__inner')
            search_box.fill(name)

            # 假设搜索结果会动态加载，可能需要等待一段时间或者监听某个事件
            self.page.wait_for_timeout(1000)  # 简单等待1秒作为示例

            # 尝试定位第一个搜索结果的“转移”按钮
            try:
                first_result_transfer_buttons = self.page.locator('.el-table__row .item-btn-transfer')
                if first_result_transfer_buttons.count() > 0:
                    # 如果找到了至少一个“转移”按钮，则点击第一个
                    first_result_transfer_buttons.nth(0).click()
                    # 等待“其他转移原因”编辑框显示
                    visible_popover = self.page.locator(
                        'div.el-popover.el-popper.none-padding-popover.transform-list-popover'
                        '[x-placement="bottom"]:not([style*="display: none"])'
                    )
                    # 等待弹框完全可见
                    visible_popover.wait_for(state='visible', timeout=10000)
                    # 选择“其他转移原因”
                    other_reason_input = visible_popover.locator('.transfer-remark-edit .el-input__inner')
                    custom_reason_text = '智能触发'
                    other_reason_input.fill(custom_reason_text)
                    time.sleep(1)
                    # 确认输入的内容
                    if other_reason_input.input_value() == custom_reason_text:
                        # 点击对应的发送按钮（确保不是禁用状态）
                        send_button = visible_popover.locator('.edit-submit-span').nth(0)
                        if 'disabled' not in send_button.get_attribute('class'):
                            send_button.click()
                            is_find_transfer = True
                        else:
                            raise Exception("发送按钮不可用，请检查是否正确填写了其他转移原因。")
                    else:
                        raise Exception("未能正确填充自定义转移原因。")
                    break
                else:
                    single_transfer('未找到'+name)
                    time.sleep(0.5)
            except Exception as e:
                # 点击坐标 (100, 200) 关闭弹框
                self.page.mouse.click(10, 10)
                raise Exception(f"查找或点击转接人时发生错误: {e}")
        #   如果未找到直接回复
        if not is_find_transfer:
            # 点击坐标 (100, 200) 关闭弹框
            self.page.mouse.click(10, 10)
            random_suffix = str(random.randint(1000, 9999))  # 生成4位随机数
            new_error = f"抱歉,转交失败{random_suffix}"
            self.sendMsg(new_error)

    # 发送信息
    def sendMsg(self,msg):
        if not msg:
            return
        # 查找图片
        msg,urls = replace_image_tag_with_word(msg)
        if urls:
            # 直接查找指定的文件上传输入框
            input_element_locator = self.page.locator('.reply-header input[type="file"][accept*="image"]')
            try:
                # 获取匹配的元素数量
                input_element_count = input_element_locator.count()
                if msg:
                    self.sendBtnMsg(msg)
                    time.sleep(1)
                if input_element_count > 0:
                    for url in urls:
                        # 清除已有文件（如果支持）
                        try:
                            input_element_locator.first.set_input_files([])  # 尝试清除文件
                        except Exception as e:
                            raise Exception("Failed to clear file input:", str(e))
                        # 设置要上传的图片路径
                        input_element_locator.first.set_input_files(r'{}'.format(url))
                        # 等待上传完成（根据实际需要调整时间）
                        self.page.wait_for_timeout(5000)
                        print("File path set for upload.")
                        # 模拟按下 Enter 键
                        self.page.keyboard.press('Enter')
                        time.sleep(1)
            except Exception as e:
                self.sendBtnMsg('图片未找到')
                raise Exception("图片路径不对或者没找到上传按钮")
        else:
            self.sendBtnMsg(msg)

    def sendBtnMsg(self,msg):
        # 使用更具体的选择器找到<footer>下的<textarea>
        # 使用链式选择器方法，从外层逐步向内层查找
        textarea = self.page.query_selector('.reply-input').query_selector('.textarea-rect').query_selector('textarea#replyTextarea')
        if textarea:
            # 输入msg
            textarea.fill(msg)
        else:
            raise Exception("输入框未找到.")
        time.sleep(random.uniform(1, 2))
        # 找到发送按钮并点击
        # 查找并点击发送按钮
        send_button = self.page.query_selector('.reply-footer .send-btn')
        if send_button:
            send_button.click()
        else:
            raise Exception("发送按钮未找到.")

    # 检查刚启动的弹框 有就关掉
    def checkPop(self):
        parent_pickupServiceGuide = self.page.query_selector('.pickupServiceGuide')
        if parent_pickupServiceGuide:
            close_icon = parent_pickupServiceGuide.query_selector('.close-icon .el-icon-close')
            if close_icon:
                close_icon.click()
                time.sleep(1)
                print("已点击关闭按钮pickupServiceGuide")
            else:
                print("未找到关闭按钮")
        else:
            print("未找到父元素pickupServiceGuide")

        parent_installerContact = self.page.query_selector('.installerContact')
        if parent_installerContact:
            close_icon = parent_installerContact.query_selector('.close-icon .el-icon-close')
            if close_icon:
                close_icon.click()
                time.sleep(1)
                print("已点击关闭按钮installerContact")
            else:
                print("未找到关闭按钮")
        else:
            print("未找到父元素installerContact")

        #  检测回复率提醒弹框
        modal = self.page.locator('div.content-modal:has-text("账号回复异常预警")')
        if modal.count() > 0:
            cancel_button = modal.locator('button:has-text("取消")')
            cancel_button.click(timeout=0)

        # 使用 XPath 定位包含特定文本的 modal-box
        modal_box = self.page.query_selector(
            "xpath=//div[@class='modal-box' and contains(., '浏览器未开启通知')]"
        )
        # 检查弹框
        if modal_box:
            # 在 modal-box 内查找 .cancel 按钮
            cancel_button = modal_box.query_selector(".btn-box .cancel")

            if cancel_button:
                cancel_button.click()
                time.sleep(1)
                print("已点击 '今天不再提示' 按钮")
            else:
                print("未找到 '今天不再提示' 按钮")
        else:
            print("未找到符合条件的 modal-box")
        #检查账号在别处登录
        modal_other = self.page.locator('div.layer-box:has-text("网络出现问题，请检查后刷新")')
        if modal_other.count() > 0:
            refresh_button = modal_other.locator('span:has-text("刷新")')
            refresh_button.click(timeout=0)

        #检查服务态度提醒
        repeat_send = self.page.locator('div.repeat-interceptor-popup:has-text("服务态度提醒")')
        if repeat_send.count() > 0:
            goon_btn = repeat_send.locator('span:has-text("继续发送")')
            goon_btn.click(timeout=0)

        #检查转移失败
        fail_transefer = self.page.locator('div.transfer-detail-dialog:has-text("正在处理此对话点击【转移会话】可将会话转移至当前账号")')
        if fail_transefer.count() > 0:
            self.pageReload()

        #检查是否跳转到登录页
        skip_login = self.page.locator('div.login-info-section:has-text("扫码登录")')
        if skip_login.count() > 0:
            raise Exception('掉线跳转到登录页')

    # 获取下一条最新消息
    def getNextNewMessage(self,checkRedMessage = True,config_checked_greetings=0,config_greetings=''):
        # 检查弹框
        self.checkPop()
        # 如果停留在当前对话框 先判断当前对话框是否有新消息
        new_msgs = self.readCurrentUnread()
        if  new_msgs:
            return new_msgs

        if not checkRedMessage:
            return []
        # 查找第一个 chat-list 下的所有 chat-item
        chat_items = self.page.locator('.chat-list-box.custom-scroll .chat-list:first-child .chat-item')

        # 判断对话列表是否有新消息 有的话 取第一个
        for index in range(chat_items.count()):
            session_wrap = chat_items.nth(index)

            # 获取 .dot 元素（如果有），这代表了未读消息的数量
            dot_locator = session_wrap.locator('.chat-portrait i')
            # 只有红色 没有红点的情况
            dot_locator_unwatch = session_wrap.locator('.un-watch')
            if dot_locator.count() > 0 or dot_locator_unwatch.count()>0:
                session_wrap.click()
                time.sleep(0.5)  # 等待页面加载
                # 加装未读消息
                new_msgs = self._getAfterSwitchMsg(config_checked_greetings,config_greetings)
                if  new_msgs:
                    print('新框消息=========')
                    print(new_msgs)
                    return new_msgs
                # 可以在这里添加点击头像等操作
                # avatar_images = session_wrap.locator('.chat-portrait img')
                # if avatar_images.count() > 0:
                #     first_avatar_image = avatar_images.nth(0)
                #     first_avatar_image.click()
                #     time.sleep(2)  # 等待页面加载
                #     # 加装未读消息
                #     new_msgs = self._getAfterSwitchMsg()
                #     if  new_msgs:
                #         print('新框消息=========')
                #         print(new_msgs)
                #         return new_msgs
        return []

    # 点击新对话 加载未读消息 加载的原理就是找到我的消息的最后一个的之后的都是未读消息
    # 加载完需要更新 last_messages
    def _getAfterSwitchMsg(self,config_checked_greetings,config_greetings):
        all_msgs = self._getAllCurrentMsg()
        my_msgs = all_msgs['my_messages']
        friend_msgs =  all_msgs['customer_messages']
        # 增加问候语 从我的消息里找 没有就认为第一次接待需要增加问候语
        if config_checked_greetings==1 and config_greetings:
            # 检查是否存在匹配
            exists_greetings = any(msg['content'] == config_greetings for msg in my_msgs)
            if not exists_greetings:
                self.sendBtnMsg(config_greetings)
        # 如果我的消息为空 说明都是未读
        if not my_msgs:
            return friend_msgs
        # 取最后一个我的消息
        my_last_msg= my_msgs[-1]
        # 取我的最后一条消息的下标
        my_last_index = my_last_msg['index']
        # 记录一下最后五条 用于定位消息
        self.last_messages = self._getLastMessages(friend_msgs)
        if not friend_msgs:
            return []
        filtered_messages = [msg for msg in friend_msgs if msg['index'] > my_last_index]
        return filtered_messages

    def _getLastMessages(self, messages, count=5):
        """获取最后所有的朋友消息"""
        last_messages =  messages[-count:]  # 返回最后最多五条消息，如果是空列表则返回空列表
        # 提取每条消息的 content 字段值
        contents = [msg['id'] for msg in last_messages if 'id' in msg and msg.get('type') != 'from_info']
        return contents

    def _getCurrentUserName(self):
        user_nickname = ''
        # 查找所有 msg-list 下的 li 元素
        message_items = self.page.locator('.msg-list > li')
        for index in range(message_items.count()):
            message_item = message_items.nth(index)
            # 检查是否是客户的消息
            if message_item.locator('.buyer-item').count() > 0:
                # 用户头像处理 获取头像src 后几位作为用户唯一值
                avatar_locator = message_item.locator('.buyer-item img.avatar')
                if avatar_locator.count() > 0:
                    avatar_src = avatar_locator.first.get_attribute('src')
                    user_nickname = avatar_src[-8:]  # 提取src属性值的最后8个字符

        return user_nickname

    def _getAllCurrentMsg(self):
        # 查找所有 msg-list 下的 li 元素
        message_items = self.page.locator('.msg-list > li')
        all_message = None
        # 客户消息 包含 来自哪里卡片  商品卡片 文字 和图片消息
        customer_messages = []
        # 自己的消息
        my_messages = []
        username = self._getCurrentUserName()
        for index in range(message_items.count()):
            message_item = message_items.nth(index)

            # 获取当前 li 的 ID
            item_id = message_item.get_attribute('id')

            # 检查是否是客户的消息
            if message_item.locator('.buyer-item').count() > 0:
                # 用户头像处理 获取头像src 后几位作为用户唯一值
                avatar_locator = message_item.locator('.buyer-item img.avatar')
                if avatar_locator.count() > 0:
                    avatar_src = avatar_locator.first.get_attribute('src')
                    username = avatar_src[-8:]  # 提取src属性值的最后8个字符
                # 检查是否是卡片消息
                if message_item.locator('.buyer-item .msg-content.good-card').count() > 0:
                    # 立即检查商品ID和商品名称是否存在并提取
                    if message_item.locator('.buyer-item .good-id').count() > 0 and message_item.locator('.buyer-item .good-name').count() > 0:
                        good_id = message_item.locator('.buyer-item .good-id').text_content().replace('商品ID：', '').replace('复制', '').strip()
                        good_name = message_item.locator('.buyer-item .good-name').text_content().strip()
                        customer_messages.append({
                            'id': item_id,
                            'index':index,
                            'who':username,
                            'type': 'card',
                            'good_id': good_id,
                            'good_name': good_name,
                            'content':f'我要咨询商品ID:{good_id},商品名称:{good_name}'
                        })
                    else:
                        print(f"未找到商品ID或商品名称，跳过ID为 {item_id} 的消息项")
                # 检查是否是文本消息
                elif message_item.locator('.buyer-item .msg-content-box').count() > 0:
                    message_content = message_item.locator('.buyer-item .msg-content-box').text_content().strip()
                    customer_messages.append({
                        'id': item_id,
                        'index':index,
                        'who':username,
                        'type': 'text',
                        'content': message_content
                    })
                # 检查是否是图片消息
                elif message_item.locator('.buyer-item .msg-content.image-msg img').count() > 0:
                    image_src = message_item.locator('.buyer-item .msg-content.image-msg img').first.get_attribute('src')
                    customer_messages.append({
                        'id': item_id,
                        'index':index,
                        'who':username,
                        'type': 'img',
                        'src':image_src,
                        'content': '告诉我这个图片url里的内容:'+ image_src
                    })
                else:
                    customer_messages.append({
                        'id': item_id,
                        'index':index,
                        'who':username,
                        'type': 'unknown',
                        'content': '未知消息'
                    })
                    print(f"未找到文本、卡片或图片消息内容，跳过ID为 {item_id} 的消息项")

            # 检查是否是客户来源提示
            elif message_item.locator('.notify-card').count() > 0:
                # 立即检查商品名称是否存在并提取
                if message_item.locator('.notify-card .good-content p').count() > 0:
                    good_name = message_item.locator('.notify-card .good-content p').text_content().strip()
                    customer_messages.append({
                        'id': item_id,
                        'index':index,
                        'who':username,
                        'type': 'from_info',
                        'good_name': good_name,
                        'content':f'我浏览了商品:{good_name}'
                    })
                else:
                    print(f"未找到商品名称，跳过ID为 {item_id} 的通知消息项")
            #检查自己的消息 记录下index 后续使用
            elif message_item.locator('.cs-item').count() > 0:
                 my_msg = message_item.locator('.cs-item .msg-content-box').text_content().strip() if message_item.locator('.cs-item .msg-content-box').count() > 0 else ""
                 my_messages.append({
                     'id': item_id,
                     'index':index,
                     'type': 'my',
                     'content': my_msg
                 })
        #         客户消息和我的消息 包括其他消息列如 info消息
        all_message = {'customer_messages':customer_messages,"my_messages":my_messages}
        return all_message


    def _getCurrentFriendMsg(self):
        friend_msg = self._getAllCurrentMsg()['customer_messages']
        return friend_msg

    def readCurrentUnread(self):
        new_messages = []
        # 获取当前对话框所有朋友消息
        friend_messages = self._getCurrentFriendMsg()
        print(friend_messages)
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
                        friend_messages_content = [msg['id'] for msg in friend_messages if 'id' in msg]
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
        print(f" - {new_messages}")  # 打印每条朋友消息
        return new_messages


    #刷新页面
    def pageReload(self, max_retries=3, base_delay=30):
        last_exception = None

        for attempt in range(max_retries + 1):
            try:
                print(f"尝试刷新页面 (第 {attempt + 1}/{max_retries + 1} 次)...")

                # 执行页面刷新
                self.page.reload(
                    timeout=30000,
                    wait_until='domcontentloaded'
                )

                # 执行滚动操作
                self.page.evaluate(f"window.scrollBy(0, {random.randint(-10, 10)})")

                print("页面刷新成功")
                return True  # 成功返回True

            except Exception as e:
                last_exception = e
                print(f"第 {attempt + 1} 次刷新失败: {e}")

                # 如果不是最后一次尝试，则使用指数退避策略等待
                if attempt < max_retries:
                    delay = base_delay * (60 ** attempt)  # 指数退避：2, 4, 8秒
                    print(f"等待 {delay} 秒后重试...")
                    time.sleep(delay)

        # 所有尝试都失败
        error_msg = f"页面刷新失败，已重试 {max_retries} 次。最后错误: {str(last_exception)}"
        print(error_msg)
        raise Exception(error_msg)

    def bringToFront(self):
        self.page.bring_to_front()