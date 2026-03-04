from playwright.sync_api import sync_playwright
import json
import os,time,random, re
import hashlib
from urllib.parse import urlparse, parse_qs, unquote
import urllib.request
from html import unescape
from utils.tools import *

class DouDian():
    # 登录地址
    chat_url =  'https://fxg.jinritemai.com/ffa/mshop/homepage/index'
    # chat_url =  'https://fxg.jinritemai.com/login/common'
    # chat_url ='https://im.jinritemai.com/pc_seller_v2/main/workspace'

    def __init__(self,headless: bool = False,storage_state_path:str='state_dd.json') -> None:
        self.headless = headless
        self.storage_state_path = storage_state_path
        self.viewport={ "width": 1280, "height": 600  }
        self.login_state = False
        # 记录当前聊天框最后的消息 用于下次匹配最新消息的开始点
        self.last_messages = []
        # 记录右侧“咨询宝贝”面板的商品信息，避免重复推送
        self.last_product_signature = ""
        self.last_panel_text = ""
        self.link_cache = {}
        self.chat_last_friend_index = {}
        self.chat_seen_friend_counts = {}
        self.last_user_nickname = ""
        self.last_chat_cache_key = ""
        self.greeting_sent_at = {}
        self.greeting_cooldown_seconds = 2 * 3600
        self.checked_feishu = 0
        self.feishu_url = ""

    # 启动
    def launchChat(self, config_checked_pwd_login=0, config_username='', config_pwd=''):
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
            has_storage_state = os.path.exists(self.storage_state_path)
            kwargs = {
                "viewport": self.viewport,
                "user_agent":user_agent
            }
            if has_storage_state:
                kwargs["storage_state"] = self.storage_state_path

            self.context = self.browser.new_context(**kwargs)
            self.home_page = self.context.new_page()
            self.home_page.set_default_timeout(5000)
            # 修改navigator.webdriver属性以规避检测
            self.home_page.add_init_script("""
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
            self.home_page.add_init_script("""
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

            # 导航到登录页面并执行登录逻辑
            self.home_page.goto(self.chat_url, timeout=60000)
            try:
                if (not has_storage_state) and config_checked_pwd_login == 1 and config_username and config_pwd:
                    try:
                        self.login_by_pwd(config_username, config_pwd)
                    except Exception:
                        pass
                feige_icon = self.home_page.wait_for_selector('div.feige_headerApp__1NrTA.nav-menu_activeHeader__1ZwyP', state='visible', timeout=18000000)
                # 捕获新标签页（点击“新闻”链接）
                with self.context.expect_page() as new_page_info:
                    feige_icon.click()
                # 获取新页面并操作
                self.page = new_page_info.value
                self.page.wait_for_load_state()
                # 例如：等待互动管理菜单项变得可交互
                self.page.wait_for_selector('.auxo-tabs-nav-wrap', state='visible', timeout=18000000)
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
            self._notify_feishu(f"抖店启动失败: {e}")
            print('Exception exe')

    def login_by_pwd(self, config_username, config_pwd):
        try:
            self.home_page.wait_for_selector("div.daren-login-container", timeout=10000)
        except Exception:
            try:
                self.home_page.wait_for_selector("input[placeholder='请输入邮箱']", timeout=10000)
            except Exception:
                pass

        # 切换到邮箱登录
        try:
            self.home_page.get_by_text("邮箱登录", exact=True).click(timeout=5000)
        except Exception:
            try:
                self.home_page.locator("div:has-text('邮箱登录')").first.click(timeout=5000)
            except Exception:
                pass

        def ensure_agreement():
            checked = None
            try:
                checkbox = self.home_page.locator("input[type='checkbox']").first
                if checkbox and checkbox.count() > 0:
                    checked = checkbox.is_checked()
                    if checked is False:
                        try:
                            checkbox.check(timeout=2000)
                        except Exception:
                            checkbox.click(timeout=2000)
            except Exception:
                checked = None
            if checked is None or checked is False:
                try:
                    agree_text = self.home_page.locator("text=登录即代表同意").first
                    if agree_text and agree_text.count() > 0:
                        agree_text.click(timeout=2000)
                except Exception:
                    pass

        # 优先在登录容器中按顺序填入账号/密码，避免写入到同一个输入框
        try:
            def slow_type(locator, text):
                try:
                    locator.click(timeout=2000)
                except Exception:
                    pass
                try:
                    locator.fill("")
                except Exception:
                    pass
                locator.type(text, delay=random.randint(80, 140))

            container = self.home_page.locator("div.daren-login-container").first
            inputs = container.locator("input")
            if inputs.count() >= 2:
                slow_type(inputs.nth(0), config_username)
                slow_type(inputs.nth(1), config_pwd)
            else:
                raise Exception("login container inputs not found")
        except Exception:
            # 输入邮箱
            email_selectors = [
                "input[placeholder='请输入邮箱']",
                "input[placeholder='邮箱']",
                "input[type='text']",
            ]
            filled = False
            for selector in email_selectors:
                try:
                    slow_type(self.home_page.locator(selector).first, config_username)
                    filled = True
                    break
                except Exception:
                    continue
            if not filled:
                try:
                    slow_type(self.home_page.get_by_placeholder("请输入邮箱").first, config_username)
                except Exception:
                    pass

            # 输入密码
            pwd_selectors = [
                "input[placeholder='密码']",
                "input[type='password']",
            ]
            for selector in pwd_selectors:
                try:
                    slow_type(self.home_page.locator(selector).first, config_pwd)
                    break
                except Exception:
                    continue

        ensure_agreement()

        # 点击登录
        try:
            self.home_page.get_by_role("button", name="登录").click(timeout=5000)
        except Exception:
            try:
                self.home_page.get_by_text("登录", exact=True).click(timeout=5000)
            except Exception:
                pass
        try:
            self.home_page.wait_for_timeout(500)
            warning = self.home_page.locator("text=请先勾选同意").first
            if warning and warning.count() > 0:
                ensure_agreement()
                self.home_page.get_by_role("button", name="登录").click(timeout=5000)
        except Exception:
            pass

    def set_feishu_config(self, checked_feishu=0, feishu_url=""):
        self.checked_feishu = 1 if checked_feishu == 1 else 0
        self.feishu_url = feishu_url or ""

    def _notify_feishu(self, message):
        if self.checked_feishu != 1 or not self.feishu_url:
            return
        payload = {"msg_type": "text", "content": {"text": message}}
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            self.feishu_url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urllib.request.urlopen(req, timeout=10)
        except Exception:
            return

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
        transfer_session_button = self.page.query_selector("[data-qa-id='qa-transfer-conversation']")
        if not transfer_session_button:
            raise Exception("未找到转移会话按钮")
        transfer_session_button.click()
        time.sleep(0.3)

        is_find_transfer = False

        names = []
        for n in other:
            n = (n or '').strip()
            if n and n not in names:
                names.append(n)

        for name in names:
            single_transfer(name)
            # 等待对话框加载完成 + 定位搜索框并输入
            search_box = self.page.locator(
                "input[type='search'].auxo-input[placeholder='请输入在线客服昵称']"
            )
            search_box.wait_for(state="visible", timeout=5000)
            search_box.fill(name)

            # 假设搜索结果会动态加载，可能需要等待一段时间或者监听某个事件
            self.page.wait_for_timeout(1000)  # 简单等待1秒作为示例

            # 先尝试定位第一个搜索结果的“转移”按钮；不同版本 UI 可能没有显式按钮，需要点列表行/二次确认
            try:
                first_result_transfer_buttons = self.page.locator(
                    'div[data-qa-id="qa-transfer-customer"][role="button"]'
                )
                if first_result_transfer_buttons.count() > 0:
                    # 如果找到了至少一个“转移”按钮，则点击第一个
                    is_find_transfer = True
                    first_result_transfer_buttons.nth(0).click()
                    print('转交成功')
                    break
            except Exception as e:
                # 点击坐标 (100, 200) 关闭弹框
                self.page.mouse.click(10, 10)
                raise Exception(f"查找或点击转接人时发生错误: {e}")

            # 兜底：点中搜索结果的“行”，部分 UI 选中后需要再点“确定/转移”
            clicked = False
            row_selectors = [
                f".auxo-list-item:has-text('{name}')",
                f"div[role='listitem']:has-text('{name}')",
                f"li:has-text('{name}')",
                f"text={name}",
            ]
            for sel in row_selectors:
                try:
                    row = self.page.locator(sel).first
                    if row and row.count() > 0:
                        row.click(timeout=1000)
                        clicked = True
                        break
                except Exception:
                    continue

            if clicked:
                # 某些版本需要再点确认按钮
                confirm_selectors = [
                    "button:has-text('转移')",
                    "button:has-text('确定')",
                    "div[role='button']:has-text('转移')",
                    "div[role='button']:has-text('确定')",
                ]
                for sel in confirm_selectors:
                    try:
                        btn = self.page.locator(sel).first
                        if btn and btn.count() > 0:
                            btn.click(timeout=1000)
                            break
                    except Exception:
                        continue
                is_find_transfer = True
                print('转交成功')
                break

            single_transfer('未找到'+name)
            time.sleep(0.5)
        #   如果未找到直接回复
        if not is_find_transfer:
            # 点击坐标 (100, 200) 关闭弹框
            self.page.mouse.click(10, 10)
            self.sendMsg("抱歉,转交失败")

    # 发送信息
    def sendMsg(self,msg):
        if not msg:
            return
        # 查找图片
        msg,urls = replace_image_tag_with_word(msg)
        if urls:
            # 直接查找指定的文件上传输入框
            input_element_locator = self.page.locator("input[type='file'][multiple][accept='.png,.jpg,.jpeg,.gif']")
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
                raise Exception("图片路径不对或者没找到上传按钮")
        else:
            self.sendBtnMsg(msg)

    def sendBtnMsg(self,msg):
        chunks = self._split_text_chunks(msg)
        for chunk in chunks:
            textarea = self.page.query_selector("[data-qa-id='qa-send-message-textarea']")
            if textarea:
                textarea.fill(chunk)
            else:
                raise Exception("输入框未找到.")
            time.sleep(random.uniform(0.6, 1.2))
            send_button = self.page.query_selector("[data-qa-id='qa-send-message-button']")
            if send_button:
                send_button.click()
            else:
                raise Exception("发送按钮未找到.")
            time.sleep(random.uniform(0.2, 0.5))

    def _split_text_chunks(self, msg, max_len=400):
        text = (msg or '').strip()
        if not text:
            return []
        if len(text) <= max_len:
            return [text]
        chunks = []
        buf = ''
        split_chars = set('。！？!?；;，,\n')
        for ch in text:
            buf += ch
            if len(buf) >= max_len:
                cut = -1
                for i in range(len(buf) - 1, int(max_len * 0.6), -1):
                    if buf[i] in split_chars:
                        cut = i + 1
                        break
                if cut == -1:
                    cut = max_len
                chunks.append(buf[:cut].strip())
                buf = buf[cut:]
        if buf.strip():
            chunks.append(buf.strip())
        return [c for c in chunks if c]

    def _switch_to_chat(self, chat_name):
        if not chat_name:
            return False
        try:
            current = self._getCurrentUserName()
        except Exception:
            current = ''
        if current == chat_name:
            return True
        chat_items = self.page.query_selector_all(
            '[data-kora="conversation"][data-qa-id="qa-conversation-chat-item"]'
        )
        for item in chat_items:
            try:
                text = (item.inner_text() or '').strip()
            except Exception:
                text = ''
            if not text:
                continue
            if chat_name in text:
                item.click()
                time.sleep(0.5)
                return True
        return False

    def sendMsgToChat(self, chat_name, msg, switch_back=True):
        if not chat_name or not msg:
            return False
        try:
            previous_chat = self._getCurrentUserName()
        except Exception:
            previous_chat = ''
        if not self._switch_to_chat(chat_name):
            return False
        self.sendMsg(msg)
        if switch_back and previous_chat and previous_chat != chat_name:
            try:
                self._switch_to_chat(previous_chat)
            except Exception:
                pass
        return True

    # 获取下一条最新消息
    def getNextNewMessage(self,checkRedMessage = True,config_checked_greetings=0,config_greetings=''):
        # 如果停留在当前对话框 先判断当前对话框是否有新消息
        new_msgs = self.readCurrentUnread(config_checked_greetings,config_greetings)
        if  new_msgs:
            return new_msgs

        if not checkRedMessage:
            return []
        # 查找第一个 chat-list 下的所有 chat-item
        chat_items = self.page.query_selector_all(
            '[data-kora="conversation"][data-qa-id="qa-conversation-chat-item"]'
        )

        # print(f"发现 {chat_items.count()} 个会话项")
        # 判断对话列表是否有新消息 有的话 取第一个
        for item in chat_items:
            # 获取背景颜色
            bg_color = item.evaluate(
                "element => window.getComputedStyle(element).backgroundColor"
            )
            # 检查是否为未读颜色
            is_unread = bg_color == 'rgb(255, 243, 232)'
            # 额外验证：检查是否有未读标识（如红点）
            unread_badge = item.query_selector(".auxo-badge-count")
            if is_unread or unread_badge is not None:
                item.click()
                time.sleep(1)  # 等待页面加载
                # 加装未读消息
                new_msgs = self._getAfterSwitchMsg(config_checked_greetings,config_greetings)
                if  new_msgs:
                    print('新框消息=========')
                    print(new_msgs)
                    return new_msgs
        return []

    # 点击新对话 加载未读消息 加载的原理就是找到我的消息的最后一个的之后的都是未读消息
    # 加载完需要更新 last_messages
    def _getAfterSwitchMsg(self,config_checked_greetings=0,config_greetings=''):
        all_msgs = self._getAllCurrentMsg()
        my_msgs = all_msgs['my_messages']
        friend_msgs =  all_msgs['customer_messages']
        chat_key = self._get_chat_cache_key()
        current_counts = self._build_message_counts(friend_msgs) if friend_msgs else {}
        self.chat_seen_friend_counts[chat_key] = current_counts
        if config_checked_greetings==1 and config_greetings:
            greeting_key = self._get_greeting_key()
            if self._should_send_greeting(greeting_key, my_msgs, config_greetings):
                self.sendBtnMsg(config_greetings)
        # 如果我的消息为空 说明都是未读
        if not my_msgs:
            if friend_msgs:
                self.chat_last_friend_index[chat_key] = max(msg['index'] for msg in friend_msgs)
            msgs = self._append_link_info_messages(friend_msgs)
            return self._append_product_panel_message(msgs)
        # 取最后一个我的消息
        my_last_msg= my_msgs[-1]
        # 取我的最后一条消息的下标
        my_last_index = my_last_msg['index']
        # 记录一下最后五条 用于定位消息
        self.last_messages = self._getLastMessages(friend_msgs)
        if not friend_msgs:
            return []
        self.chat_last_friend_index[chat_key] = max(msg['index'] for msg in friend_msgs)
        filtered_messages = [msg for msg in friend_msgs if msg['index'] > my_last_index]
        filtered_messages = self._append_link_info_messages(filtered_messages)
        if filtered_messages:
            return self._append_product_panel_message(filtered_messages)
        return filtered_messages

    def _getLastMessages(self, messages, count=5):
        """获取最后所有的朋友消息"""
        last_messages =  messages[-count:]  # 返回最后最多五条消息，如果是空列表则返回空列表
        # 提取每条消息的 content 字段值
        contents = [msg['content'] for msg in last_messages if 'content' in msg and msg.get('type') != 'from_info']
        return contents

    def _get_greeting_key(self):
        return self._get_chat_cache_key()

    def _should_send_greeting(self, key, my_msgs, greetings):
        now = time.time()
        last = self.greeting_sent_at.get(key)
        if last is None or now - last >= self.greeting_cooldown_seconds:
            self.greeting_sent_at[key] = now
            return True
        return False

    def _get_panel_info(self, panel_selector, tab_selector, panel_tag, empty_markers):
        panel = self.page.query_selector(panel_selector)
        if not panel:
            tab = self.page.query_selector(tab_selector)
            if tab:
                tab.click()
                time.sleep(0.3)
                panel = self.page.query_selector(panel_selector)
        if not panel:
            return None

        text = panel.inner_text().strip()
        if not text:
            return None

        panel_key = f"{panel_tag}:{text}"
        if panel_key == self.last_panel_text:
            return None

        if any(m in text for m in empty_markers):
            self.last_panel_text = panel_key
            self.last_product_signature = ""
            return None
        self.last_panel_text = panel_key

        img_url = ''
        img_el = panel.query_selector("div[style*='background-image']")
        if img_el:
            style = img_el.get_attribute('style') or ''
            m = re.search(r'url\\(\"?([^\"\\)]+)\"?\\)', style)
            if m:
                img_url = m.group(1)

        price = ''
        m = re.search(r"￥\s*([0-9]+(?:\.[0-9]+)?)", text)
        if m:
            price = m.group(1)

        lines = [l.strip() for l in text.splitlines() if l.strip()]
        stop_words = [
            '咨询宝贝',
            '浏览足迹',
            '爆品推荐',
            '邀请下单',
            '计算价格',
            '规格属性',
            '商品视频',
            '商品评价',
            '搭配商品',
            '券后价',
            '已售',
            '￥',
        ]
        candidates = [l for l in lines if not any(w in l for w in stop_words)]
        title = max(candidates, key=len, default='')

        return {'title': title, 'price': price, 'img_url': img_url, 'raw_text': text}

    def _get_product_panel_info(self):
        try:
            empty_markers = [
                '暂无咨询',
                '暂无商品',
                '用户最近没有咨询过宝贝',
                '最近没有咨询过宝贝',
                '暂无浏览',
                '暂无足迹',
                '暂无记录',
                '最近看过以下商品',
                '消费者最近看过以下商品',
                '详情已浏览',
            ]
            info = self._get_panel_info(
                '#rc-tabs-1-panel-combination',
                '#rc-tabs-1-tab-combination',
                'combination',
                empty_markers,
            )
            if info:
                return info
            info = self._get_panel_info(
                '#rc-tabs-1-panel-footprint',
                '#rc-tabs-1-tab-footprint',
                'footprint',
                empty_markers,
            )
            if info:
                return info
            return self._get_panel_info(
                '#rc-tabs-1-panel-hot_product',
                '#rc-tabs-1-tab-hot_product',
                'hot_product',
                empty_markers,
            )
        except Exception:
            return None

    def _append_product_panel_message(self, messages):
        info = self._get_product_panel_info()
        if not info:
            return messages
        signature = f"{info.get('title','')}|{info.get('price','')}|{info.get('img_url','')}"
        if signature == self.last_product_signature:
            return messages
        self.last_product_signature = signature

        parts = []
        if info.get('title'):
            parts.append(f"咨询商品:{info['title']}")
        if info.get('price'):
            parts.append(f"价格:{info['price']}")
        if info.get('img_url'):
            parts.append(f"图片:{info['img_url']}")
        content = ' '.join(parts).strip() or '咨询商品信息已更新'

        messages.append({
            'index': len(messages),
            'who': self._getCurrentUserName(),
            'type': 'from_info',
            'source': 'panel',
            'good_name': info.get('title', ''),
            'content': content,
            'product': info,
        })
        return messages

    def _extract_urls(self, text):
        if not text:
            return []
        urls = re.findall(r'https?://[^\s]+', text)
        cleaned = []
        for url in urls:
            url = url.rstrip(').,;]}>\"\'')
            cleaned.append(url)
        return cleaned

    def _extract_product_id(self, url):
        try:
            parsed = urlparse(url)
            qs = parse_qs(parsed.query)
            for key in ['id', 'item_id', 'product_id']:
                if key in qs and qs[key]:
                    return qs[key][0]
            m = re.search(r'(?:id=|item/|product/)(\d{6,})', url)
            if m:
                return m.group(1)
        except Exception:
            return ''
        return ''

    def _should_fetch_url(self, url):
        try:
            netloc = urlparse(url).netloc.lower()
        except Exception:
            return False
        return any(domain in netloc for domain in ['jinritemai.com', 'douyin.com', 'dy.com', 'v.douyin.com'])

    def _fetch_link_page(self, url):
        if not url:
            return "", "", ""
        context = getattr(self, "context", None)
        if not context:
            return url, "", ""
        page = None
        try:
            page = context.new_page()
            page.goto(url, timeout=15000, wait_until="domcontentloaded")
            page.wait_for_timeout(800)
            body_text = ""
            try:
                body_text = page.inner_text("body").strip()
            except Exception:
                try:
                    body_text = (page.evaluate("() => (document.body && document.body.innerText) ? document.body.innerText : ''") or "").strip()
                except Exception:
                    body_text = ""
            return page.url, page.content(), body_text
        except Exception:
            return url, "", ""
        finally:
            if page:
                try:
                    page.close()
                except Exception:
                    pass

    def _extract_from_resolved_url(self, resolved_url):
        info = {"title": "", "price": "", "product_id": "", "full_text": ""}
        if not resolved_url:
            return info
        try:
            parsed = urlparse(resolved_url)
            qs = parse_qs(parsed.query)
            for key in ["id", "product_id", "item_id", "goods_id"]:
                if qs.get(key):
                    info["product_id"] = qs[key][0]
                    break

            goods_detail_raw = ""
            if qs.get("goods_detail"):
                goods_detail_raw = qs["goods_detail"][0]
            if goods_detail_raw:
                decoded = goods_detail_raw
                for _ in range(3):
                    nxt = unquote(decoded)
                    if nxt == decoded:
                        break
                    decoded = nxt
                goods_detail = {}
                try:
                    goods_detail = json.loads(decoded)
                except Exception:
                    goods_detail = {}
                if goods_detail:
                    title = str(goods_detail.get("title", "")).strip()
                    if title:
                        info["title"] = title
                    min_price = goods_detail.get("min_price")
                    max_price = goods_detail.get("max_price")
                    if min_price is not None:
                        try:
                            price_val = float(min_price) / 100.0
                            if max_price is not None and str(max_price) != str(min_price):
                                max_val = float(max_price) / 100.0
                                info["price"] = f"{price_val:.2f}-{max_val:.2f}"
                            else:
                                info["price"] = f"{price_val:.2f}"
                        except Exception:
                            pass
                    info["full_text"] = json.dumps(goods_detail, ensure_ascii=False)
        except Exception:
            return info
        return info

    def _extract_full_text_from_html(self, html):
        if not html:
            return ""
        text = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.I | re.S)
        text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
        text = re.sub(r"<[^>]+>", " ", text)
        text = unescape(text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _get_product_info_from_douyin_page(self, html):
        info = {"title": "", "price": "", "product_id": "", "full_text": ""}
        if not html:
            return info
        info["full_text"] = self._extract_full_text_from_html(html)
        # title
        m = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
        if m:
            info["title"] = re.sub(r"\\s+", " ", m.group(1)).strip()
        # common id patterns
        for pat in [
            r'"productId"\\s*:\\s*"?(\\d{6,})"?',
            r'"commodityId"\\s*:\\s*"?(\\d{6,})"?',
            r'"item_id"\\s*:\\s*"?(\\d{6,})"?',
            r'\\bitem_id=(\\d{6,})',
            r'\\bproduct_id=(\\d{6,})',
            r'\\bid=(\\d{6,})',
        ]:
            m = re.search(pat, html)
            if m:
                info["product_id"] = m.group(1)
                break
        # price patterns
        for pat in [
            r'"price"\\s*:\\s*"?(\\d+(?:\\.\\d+)?)"?',
            r'"salePrice"\\s*:\\s*"?(\\d+(?:\\.\\d+)?)"?',
            r"￥\\s*([0-9]+(?:\\.[0-9]+)?)",
        ]:
            m = re.search(pat, html)
            if m:
                info["price"] = m.group(1)
                break
        return info

    def _extract_info_from_share_text(self, text, url):
        info = {"title": "", "price": "", "product_id": "", "full_text": ""}
        if not text:
            return info
        clean = text.replace("【抖音商城】", " ").replace(url, " ")
        clean = re.sub(r"长按复制.*$", "", clean, flags=re.S)
        clean = re.sub(r"已售\\s*\\d+(?:\\.\\d+)?\\s*(?:件|单|笔)?", " ", clean)
        clean = re.sub(r"\s+", " ", clean).strip(" ，。,:：")
        m = re.search(r"[\u4e00-\u9fff]", clean)
        if m and m.start() > 0:
            clean = clean[m.start():]
        if clean:
            info["title"] = clean[:120]
            info["full_text"] = clean
        m = re.search(r"[￥¥]\s*([0-9]+(?:\.[0-9]+)?)", text)
        if m:
            info["price"] = m.group(1)
        for pat in [
            r"商品ID\s*[:：]\s*(\d{6,})",
            r"\bgoods_id=(\d{6,})",
            r"\bitem_id=(\d{6,})",
            r"\bproduct_id=(\d{6,})",
            r"\bid=(\d{6,})",
        ]:
            m = re.search(pat, text)
            if m:
                info["product_id"] = m.group(1)
                break
        return info

    def _get_product_info_from_link(self, url, raw_text=''):
        if url in self.link_cache:
            return self.link_cache[url]
        info = {'url': url, 'title': '', 'price': '', 'product_id': self._extract_product_id(url), 'full_text': ''}
        if self._should_fetch_url(url):
            try:
                # Douyin short links often require browser redirects; use a temp page to avoid navigating away from IM page.
                resolved, html, body_text = self._fetch_link_page(url)
                info["url"] = resolved or url
                from_resolved = self._extract_from_resolved_url(info["url"])
                if from_resolved.get("title"):
                    info["title"] = from_resolved["title"]
                if from_resolved.get("price"):
                    info["price"] = from_resolved["price"]
                if from_resolved.get("product_id"):
                    info["product_id"] = info.get("product_id") or from_resolved["product_id"]
                if from_resolved.get("full_text"):
                    info["full_text"] = from_resolved["full_text"]
                if html:
                    dy = self._get_product_info_from_douyin_page(html)
                    if dy.get("title"):
                        info["title"] = dy["title"]
                    if dy.get("price"):
                        info["price"] = dy["price"]
                    if dy.get("product_id"):
                        info["product_id"] = info.get("product_id") or dy["product_id"]
                    if dy.get("full_text"):
                        info["full_text"] = dy["full_text"]
                if body_text:
                    info["full_text"] = body_text
            except Exception:
                pass
        # Fallback for Douyin share text like:
        # 4.10 s@... https://v.douyin.com/... 商品标题 长按复制...
        if raw_text and (not info.get("title") or not info.get("price") or not info.get("product_id")):
            ext = self._extract_info_from_share_text(raw_text, url)
            if ext.get("title") and not info.get("title"):
                info["title"] = ext["title"]
            if ext.get("price") and not info.get("price"):
                info["price"] = ext["price"]
            if ext.get("product_id") and not info.get("product_id"):
                info["product_id"] = ext["product_id"]
            if ext.get("full_text") and not info.get("full_text"):
                info["full_text"] = ext["full_text"]
        if raw_text and not info.get("full_text"):
            info["full_text"] = raw_text
        self.link_cache[url] = info
        return info

    def _append_link_info_messages(self, messages):
        if not messages:
            return messages
        extra = []
        for msg in messages:
            if msg.get('type') != 'text':
                continue
            urls = self._extract_urls(msg.get('content', ''))
            for url in urls:
                info = self._get_product_info_from_link(url, msg.get('content', ''))
                if not info:
                    continue
                parts = [f"商品链接:{url}"]
                if info.get('title'):
                    parts.append(f"商品标题:{info['title']}")
                if info.get('price'):
                    parts.append(f"价格:{info['price']}")
                if info.get('product_id'):
                    parts.append(f"商品ID:{info['product_id']}")
                if info.get('full_text'):
                    parts.append(f"商品全文:{info['full_text']}")
                extra.append({
                    'index': len(messages) + len(extra),
                    'who': msg.get('who', ''),
                    'type': 'from_info',
                    'source': 'link',
                    'content': ' '.join(parts),
                    'product_link': url,
                    'product': info,
                })
        if extra:
            messages = list(messages) + extra
        return messages

    def _getCurrentUserName(self):
        # 等待页面加载完成并找到包含用户昵称的元素
        user_nickname_element = self.page.query_selector('._aTiznnWtrpmuI8BajvY')
        user_nickname = ''
        selector_candidates = [
            '._aTiznnWtrpmuI8BajvY',
            '[data-qa-id="qa-conversation-chat-user-name"]',
            '[data-qa-id="qa-conversation-user-name"]',
            '.chat-info-user-name',
            '[class*="chat-user-name"]',
            '[class*="conversation-user-name"]',
            '[class*="session-user-name"]',
        ]
        for selector in selector_candidates:
            try:
                user_nickname_element = self.page.query_selector(selector)
                if not user_nickname_element:
                    continue
                text = (user_nickname_element.text_content() or '').strip()
                if text:
                    user_nickname = re.sub(r"\s+", " ", text)
                    break
            except Exception:
                continue

        # 兜底：从输入提示/顶部文案中提取当前会话昵称
        if not user_nickname:
            try:
                guessed = self.page.evaluate(
                    """() => {
                        const norm = (s) => (s || '').replace(/\\s+/g, ' ').trim();
                        const body = document.body ? (document.body.innerText || '') : '';
                        if (!body) return '';
                        let m = body.match(/发送给\\s*([^，,\\n]{1,40})\\s*[，,]/);
                        if (m && m[1]) return norm(m[1]);
                        m = body.match(/发送给\\s*([^\\n]{1,40})\\s*使用Enter/);
                        if (m && m[1]) return norm(m[1]);
                        m = body.match(/\\n([^\\n]{1,40})\\s+添加备注/);
                        if (m && m[1]) return norm(m[1]);
                        return '';
                    }"""
                )
                if guessed:
                    user_nickname = re.sub(r"\s+", " ", guessed).strip()
            except Exception:
                pass

        if user_nickname:
            self.last_user_nickname = user_nickname
            return user_nickname
        return self.last_user_nickname

    def getCurrentChatName(self):
        return self._getCurrentUserName()

    def get_current_session_key(self):
        username = self._getCurrentUserName()
        try:
            key = self.page.evaluate(
                """(name) => {
                    const norm = (s) => (s || '').replace(/\\s+/g, ' ').trim();
                    const items = Array.from(document.querySelectorAll('[data-kora="conversation"][data-qa-id="qa-conversation-chat-item"]'));
                    if (!items.length) return '';
                    let active = items.find((el) => (el.getAttribute('aria-selected') || '') === 'true');
                    if (!active) {
                        active = items.find((el) => /active|selected/i.test(el.className || ''));
                    }
                    if (!active && name) {
                        active = items.find((el) => norm(el.innerText).includes(name));
                    }
                    if (!active) return '';
                    const attrs = ['data-conversation-id', 'data-session-id', 'data-id', 'data-user-id', 'id'];
                    for (const attr of attrs) {
                        const val = active.getAttribute(attr);
                        if (val) return `${attr}:${val}`;
                    }
                    const text = norm(active.innerText);
                    return text ? `text:${text.slice(0, 80)}` : '';
                }""",
                username or '',
            )
            if key:
                return f"conv::{key}"
        except Exception:
            pass
        if username:
            return f"name::{username}"
        return ''

    def _get_chat_cache_key(self):
        username = self._getCurrentUserName()
        session_key = self.get_current_session_key()
        # 会话列表文本键(conv::text:...)不稳定，优先用昵称键避免同会话抖动
        key = ''
        if session_key and not session_key.startswith('conv::text:'):
            key = session_key
        elif username:
            key = f"name::{username}"
        elif session_key:
            key = session_key
        elif self.last_chat_cache_key:
            key = self.last_chat_cache_key
        else:
            key = 'session'
        if key:
            self.last_chat_cache_key = key
        return key

    def get_chat_cache_key(self):
        return self._get_chat_cache_key()


    def _getAllCurrentMsg(self):
        # 查找所有 msg-list 下的 li 元素
        message_items = self.page.query_selector_all('.msgItemWrap')
        all_message = None
        # 客户消息 包含 来自哪里卡片  商品卡片 文字 和图片消息
        customer_messages = []
        # 自己的消息
        my_messages = []
        username = self._getCurrentUserName()
        def extract_other_text(element):
            selectors = [
                '.leaveMessage.messageNotMe pre',
                '.leaveMessage.messageNotMe .content',
                '.leaveMessage.messageNotMe',
                '.messageNotMe pre',
                '.messageNotMe .content',
                '.messageNotMe',
            ]
            for sel in selectors:
                try:
                    el = element.query_selector(sel)
                    if not el:
                        continue
                    txt = (el.inner_text() or '').strip()
                    if txt:
                        return re.sub(r"\s+", " ", txt).strip()
                except Exception:
                    continue
            return ''
        for index in  range(len(message_items)):
            """解析消息类型并提取内容"""
            """判断消息发送者：my（自己）、other（对方）、system（系统）"""
            # 优先检查消息容器的布局方向
            element = message_items[index]
            sender = None
            # flex_container = element.query_selector('.Ie29C7uLyEjZzd8JeS8A')
            flex_container = element.query_selector("div[style*='flex-direction']")
            if flex_container:
                flex_dir = flex_container.get_attribute('style')
                if 'row-reverse' in flex_dir:
                    sender =  'my'  # 自己的消息：布局方向为 row-reverse
                else:
                    sender =  'other'  # 对方的消息：布局方向为 row

            # 检查是否为系统消息（无头像且包含特定文本）
            system_text = element.query_selector('.content.max-line span')
            if system_text and '用户正在查看商品' in system_text.inner_text():
                sender =  'system'
                spans = element.query_selector_all('.content.max-line span')
                texts = []
                for span in spans:
                    text = span.inner_text().strip()
                    if text:
                        texts.append(text)
                product_name = ' '.join(texts)
                customer_messages.append({
                    'index':index,
                    'who':username,
                    'type': 'from_info',
                    'source': 'system',
                    'good_name': product_name,
                    'content':f'我浏览了商品:{product_name}'
                })

            if sender =='other':
                # 商品卡片消息（系统或对方推送）
                card_element = element.query_selector('.chatd-card')
                if card_element:
                    spans = card_element.query_selector_all('.content.max-line span')
                    texts = []
                    for span in spans:
                        text = span.inner_text().strip()
                        if text:
                            texts.append(text)
                    ignore_keywords = [
                        '来自电商小助手的推荐',
                        '已售',
                        '券后价',
                        '保障',
                        '优惠',
                        '物流',
                    ]
                    candidates = [t for t in texts if not any(k in t for k in ignore_keywords)]
                    product_name = max(candidates, key=len, default='') or max(texts, key=len, default='')
                    price = ''
                    price_int = card_element.query_selector('.chatd-price-price-inter')
                    price_dec = card_element.query_selector('.chatd-price-price-decimal')
                    if price_int:
                        price = price_int.inner_text().strip()
                        if price_dec:
                            price += price_dec.inner_text().strip()
                    if not price:
                        card_text = card_element.inner_text()
                        m = re.search(r"￥\s*([0-9]+(?:\.[0-9]+)?)", card_text)
                        if m:
                            price = m.group(1)
                    parts = []
                    if product_name:
                        parts.append(f"我要咨询商品名称:{product_name}")
                    if price:
                        parts.append(f"价格:{price}")
                    content = ' '.join(parts).strip()
                    customer_messages.append({
                        'index':index,
                        'who':username,
                        'type': 'card',
                        'good_name': product_name,
                        'content': content
                    })
                # 图片消息
                img_element = element.query_selector("img[alt='图片'].auxo-dropdown-trigger")
                if img_element:
                    src = img_element.get_attribute('src')
                    if src and not src.startswith('data:image/svg+xml'):
                        customer_messages.append({
                            'index':index,
                            'who':username,
                            'type': 'img',
                            'src':src,
                            'content': '告诉我这个图片url里的内容:'+ src
                        })

                # 文字消息（兼容不同DOM结构）
                message_content = extract_other_text(element)
                if message_content:
                    customer_messages.append({
                        'index':index,
                        'who':username,
                        'type': 'text',
                        'content': message_content
                    })
            elif sender == 'my':
                 robot_div = element.query_selector("div:has-text('此消息由机器人自动回复')")
                 text_content = element.query_selector('.leaveMessage.messageIsMe pre')
                 message_content = ''
                 if text_content:
                    message_content = text_content.inner_text().strip()
                    # customer_messages.append({
                    #     'index':index,
                    #     'who':username,
                    #     'type': 'text',
                    #     'content': message_content
                    # })
                 if not robot_div and '很高兴为您服务，请问有什么可以帮您？' not in message_content:
                     my_messages.append({
                         'index':index,
                         'type': 'my',
                         'content': message_content
                     })
        #         客户消息和我的消息 包括其他消息列如 info消息
        all_message = {'customer_messages':customer_messages,"my_messages":my_messages}
        return all_message


    def _getCurrentFriendMsg(self):
        friend_msg = self._getAllCurrentMsg()['customer_messages']
        return friend_msg

    def _message_fingerprint(self, msg):
        base = "|".join([
            str(msg.get('type', '')),
            str(msg.get('source', '')),
            str(msg.get('good_name', '')),
            str(msg.get('content', '')).strip(),
            str(msg.get('src', '')),
            str(msg.get('product_link', '')),
        ])
        return hashlib.sha1(base.encode('utf-8', errors='ignore')).hexdigest()

    def _build_message_counts(self, messages):
        counts = {}
        for msg in messages:
            fp = msg.get('fingerprint') or self._message_fingerprint(msg)
            msg['fingerprint'] = fp
            counts[fp] = counts.get(fp, 0) + 1
        return counts

    def _diff_new_messages(self, messages, previous_counts):
        seen_now = {}
        new_messages = []
        for msg in messages:
            fp = msg.get('fingerprint') or self._message_fingerprint(msg)
            msg['fingerprint'] = fp
            seen_now[fp] = seen_now.get(fp, 0) + 1
            if seen_now[fp] > previous_counts.get(fp, 0):
                new_messages.append(msg)
        return new_messages

    def readCurrentUnread(self,config_checked_greetings=0,config_greetings=''):
        new_messages = []
        # 获取当前对话框所有朋友消息
        all_msgs = self._getAllCurrentMsg()
        friend_messages = all_msgs['customer_messages']
        my_messages = all_msgs['my_messages']
        chat_key = self._get_chat_cache_key()
        print(friend_messages)
        if not friend_messages:
            return  new_messages
        if config_checked_greetings==1 and config_greetings:
            greeting_key = self._get_greeting_key()
            if self._should_send_greeting(greeting_key, my_messages, config_greetings):
                self.sendBtnMsg(config_greetings)
        current_counts = self._build_message_counts(friend_messages)
        previous_counts = self.chat_seen_friend_counts.get(chat_key)
        if previous_counts is None:
            self.chat_seen_friend_counts[chat_key] = current_counts
            print("\n没有新的消息。")
            print(f" - {new_messages}")
            return new_messages

        new_messages = self._diff_new_messages(friend_messages, previous_counts)
        self.chat_seen_friend_counts[chat_key] = current_counts
        if not new_messages:
            print(f" - {new_messages}")
            return new_messages
        # print('# =============')
        new_messages = self._append_link_info_messages(new_messages)
        new_messages = self._append_product_panel_message(new_messages)
        print(f" - {new_messages}")  # 打印每条朋友消息
        return new_messages


    #刷新页面
    def pageReload(self):
        self.page.reload()
        # 确保页面加载完成
        self.page.wait_for_load_state('load')
        self.page.evaluate(f"window.scrollBy(0, {random.randint(-10, 10)})")
