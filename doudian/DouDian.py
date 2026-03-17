from collections import OrderedDict
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
        self.chat_last_message_cursor = {}
        self.chat_seen_message_keys = {}
        self.chat_seen_message_limit = 2000
        self.last_chat_cache_key = ""
        self.greeting_sent_at = {}
        self.greeting_cooldown_seconds = 2 * 3600
        self.checked_feishu = 0
        self.feishu_url = ""
        self.conversation_cache = {}
        self.conversation_ids_by_nickname = {}
        self.conversation_row_cache = {}

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
                self.page.on("response", self._handle_page_response)
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

    def _normalize_text(self, text):
        return re.sub(r"\s+", " ", str(text or "").strip())

    def _normalize_nickname(self, text):
        return self._normalize_text(text)

    def _is_system_notice_text(self, text):
        text = self._normalize_text(text)
        if not text:
            return False
        exact_tokens = (
            "此消息由机器人自动回复",
            "机器人接待中",
            "系统关闭会话",
            "当前会话已长时间未回复",
            "平台可能主动介入",
            "服务态度预警",
            "会话已转交",
            "会话已被转交",
            "会话已结束",
        )
        if any(token in text for token in exact_tokens):
            return True
        regex_patterns = (
            r"^客服.+接入$",
            r"^客服.+已接入.*$",
            r"^.+客服已接入.*$",
            r"^.+已转交给客服.*$",
            r"^.+已由客服接待.*$",
        )
        return any(re.match(pattern, text) for pattern in regex_patterns)

    def _extract_preview_from_dom_text(self, text, nickname=""):
        text = self._normalize_text(text)
        nickname = self._normalize_nickname(nickname)
        if nickname and text.startswith(nickname):
            text = text[len(nickname):].strip()
        text = re.sub(r"(重复来访|新客|老客|未读|已读|机器人接待中)", " ", text)
        text = re.sub(r"\b\d{1,2}:\d{2}(:\d{2})?\b", " ", text)
        text = re.sub(r"\b\d+\s*(秒|分钟|小时|天前|分钟前|小时前)\b", " ", text)
        text = re.sub(r"\b(昨天|今天|前天|刚刚)\b", " ", text)
        text = re.sub(r"\s{2,}", " ", text).strip()
        return text[:120]

    def _extract_conversation_preview(self, conv):
        msg_list = conv.get("msgList") or []
        skip_patterns = (
            "[商品]",
            "用户正在查看商品",
            "客服",
            "人工客服",
            "系统关闭会话",
        )
        fallback = ""
        for msg in msg_list:
            body = msg.get("messageBody") or {}
            content = self._normalize_text(body.get("content", ""))
            if not content:
                continue
            if not fallback:
                fallback = content
            if any(token in content for token in skip_patterns):
                continue
            return content[:120]
        return fallback[:120]

    def _extract_conversation_nickname_from_payload(self, conv):
        for msg in conv.get("msgList") or []:
            body = msg.get("messageBody") or {}
            ext = body.get("ext") or {}
            for key in ("nickname", "uname"):
                val = self._normalize_nickname(ext.get(key, ""))
                if val:
                    return val
        return ""

    def _rebuild_conversation_indexes(self):
        nickname_map = {}
        for biz_id, meta in self.conversation_cache.items():
            nickname = self._normalize_nickname(meta.get("nickname", ""))
            if not nickname:
                continue
            nickname_map.setdefault(nickname, []).append(biz_id)
        self.conversation_ids_by_nickname = nickname_map

    def _cache_conversation_list(self, data, source_url=""):
        if not isinstance(data, list):
            return
        changed = False
        now_ts = time.time()
        for conv in data:
            if not isinstance(conv, dict):
                continue
            biz_id = self._normalize_text(conv.get("bizConversationId", ""))
            if not biz_id:
                continue
            nickname = self._extract_conversation_nickname_from_payload(conv)
            preview = self._extract_conversation_preview(conv)
            old_meta = self.conversation_cache.get(biz_id, {})
            meta = {
                "bizConversationId": biz_id,
                "subConversationId": self._normalize_text(conv.get("subConversationId", "")),
                "parentConShortId": self._normalize_text(conv.get("parentConShortId", "")),
                "pigeonUid": self._normalize_text(conv.get("pigeonUid", "")),
                "nickname": nickname or old_meta.get("nickname", ""),
                "preview": preview or old_meta.get("preview", ""),
                "updated_at": now_ts,
                "source_url": source_url,
                "dom_text": old_meta.get("dom_text", ""),
            }
            if meta != old_meta:
                self.conversation_cache[biz_id] = meta
                changed = True
        if changed:
            self._rebuild_conversation_indexes()

    def _handle_page_response(self, response):
        try:
            url = response.url or ""
            if "/conversation/" not in url or "get_" not in url:
                return
            if all(token not in url for token in (
                "get_current_conversation_list",
                "get_last_conversation_list",
                "get_recent_conversation_list",
                "get_history_conversation_list",
                "search_conversation",
            )):
                return
            if response.status != 200:
                return
            text = response.text()
            if not text or not text.lstrip().startswith("{"):
                return
            payload = json.loads(text)
            data = payload.get("data")
            if isinstance(data, list):
                self._cache_conversation_list(data, source_url=url)
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
            textarea = None
            try:
                self.page.wait_for_selector("[data-qa-id='qa-send-message-textarea']", state="visible", timeout=3000)
            except Exception:
                pass
            textarea = self.page.query_selector("[data-qa-id='qa-send-message-textarea']")
            if textarea:
                textarea.fill(chunk)
            else:
                raise Exception("输入框未找到.")
            time.sleep(random.uniform(0.6, 1.2))
            try:
                self.page.wait_for_selector("[data-qa-id='qa-send-message-button']", state="visible", timeout=3000)
            except Exception:
                pass
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

    def _parse_session_key(self, session_key):
        if not session_key or not isinstance(session_key, str):
            return "", ""
        if not session_key.startswith("conv::"):
            return "", ""
        raw = session_key[len("conv::"):]
        if ":" not in raw:
            return "", ""
        attr, value = raw.split(":", 1)
        attr = (attr or "").strip()
        value = (value or "").strip()
        if not attr or not value:
            return "", ""
        return attr, value

    def _is_biz_session_key(self, session_key):
        attr, value = self._parse_session_key(session_key)
        return attr == "biz" and bool(self._normalize_text(value))

    def _extract_conversation_nickname(self, item):
        if not item:
            return ""
        # 新版飞鸽会话项通常会把昵称放在 title 属性里
        title_selectors = [
            '[title]',
            '[class*="name"][title]',
            '[class*="nick"][title]',
        ]
        for selector in title_selectors:
            try:
                el = item.query_selector(selector)
                if not el:
                    continue
                title = (el.get_attribute('title') or '').strip()
                if title:
                    return re.sub(r"\s+", " ", title)
            except Exception:
                continue
        try:
            text = re.sub(r"\s+", " ", (item.inner_text() or '').strip())
        except Exception:
            text = ''
        if not text:
            return ''
        # 文本兜底：取首段昵称，剔除常见状态词
        text = re.sub(r"(重复来访|新客|老客|未读|已读|分钟前|小时前|刚刚).*", "", text).strip()
        text = re.sub(r"\b\d{1,2}:\d{2}(:\d{2})?\b.*", "", text).strip()
        if text:
            return text[:40]
        return ''

    def _extract_conversation_item_meta(self, item):
        if not item:
            return {"nickname": "", "text": "", "preview": ""}
        nickname = self._extract_conversation_nickname(item)
        try:
            text = self._normalize_text(item.inner_text() or '')
        except Exception:
            text = ''
        preview = self._extract_preview_from_dom_text(text, nickname)
        return {
            "nickname": self._normalize_nickname(nickname),
            "text": text[:200],
            "preview": preview[:120],
        }

    def _match_cached_conversation(self, nickname="", full_text="", preview=""):
        nickname = self._normalize_nickname(nickname)
        full_text = self._normalize_text(full_text)
        preview = self._normalize_text(preview)
        candidate_ids = list(self.conversation_ids_by_nickname.get(nickname, []))
        if not candidate_ids:
            return None
        best_meta = None
        best_score = -1
        for biz_id in candidate_ids:
            meta = self.conversation_cache.get(biz_id)
            if not meta:
                continue
            score = 0
            if nickname and self._normalize_nickname(meta.get("nickname", "")) == nickname:
                score += 100
            cached_preview = self._normalize_text(meta.get("preview", ""))
            cached_dom_text = self._normalize_text(meta.get("dom_text", ""))
            if preview and cached_preview == preview:
                score += 40
            elif preview and cached_preview and preview in cached_preview:
                score += 25
            elif preview and cached_dom_text and preview in cached_dom_text:
                score += 20
            if full_text and cached_dom_text and cached_dom_text == full_text:
                score += 60
            elif full_text and cached_dom_text and full_text in cached_dom_text:
                score += 25
            score += min(int(max(0, time.time() - meta.get("updated_at", 0)) // 60), 10) * -1
            if score > best_score:
                best_meta = meta
                best_score = score
        return best_meta if best_score >= 100 else None

    def _remember_dom_hint(self, biz_id, item_meta):
        if not biz_id or not item_meta:
            return
        meta = self.conversation_cache.get(biz_id)
        if not meta:
            return
        dom_text = self._normalize_text(item_meta.get("text", ""))
        if dom_text:
            meta["dom_text"] = dom_text[:200]
        preview = self._normalize_text(item_meta.get("preview", ""))
        if preview and not meta.get("preview"):
            meta["preview"] = preview[:120]
        nickname = self._normalize_nickname(item_meta.get("nickname", ""))
        if nickname and not meta.get("nickname"):
            meta["nickname"] = nickname
        meta["updated_at"] = time.time()
        self.conversation_cache[biz_id] = meta
        self._rebuild_conversation_indexes()

    def _get_runtime_chat_state(self):
        try:
            return self.page.evaluate(
                """() => {
                    const store = window.__monaGlobalStore?.getData?.()?.initContextData?.Store?.instance;
                    if (!store) return null;
                    const bm = store.buyerMap;
                    const ci = store.conversationsInfo;
                    const currentConvId = ci?.currentConversation?.id || '';
                    const currentBuyerId = bm?.currentTalkingBuyerId || '';
                    const currentBuyerInfo = currentBuyerId && bm?.getInfo ? bm.getInfo(currentBuyerId) : null;
                    return {
                        currentConversationId: currentConvId,
                        currentBuyerId,
                        currentBuyerConversationId: currentBuyerInfo?._conversationId || '',
                        historyBuyers: Array.isArray(bm?.historyBuyers) ? bm.historyBuyers.slice() : [],
                        recentSystemConvList: Array.isArray(bm?.recentSystemConvList) ? bm.recentSystemConvList.slice() : [],
                        servicingBuyers: Array.isArray(bm?.servicingBuyers) ? bm.servicingBuyers.slice() : [],
                        waitReplyBuyers: Array.isArray(bm?.waitReplyBuyers) ? bm.waitReplyBuyers.slice() : [],
                        overThreeBuyers: Array.isArray(bm?.overThreeBuyers) ? bm.overThreeBuyers.slice() : [],
                        aiServerBuyers: Array.isArray(bm?.aiServerBuyers) ? bm.aiServerBuyers.slice() : [],
                        autoReplyBuyers: Array.isArray(bm?.autoReplyBuyers) ? bm.autoReplyBuyers.slice() : [],
                        humanReplyBuyers: Array.isArray(bm?.humanReplyBuyers) ? bm.humanReplyBuyers.slice() : [],
                        systemConvList: Array.isArray(bm?.systemConvList) ? bm.systemConvList.slice() : [],
                        activeTab: (() => {
                            const active = document.querySelector('.auxo-tabs-tab.auxo-tabs-tab-active');
                            return active ? (active.innerText || '').replace(/\\s+/g, ' ').trim() : '';
                        })(),
                    };
                }"""
            )
        except Exception:
            return None

    def _get_runtime_current_conversation_id(self):
        state = self._get_runtime_chat_state() or {}
        current_id = self._normalize_text(state.get("currentConversationId", ""))
        if current_id:
            return current_id
        return self._normalize_text(state.get("currentBuyerConversationId", ""))

    def _get_visible_conversation_rows(self):
        try:
            return self.page.evaluate(
                """() => {
                    const norm = (s) => (s || '').replace(/\\s+/g, ' ').trim();
                    return Array.from(document.querySelectorAll('[data-kora="conversation"][data-qa-id="qa-conversation-chat-item"]')).map((el, index) => ({
                        index,
                        btm: el.getAttribute('data-btm-id') || '',
                        title: el.querySelector('[title]')?.getAttribute('title') || '',
                        text: norm(el.innerText || ''),
                        className: el.className || '',
                    }));
                }"""
            )
        except Exception:
            return []

    def _activate_conversation_tab(self, tab_name):
        target = (tab_name or "").strip().lower()
        if target not in ("current", "recent"):
            return False
        selector = '[data-qa-id="qa-active-chat-tab"]' if target == "current" else '[data-qa-id="qa-last-chat-tab"]'
        try:
            self.page.locator(selector).click(timeout=3000)
            time.sleep(0.6)
            return True
        except Exception:
            return False

    def _click_conversation_row_by_index(self, index):
        try:
            self.page.evaluate(
                """(idx) => {
                    const items = Array.from(document.querySelectorAll('[data-kora="conversation"][data-qa-id="qa-conversation-chat-item"]'));
                    const target = items[idx];
                    if (target) target.click();
                }""",
                int(index),
            )
            time.sleep(0.8)
            return True
        except Exception:
            return False

    def _cache_row_mapping(self, biz_id, tab_name, row):
        if not biz_id or not row:
            return
        self.conversation_row_cache[biz_id] = {
            "tab": tab_name,
            "index": row.get("index"),
            "btm": row.get("btm", ""),
            "title": self._normalize_nickname(row.get("title", "")),
            "text": self._normalize_text(row.get("text", ""))[:200],
            "ts": time.time(),
        }

    def _try_cached_row_mapping(self, target_biz_id):
        cache = self.conversation_row_cache.get(target_biz_id)
        if not cache:
            return False
        tab_name = cache.get("tab", "")
        row_index = cache.get("index")
        if row_index is None:
            return False
        if tab_name:
            self._activate_conversation_tab(tab_name)
        rows = self._get_visible_conversation_rows()
        if row_index >= len(rows):
            return False
        row = rows[row_index]
        if cache.get("btm") and row.get("btm") != cache.get("btm"):
            return False
        if cache.get("title") and self._normalize_nickname(row.get("title", "")) != cache.get("title"):
            return False
        if not self._click_conversation_row_by_index(row_index):
            return False
        current_biz = self._get_runtime_current_conversation_id()
        if current_biz == target_biz_id:
            self._cache_row_mapping(target_biz_id, tab_name, row)
            return True
        return False

    def _try_switch_via_recent_order(self, target_biz_id, target_meta=None):
        state = self._get_runtime_chat_state() or {}
        buyer_id = self._normalize_text((target_meta or {}).get("pigeonUid", ""))
        if not buyer_id and target_biz_id:
            buyer_id = target_biz_id.split(":", 1)[0].strip()
        if not buyer_id:
            return False
        history_buyers = [self._normalize_text(v) for v in state.get("historyBuyers", []) if self._normalize_text(v)]
        system_buyers = [self._normalize_text(v) for v in state.get("recentSystemConvList", []) if self._normalize_text(v)]
        rows = []
        if buyer_id in history_buyers:
            if not self._activate_conversation_tab("recent"):
                return False
            rows = [r for r in self._get_visible_conversation_rows() if "recent" in (r.get("btm") or "")]
            pos = history_buyers.index(buyer_id)
        elif buyer_id in system_buyers:
            if not self._activate_conversation_tab("recent"):
                return False
            rows = [r for r in self._get_visible_conversation_rows() if "systemConv" in (r.get("btm") or "")]
            pos = system_buyers.index(buyer_id)
        else:
            return False
        if pos >= len(rows):
            return False
        row = rows[pos]
        if not self._click_conversation_row_by_index(row.get("index", -1)):
            return False
        current_biz = self._get_runtime_current_conversation_id()
        if current_biz == target_biz_id:
            self._cache_row_mapping(target_biz_id, "recent", row)
            return True
        return False

    def _probe_switch_in_tab(self, target_biz_id, tab_name):
        if not self._activate_conversation_tab(tab_name):
            return False
        rows = self._get_visible_conversation_rows()
        for row in rows:
            btm = row.get("btm") or ""
            if not btm:
                continue
            if tab_name == "recent" and not ("recent" in btm or "systemConv" in btm):
                continue
            if tab_name == "current" and "recent" in btm:
                continue
            if not self._click_conversation_row_by_index(row.get("index", -1)):
                continue
            current_biz = self._get_runtime_current_conversation_id()
            if current_biz == target_biz_id:
                self._cache_row_mapping(target_biz_id, tab_name, row)
                return True
        return False

    def _switch_to_session(self, session_key):
        attr, value = self._parse_session_key(session_key)
        if not attr or not value:
            return False
        norm_value = self._normalize_text(value)
        current_biz = self._get_runtime_current_conversation_id()
        current_session = f"conv::biz:{current_biz}" if current_biz else self.get_current_session_key()
        if current_session == session_key:
            return True
        chat_items = self.page.query_selector_all(
            '[data-kora="conversation"][data-qa-id="qa-conversation-chat-item"]'
        )
        if attr == "biz":
            target_meta = self.conversation_cache.get(norm_value)
            if self._try_cached_row_mapping(norm_value):
                return True
            if self._try_switch_via_recent_order(norm_value, target_meta):
                return True
            if self._probe_switch_in_tab(norm_value, "current"):
                return True
            if self._probe_switch_in_tab(norm_value, "recent"):
                return True
            if not target_meta:
                return False
            target_nickname = self._normalize_nickname(target_meta.get("nickname", ""))
            target_preview = self._normalize_text(target_meta.get("preview", ""))
            target_dom_text = self._normalize_text(target_meta.get("dom_text", ""))
            exact_dom_match = None
            exact_preview_match = None
            nickname_match = None
            for item in chat_items:
                item_meta = self._extract_conversation_item_meta(item)
                if target_dom_text and item_meta["text"] == target_dom_text:
                    exact_dom_match = (item, item_meta)
                    break
                if target_nickname and item_meta["nickname"] != target_nickname:
                    continue
                if target_preview and item_meta["preview"] == target_preview and not exact_preview_match:
                    exact_preview_match = (item, item_meta)
                if not nickname_match:
                    nickname_match = (item, item_meta)
            chosen = exact_dom_match or exact_preview_match or nickname_match
            if not chosen:
                return False
            chosen[0].click()
            time.sleep(0.5)
            self._remember_dom_hint(norm_value, chosen[1])
            return True
        if attr == "nickname":
            for item in chat_items:
                item_meta = self._extract_conversation_item_meta(item)
                if item_meta["nickname"] == norm_value:
                    item.click()
                    time.sleep(0.5)
                    return True
            return False
        if attr == "text":
            for item in chat_items:
                item_meta = self._extract_conversation_item_meta(item)
                if item_meta["text"] and item_meta["text"] == norm_value:
                    item.click()
                    time.sleep(0.5)
                    return True
            return False
        for item in chat_items:
            try:
                item_val = (item.get_attribute(attr) or "").strip()
            except Exception:
                item_val = ""
            if not item_val:
                continue
            if item_val == value:
                item.click()
                time.sleep(0.5)
                return True
        return False

    def sendMsgToSession(self, session_key, msg, switch_back=True):
        if not self._is_biz_session_key(session_key) or not msg:
            return False
        previous_session = self.get_current_session_key()
        if not self._is_biz_session_key(previous_session):
            previous_session = ''
        if not self._switch_to_session(session_key):
            return False
        current_session = self.get_current_session_key()
        if current_session != session_key:
            return False
        self.sendMsg(msg)
        if switch_back and previous_session and previous_session != session_key:
            try:
                self._switch_to_session(previous_session)
            except Exception:
                pass
        return True

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
        chat_key = all_msgs.get('session_key') or self._get_chat_cache_key()
        previous_cursor = self.chat_last_message_cursor.get(chat_key)
        current_max_index = max((self._to_int_index(msg.get('index')) for msg in friend_msgs), default=0)
        self.chat_last_message_cursor[chat_key] = current_max_index
        if config_checked_greetings==1 and config_greetings:
            greeting_key = self._get_greeting_key()
            if self._should_send_greeting(greeting_key, my_msgs, config_greetings):
                self.sendBtnMsg(config_greetings)
        if previous_cursor is not None:
            diff_messages = [msg for msg in friend_msgs if self._to_int_index(msg.get('index')) > previous_cursor]
            if friend_msgs:
                self.chat_last_friend_index[chat_key] = current_max_index
            diff_messages = self._append_link_info_messages(diff_messages)
            if diff_messages:
                diff_messages = self._append_product_panel_message(diff_messages)
                diff_messages = self._filter_unseen_messages(chat_key, diff_messages)
                self._remember_seen_messages(chat_key, diff_messages)
                return diff_messages
            return []
        # 如果我的消息为空 说明都是未读
        service_read_index = self._to_int_index(all_msgs.get('service_read_index'))
        if service_read_index > 0:
            unread_messages = [msg for msg in friend_msgs if self._to_int_index(msg.get('index')) > service_read_index]
            if friend_msgs:
                self.chat_last_friend_index[chat_key] = current_max_index
            unread_messages = self._append_link_info_messages(unread_messages)
            if unread_messages:
                unread_messages = self._append_product_panel_message(unread_messages)
                unread_messages = self._filter_unseen_messages(chat_key, unread_messages)
                self._remember_seen_messages(chat_key, unread_messages)
                return unread_messages
        if not my_msgs:
            if friend_msgs:
                self.chat_last_friend_index[chat_key] = current_max_index
            msgs = self._append_link_info_messages(friend_msgs)
            msgs = self._append_product_panel_message(msgs)
            msgs = self._filter_unseen_messages(chat_key, msgs)
            self._remember_seen_messages(chat_key, msgs)
            return msgs
        # 取最后一个我的消息
        my_last_msg= my_msgs[-1]
        # 取我的最后一条消息的下标
        my_last_index = self._to_int_index(my_last_msg['index'])
        # 记录一下最后五条 用于定位消息
        self.last_messages = self._getLastMessages(friend_msgs)
        if not friend_msgs:
            return []
        self.chat_last_friend_index[chat_key] = current_max_index
        filtered_messages = [msg for msg in friend_msgs if self._to_int_index(msg.get('index')) > my_last_index]
        filtered_messages = self._append_link_info_messages(filtered_messages)
        if filtered_messages:
            filtered_messages = self._append_product_panel_message(filtered_messages)
            filtered_messages = self._filter_unseen_messages(chat_key, filtered_messages)
            self._remember_seen_messages(chat_key, filtered_messages)
            return filtered_messages
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

        return user_nickname

    def getCurrentChatName(self):
        return self._getCurrentUserName()

    def get_current_session_key(self):
        runtime_current_id = self._get_runtime_current_conversation_id()
        if runtime_current_id:
            return f"conv::biz:{runtime_current_id}"
        username = self._getCurrentUserName()
        active_item = None
        active_meta = {"nickname": "", "text": "", "preview": ""}
        chat_items = self.page.query_selector_all(
            '[data-kora="conversation"][data-qa-id="qa-conversation-chat-item"]'
        )
        if username:
            norm_username = self._normalize_nickname(username)
            for item in chat_items:
                item_meta = self._extract_conversation_item_meta(item)
                if item_meta["nickname"] == norm_username:
                    active_item = item
                    active_meta = item_meta
                    break
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
                    const nameEl = active.querySelector('[title], [class*="name"][title], [class*="nick"][title]');
                    if (nameEl) {
                        const nick = norm(nameEl.getAttribute('title') || nameEl.textContent || '');
                        if (nick) return `nickname:${nick.slice(0, 80)}`;
                    }
                    const text = norm(active.innerText);
                    return text ? `text:${text.slice(0, 80)}` : '';
                }""",
                username or '',
            )
            if key:
                direct_key = f"conv::{key}"
                attr, value = self._parse_session_key(direct_key)
                if attr in ("data-conversation-id", "data-session-id", "data-id", "data-user-id", "id"):
                    return direct_key
        except Exception:
            pass
        matched = self._match_cached_conversation(
            nickname=active_meta.get("nickname", "") or username,
            full_text=active_meta.get("text", ""),
            preview=active_meta.get("preview", ""),
        )
        if matched and matched.get("bizConversationId"):
            self._remember_dom_hint(matched["bizConversationId"], active_meta)
            return f"conv::biz:{matched['bizConversationId']}"
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

    def _to_int_index(self, value):
        try:
            return int(str(value or "0"))
        except Exception:
            return 0

    def _safe_json_loads(self, raw):
        if isinstance(raw, dict):
            return raw
        if not raw or not isinstance(raw, str):
            return {}
        try:
            return json.loads(raw)
        except Exception:
            return {}

    def _pick_first_product(self, static_data):
        data = self._safe_json_loads(static_data)
        if not data:
            return {}
        for key in ("sale_goods", "b_goods", "goods", "products"):
            goods = data.get(key)
            if isinstance(goods, list) and goods:
                item = goods[0]
                if isinstance(item, dict):
                    return item
        return {}

    def _extract_price_from_product(self, product):
        if not isinstance(product, dict):
            return ""
        for key in ("current_price", "discount_price"):
            price_info = product.get(key)
            if isinstance(price_info, dict):
                price = self._normalize_text(price_info.get("price", ""))
                if price:
                    return price
        for key in ("price", "origin_price"):
            price = self._normalize_text(product.get(key, ""))
            if price:
                return price
        return ""

    def _extract_product_info_from_static_data(self, static_data):
        data = self._safe_json_loads(static_data)
        if not data:
            return {}
        product = self._pick_first_product(data)
        title = self._normalize_text(
            product.get("product_name")
            or product.get("title")
            or product.get("product_name_two_lines")
            or ""
        )
        product_id = self._normalize_text(
            product.get("product_id")
            or data.get("product_id")
            or ""
        )
        price = self._extract_price_from_product(product)
        sell_num = self._normalize_text(product.get("sell_num_desc", ""))
        return {
            "title": title,
            "price": price,
            "product_id": product_id,
            "sell_num": sell_num,
            "raw": data,
        }

    def _get_runtime_current_messages(self):
        try:
            snapshot = self.page.evaluate(
                """() => {
                    const store = window.__monaGlobalStore?.getData?.()?.initContextData?.Store?.instance;
                    if (!store) return null;
                    const buyerMap = store.buyerMap;
                    const convId =
                        store.conversationsInfo?.currentConversation?.id ||
                        (buyerMap?.currentTalkingBuyerId && buyerMap?.getInfo
                            ? buyerMap.getInfo(buyerMap.currentTalkingBuyerId)?._conversationId
                            : '') ||
                        '';
                    if (!convId) return null;
                    const conv = store.conversationsInfo?.conversationMap?.get?.(convId);
                    const bucket = store.conversationsInfo?.messagesByConversationId?.get?.(convId);
                    const serviceMember = Array.isArray(conv?.members)
                        ? conv.members.find((m) => m?.role === 'service')
                        : null;
                    const buyerMember = Array.isArray(conv?.members)
                        ? conv.members.find((m) => m?.role === 'buyer')
                        : null;
                    const messages = bucket?.map
                        ? Array.from(bucket.map.values()).map((m) => ({
                              id: m?.id || '',
                              serverId: m?.serverId || '',
                              indexInConversation: m?.indexInConversation || '',
                              indexInConversationV2: m?.indexInConversationV2 || '',
                              conversationId: m?.conversationId || '',
                              sender: m?.sender || '',
                              content: m?.content || '',
                              type: m?.type,
                              ext: m?.ext || {},
                          }))
                        : [];
                    return {
                        conversationId: convId,
                        buyerId: conv?.buyerId || buyerMember?.id || '',
                        currentTalkId: conv?.currentTalkId || '',
                        serviceReadIndex: serviceMember?.pigeonReadIndex || bucket?.serviceReadIndex || '0',
                        buyerReadIndex: buyerMember?.pigeonReadIndex || bucket?.buyerReadIndex || '0',
                        selfId: store.selfInfo?.id || '',
                        serviceEntityId: store.shopInfo?.serviceEntityId || conv?.serviceEntityId || '',
                        messages,
                    };
                }"""
            )
        except Exception:
            return None
        if not snapshot or not snapshot.get("conversationId"):
            return None
        messages = snapshot.get("messages") or []
        messages.sort(key=lambda m: (self._to_int_index(m.get("indexInConversation")), str(m.get("serverId") or m.get("id") or "")))
        snapshot["messages"] = messages
        return snapshot

    def _build_store_product_hints(self, raw_messages):
        hints = {}
        for msg in raw_messages:
            ext = msg.get("ext") or {}
            if str(ext.get("type") or "") != "template_card":
                continue
            product = self._extract_product_info_from_static_data(ext.get("static_data", ""))
            if not product.get("title"):
                continue
            goods_id = self._normalize_text(ext.get("goods_id") or product.get("product_id") or "")
            if goods_id:
                hints[goods_id] = product
        return hints

    def _convert_store_messages(self, snapshot):
        if not snapshot:
            return None
        raw_messages = snapshot.get("messages") or []
        if not raw_messages:
            return {
                "customer_messages": [],
                "my_messages": [],
                "session_key": f"conv::biz:{snapshot.get('conversationId', '')}",
                "service_read_index": snapshot.get("serviceReadIndex", "0"),
            }
        username = self._getCurrentUserName()
        buyer_id = self._normalize_text(snapshot.get("buyerId", ""))
        self_id = self._normalize_text(snapshot.get("selfId", ""))
        service_entity_id = self._normalize_text(snapshot.get("serviceEntityId", ""))
        product_hints = self._build_store_product_hints(raw_messages)
        user_enter_goods_ids = {
            self._normalize_text((msg.get("ext") or {}).get("goods_id", ""))
            for msg in raw_messages
            if str((msg.get("ext") or {}).get("type") or "") == "user_enter_from_goods"
        }

        customer_messages = []
        my_messages = []

        for raw in raw_messages:
            ext = raw.get("ext") or {}
            ext_type = str(ext.get("type") or "")
            sender_role = str(ext.get("sender_role") or "")
            sender = self._normalize_text(raw.get("sender", ""))
            content = self._normalize_text(raw.get("content", ""))
            goods_id = self._normalize_text(ext.get("goods_id", ""))
            product = self._extract_product_info_from_static_data(ext.get("static_data", ""))
            if goods_id and product_hints.get(goods_id):
                merged = dict(product_hints[goods_id])
                merged.update({k: v for k, v in product.items() if v})
                product = merged
            idx = raw.get("indexInConversation") or "0"

            if ext_type == "template_card" and content == "[商品]":
                parts = []
                if product.get("title"):
                    parts.append(f"我要咨询商品名称:{product['title']}")
                if product.get("price"):
                    parts.append(f"价格:{product['price']}")
                if product.get("product_id"):
                    parts.append(f"商品ID:{product['product_id']}")
                customer_messages.append({
                    "index": idx,
                    "who": username,
                    "type": "card",
                    "good_name": product.get("title", ""),
                    "content": " ".join(parts).strip() or content,
                    "product": product,
                    "server_id": raw.get("serverId", ""),
                    "message_id": raw.get("id", ""),
                })
                continue

            if ext_type == "template_card" and "用户正在查看商品" in content and goods_id in user_enter_goods_ids:
                continue

            if ext_type == "user_enter_from_goods" or (ext_type == "template_card" and "用户正在查看商品" in content):
                product_name = product.get("title", "")
                if not product_name:
                    product_name = content
                customer_messages.append({
                    "index": idx,
                    "who": username,
                    "type": "from_info",
                    "source": "system",
                    "good_name": product_name,
                    "content": f"我浏览了商品:{product_name}" if product_name else "我浏览了商品",
                    "product": product,
                    "server_id": raw.get("serverId", ""),
                    "message_id": raw.get("id", ""),
                })
                continue

            if self._is_system_notice_text(content):
                continue

            if sender_role == "2" or (self_id and sender == self_id) or (service_entity_id and sender == service_entity_id):
                if content and "此消息由机器人自动回复" not in content and "很高兴为您服务，请问有什么可以帮您？" not in content:
                    my_messages.append({
                        "index": idx,
                        "type": "my",
                        "content": content,
                        "server_id": raw.get("serverId", ""),
                        "message_id": raw.get("id", ""),
                    })
                continue

            if sender_role == "1" or (buyer_id and sender == buyer_id):
                if content:
                    customer_messages.append({
                        "index": idx,
                        "who": username,
                        "type": "text",
                        "content": content,
                        "server_id": raw.get("serverId", ""),
                        "message_id": raw.get("id", ""),
                    })

        return {
            "customer_messages": customer_messages,
            "my_messages": my_messages,
            "session_key": f"conv::biz:{snapshot.get('conversationId', '')}",
            "service_read_index": snapshot.get("serviceReadIndex", "0"),
        }

    def _getAllCurrentMsgFromDom(self):
        self._scroll_current_chat_to_bottom()
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
                 if not robot_div and '很高兴为您服务，请问有什么可以帮您？' not in message_content:
                     my_messages.append({
                         'index':index,
                         'type': 'my',
                         'content': message_content
                     })
        #         客户消息和我的消息 包括其他消息列如 info消息
        all_message = {'customer_messages':customer_messages,"my_messages":my_messages}
        return all_message


    def _scroll_current_chat_to_bottom(self):
        try:
            self.page.evaluate(
                """() => {
                    const touched = new Set();
                    const touch = (el) => {
                        if (!el || touched.has(el)) return;
                        touched.add(el);
                        try {
                            if (typeof el.scrollIntoView === 'function') {
                                el.scrollIntoView({ block: 'end' });
                            }
                        } catch (e) {}
                        let node = el;
                        while (node) {
                            try {
                                if (node.scrollHeight && node.clientHeight && node.scrollHeight > node.clientHeight + 20) {
                                    node.scrollTop = node.scrollHeight;
                                }
                            } catch (e) {}
                            node = node.parentElement;
                        }
                    };
                    const lastMsg = document.querySelector('.msgItemWrap:last-child');
                    if (lastMsg) touch(lastMsg);
                    const candidates = Array.from(document.querySelectorAll('div')).filter((el) => {
                        const classText = `${el.className || ''} ${el.getAttribute('data-qa-id') || ''}`;
                        return /msg|message|chat|scroll|list|content/i.test(classText);
                    });
                    candidates.sort((a, b) => (b.scrollHeight || 0) - (a.scrollHeight || 0)).slice(0, 12).forEach(touch);
                }"""
            )
            time.sleep(0.1)
        except Exception:
            return

    def _getAllCurrentMsg(self):
        snapshot = self._get_runtime_current_messages()
        store_messages = self._convert_store_messages(snapshot)
        if store_messages is not None:
            return store_messages
        return self._getAllCurrentMsgFromDom()


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

    def _message_unique_key(self, msg):
        msg_type = str(msg.get('type', '') or '')
        source = str(msg.get('source', '') or '')
        message_id = str(msg.get('message_id', '') or '')
        server_id = str(msg.get('server_id', '') or '')
        index = str(msg.get('index', '') or '')
        if message_id or server_id:
            return "|".join([
                msg_type,
                source,
                f"mid:{message_id}",
                f"sid:{server_id}",
            ])
        return "|".join([
            msg_type,
            source,
            f"idx:{index}",
            str(msg.get('content', '') or '').strip(),
            str(msg.get('good_name', '') or '').strip(),
            str(msg.get('src', '') or '').strip(),
            str(msg.get('product_link', '') or '').strip(),
        ])

    def _get_seen_message_cache(self, chat_key):
        cache = self.chat_seen_message_keys.get(chat_key)
        if cache is None:
            cache = OrderedDict()
            self.chat_seen_message_keys[chat_key] = cache
        return cache

    def _remember_seen_messages(self, chat_key, messages):
        if not chat_key or not messages:
            return
        cache = self._get_seen_message_cache(chat_key)
        for msg in messages:
            key = self._message_unique_key(msg)
            if key in cache:
                cache.move_to_end(key)
            else:
                cache[key] = 1
            while len(cache) > self.chat_seen_message_limit:
                cache.popitem(last=False)

    def _filter_unseen_messages(self, chat_key, messages):
        if not chat_key or not messages:
            return list(messages or [])
        cache = self._get_seen_message_cache(chat_key)
        unseen = []
        for msg in messages:
            key = self._message_unique_key(msg)
            if key in cache:
                continue
            unseen.append(msg)
        return unseen

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
        chat_key = all_msgs.get('session_key') or self._get_chat_cache_key()
        print(friend_messages)
        if not friend_messages:
            return  new_messages
        if config_checked_greetings==1 and config_greetings:
            greeting_key = self._get_greeting_key()
            if self._should_send_greeting(greeting_key, my_messages, config_greetings):
                self.sendBtnMsg(config_greetings)
        current_counts = self._build_message_counts(friend_messages)
        previous_cursor = self.chat_last_message_cursor.get(chat_key)
        current_max_index = max(self._to_int_index(msg.get('index')) for msg in friend_messages)
        self.chat_last_friend_index[chat_key] = current_max_index
        self.chat_seen_friend_counts[chat_key] = current_counts
        if previous_cursor is None:
            self.chat_last_message_cursor[chat_key] = current_max_index
            self._remember_seen_messages(chat_key, friend_messages)
            print("\n没有新的消息。")
            print(f" - {new_messages}")
            return new_messages

        new_messages = [msg for msg in friend_messages if self._to_int_index(msg.get('index')) > previous_cursor]
        self.chat_last_message_cursor[chat_key] = current_max_index
        if not new_messages:
            print(f" - {new_messages}")
            return new_messages
        # print('# =============')
        new_messages = self._append_link_info_messages(new_messages)
        new_messages = self._append_product_panel_message(new_messages)
        new_messages = self._filter_unseen_messages(chat_key, new_messages)
        self._remember_seen_messages(chat_key, new_messages)
        print(f" - {new_messages}")  # 打印每条朋友消息
        return new_messages


    #刷新页面
    def pageReload(self):
        self.page.reload()
        # 确保页面加载完成
        self.page.wait_for_load_state('load')
        self.page.evaluate(f"window.scrollBy(0, {random.randint(-10, 10)})")
