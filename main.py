#!/usr/bin/env python
# -*- coding:utf-8 -*-
import uuid
import json
from PyQt5.QtWidgets import QApplication
from PyQt5.QtWidgets import *
from dashscope import base_http_api_url
from utils import req_util
from utils.feishu import send_feishu_message
from  utils.tools import *
import threading
from PyQt5 import QtCore
from PyQt5 import QtWebEngineWidgets
from PyQt5.QtWebChannel import QWebChannel
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import *
from PyQt5.QtGui import QIcon
import time
import random
import re
import queue
from collections import deque
from llm.cozeUtil import CozeUtil
from llm.bailianUtil import BalianUtil
from configUtil import *
from llm.fastGptUtil import FastGPTClient
import logging
from utils.db_utils import DatabaseManager
from PyQt5.QtCore import QThread, pyqtSignal


db_manager = DatabaseManager()
db_manager.create_tables()

# coze api
coze_api_base = "https://api.coze.cn"
# 定时查询时间
wait = 0.5  # 设置1秒查看一次是否有新消息
# 人工介入
manual_intervention = False

user_id = None

# 获取电脑的MAC地址
mac = uuid.getnode()
# 生成基于命名空间和名称的UUID
namespace = uuid.NAMESPACE_DNS
name = str(mac)
unique_id = uuid.uuid5(namespace, name)
# print(unique_id)

# unique_id = uuid.uuid4()
# 防止每次都重复回复加随机语
random_reply_word=['亲','亲亲']
random_reply_character=[',','.','!','~','。','。。','~~','-','--','*','!!','..','=_=','^_^','*_*','**','#','##','^','@','&','`']

class JsBridge(QObject):
    
    platformStart = pyqtSignal(int)  # 定义信号
    platformStop = pyqtSignal(str)  # 定义信号

    def __init__(self, web_view):
        super().__init__()
        self.webView = web_view    
    '''
    共享类  js调用python方法
    '''
    # 启动平台
    @pyqtSlot(int, result=str)
    def js_start_platform(self, id):
        self.platformStart.emit(id)

    # 停止平台
    @pyqtSlot(str, result=str)
    def js_stop_platform(self, platform):
        print(platform)
        global chose_platform
        chose_platform = platform
        self.platformStop.emit(platform)

    # 转人工
    @pyqtSlot(bool, result=str)
    def js_transfer_type(self, is_human):
        print(is_human)
        global manual_intervention
        manual_intervention = is_human

    # 添加平台
    @pyqtSlot(str, result=str)
    def js_add_platform(self, platform_info):
        platform_info = json.loads(platform_info)
        result = False
        try:
            # platform_name, platform_type,alias_name, transfrom_name, transfrom_keywork, designated_person,connect_type_id,token_id,token,bot_id, refresh_interval
            result = db_manager.insert_platform(platform_info['platform_name'],
                                                platform_info['platform_type'],
                                                platform_info['alias_name'],
                                                platform_info['transfer_name'],
                                                platform_info['transfer_keyword'],
                                                platform_info['replay_name'],
                                                int(platform_info['connect_type_id']),
                                                int(platform_info['token_id']),
                                                platform_info['token'],
                                                platform_info['bot_id'],
                                                int(platform_info['refresh_time']),
                                                platform_info['greetings'],
                                                platform_info['username'],
                                                platform_info['pwd'],
                                                platform_info['feishu_url'],
                                                )
        except Exception as e:
            print(f"错误: {str(e)}")
        if result:
            return 'success'
        else:
            return 'error'

    # 修改平台
    @pyqtSlot(str, result=str)
    def js_update_platform(self, platform_info):
        platform_info = json.loads(platform_info)
        result = False
        try:
            update_info={
                'platform_name':platform_info['platform_name'],
                'platform_type':platform_info['platform_type'],
                'alias_name':platform_info['alias_name'],
                'transfrom_name':platform_info['transfer_name'],
                'transfrom_keywork':platform_info['transfer_keyword'],
                'designated_person':platform_info['replay_name'],
                'connect_type_id':int(platform_info['connect_type_id']),
                'token_id':int(platform_info['token_id']),
                'token':platform_info['token'],
                'bot_id':platform_info['bot_id'],
                'refresh_interval':int(platform_info['refresh_time']),
                'greetings':platform_info['greetings'],
                'username':platform_info['username'],
                'pwd':platform_info['pwd'],
                'feishu_url':platform_info['feishu_url'],

            }
            # platform_name, platform_type,alias_name, transfrom_name, transfrom_keywork, designated_person,connect_type_id,token_id,token,bot_id, refresh_interval
            result = db_manager.update_platform(int(platform_info['id']),**update_info)

        except Exception as e:
            print(f"错误: {str(e)}")
        if result:
            return 'success'
        else:
            return 'error'

    # 是否开启问候语和密码登录
    @pyqtSlot(str, result=str)
    def js_update_greetings_or_loginpwd(self, platform_info):
        platform_info = json.loads(platform_info)
        result = False
        try:
            update_info={}
            if platform_info['type']=="greetings":
                update_info={
                    'checked_greetings':platform_info['checked_greetings'],
                }
            elif  platform_info['type']=="pwd_login":
                update_info={
                    'checked_pwd_login':platform_info['checked_pwd_login'],
                }
            elif  platform_info['type']=="feishu":
                update_info={
                    'checked_feishu':platform_info['checked_feishu'],
                }

            result = db_manager.update_platform(int(platform_info['id']),**update_info)

        except Exception as e:
            print(f"错误: {str(e)}")
        if result:
            return 'success'
        else:
            return 'error'

    # 删除平台
    @pyqtSlot(int,str, result=str)
    def js_delete_platform(self, id,file):
        print(id)
        result = db_manager.delete_platform(id)
        try:
            file_path = get_config_path(file)
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"文件已删除：{file_path}")
            else:
                print(f"文件不存在：{file_path}")
        except PermissionError:
            print(f"权限不足，无法删除文件：{file_path}")
        except Exception as e:
            print(f"发生错误：{e}")
        print(result)
        if result:
            return 'success'
        else:
            return 'error'

    # 获取平台
    @pyqtSlot(result=str)
    def js_get_platform(self):
        result = db_manager.get_platforms()
        return json.dumps(result)
    
    #获取用户
    @pyqtSlot(result=str)    
    def js_get_user(self):
        result = db_manager.get_first_user()
        if result:
            username = result['username'];
            password = result['password'];
            data = req_util.login_user(username,password,is_insert=False); 
            if data['code'] == 'success':
                global user_id
                user_id = data['message']
            return   json.dumps(data)
        return json.dumps({'code':'error','message':'未登录'} )

    # 登录
    @pyqtSlot(str, result=str)  
    def js_login(self,user):
        user = json.loads(user)
        username = user['username']
        password = user['password'] 
        data = req_util.login_user(username,password);  
        if data['code'] == 'success':
            global user_id
            user_id = data['message']
        return  json.dumps(data) ;       

    # 添加token
    @pyqtSlot(str, result=str)
    def js_add_token(self, all_set):
        config = json.loads(all_set)
        result = db_manager.insert_token(config['token'], config['bot_id'], '',config['type_id'],config['type_name'])
        if result:
            return 'success'
        else:
            return 'error'

    # 删除token
    @pyqtSlot(int, result=str)
    def js_delete_token(self, id):
        print(id)
        result = db_manager.delete_token(id)
        print(result)
        if result:
            return 'success'
        else:
            return 'error'

    # 获取token
    @pyqtSlot(result=str)
    def js_get_all_token(self):
        all_tokens = db_manager.get_tokens()
        return json.dumps(all_tokens)

class MainWindow(QMainWindow):
    # 添加一个自定义信号
    updateWebView = pyqtSignal(str)
    # 初始化
    def __init__(self, parent=None):
        self.platform_threads = {}  # 存储平台名称和对应的线程以及是否运行的标志

        super().__init__()

        if getattr(sys, 'frozen', None):
            basedir = sys._MEIPASS
        else:
            basedir = os.path.dirname(__file__)

        icon_path = os.path.join(basedir, 'hui.ico')
        # 然后使用 icon_path 作为 QIcon 构造函数的参数
        self.setWindowIcon(QIcon(icon_path))

        # 设置窗口始终在最前
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

        self.webView = QWebEngineView()
        self.webView.settings().setAttribute(QtWebEngineWidgets.QWebEngineSettings.JavascriptEnabled, True)
        # 设置跨域访问
        self.webView.page().settings().setAttribute(QtWebEngineWidgets.QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)

        channel = QWebChannel(self.webView.page())
        self.webView.page().setWebChannel(channel)
        self.python_bridge = JsBridge(self.webView)
        channel.registerObject("pythonBridge", self.python_bridge)
        layout = QVBoxLayout()
        layout.addWidget(self.webView)

        widget = QWidget()
        widget.setLayout(layout)
        self.setCentralWidget(widget)

        self.resize(800, 560)
        self.setWindowTitle('智能客服')
        qr = self.frameGeometry()
        cp = QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())
        self.show()
        html_path = QtCore.QUrl.fromLocalFile(basedir + "/static_src/index.html")
        self.webView.load(html_path)

        self.python_bridge.platformStart.connect(self.start_platform)
        self.python_bridge.platformStop.connect(self.stop_platform)
        # 连接信号到槽函数
        self.updateWebView.connect(self.onUpdateWebView)
        # self.timer = QTimer(self)
        # self.timer.timeout.connect(self.send_api_request)
        # self.timer.start(1000*30)  #间隔

    @pyqtSlot(str)
    def onUpdateWebView(self, fun):
        # 在这里安全地更新webview
        self.webView.page().runJavaScript(fun)

    class ApiRequestThread(QThread):
        finished = pyqtSignal()
        def run(self):
            try:
                if user_id:
                    print('开始发送心跳')
                    req_util.heart_beat(user_id,random_value=unique_id);
            except Exception as e:
                print(f'请求接口时发生错误: {str(e)}')
            self.finished.emit()

    def send_api_request(self):
        self.api_thread = self.ApiRequestThread()
        self.api_thread.start()

    # 开启平台
    def start_platform(self,id):
        # if not user_id:
        #     self.updateWebView.emit(f"py_add_msg({json.dumps('请先登录')});")
        #     return
        single_platform = db_manager.get_platform_by_id(id)
        platform = single_platform['platform_type']
        thread_name = f"thread-{single_platform['platform_type']}-{single_platform['id']}"  # 根据平台名称生成线程名
        if thread_name in self.platform_threads and self.platform_threads[thread_name]['thread'].is_alive():
            self.updateWebView.emit(f"py_add_msg({json.dumps('平台已在运行中')});")
            return
        print(f"》》》》》》》》启动选择了平台: {thread_name}")
        print(single_platform)
        if check_expiry():
            self.updateWebView.emit(f"py_add_msg({json.dumps('plug error')});")
            return
        try:
            stop_event = threading.Event()  # 创建一个事件对象
            thread = threading.Thread(target=self.start_running_task,
                                      args=(single_platform, stop_event),
                                      name=thread_name)# 设置线程名称
            thread.daemon = True  # 设置为守护线程，当主程序退出时子线程也会被强制结束
            self.platform_threads[thread_name] = {'thread': thread, 'stop_event': stop_event}  # 存储线程和事件
            thread.start()
        except Exception as e:
            logging.error(e)
            print(f"Failed to start platform {thread_name}: {str(e)}")

    def stop_platform(self,id):
        single_platform = db_manager.get_platform_by_id(id)
        thread_name = f"thread-{single_platform['platform_type']}-{single_platform['id']}"
        print(f"《《《《《《《《《《停止平台: {thread_name}")
        if thread_name in self.platform_threads:
            self.platform_threads[thread_name]['stop_event'].set()  # 发送停止信号
            self.platform_threads[thread_name]['thread'].join(timeout=8)
            if self.platform_threads[thread_name]['thread'].is_alive():
                self.updateWebView.emit(f"py_add_msg({json.dumps('平台停止中，请稍候...')});")
            else:
                del self.platform_threads[thread_name]  # 清理已停止的线程信息
                self.updateWebView.emit(f"py_add_msg({json.dumps('平台已停止')});")



    def start_running_task(self, single_platform,stop_event):
        if single_platform['platform_type'] == 'vx':
            self.wx_task(single_platform,stop_event)
        elif single_platform['platform_type']  == 'sph':
            self.sph_task(single_platform,stop_event)
        elif single_platform['platform_type'] =='wxxd':
            self.wxxd_task(single_platform,stop_event)
        elif single_platform['platform_type'] =='pdd':
            self.pdd_task(single_platform,stop_event)
        elif single_platform['platform_type'] =='qn':
            self.qn_task(single_platform,stop_event)
        elif single_platform['platform_type'] =='dd':
            self.dd_task(single_platform,stop_event)
        else:
            self.updateWebView.emit(f"py_add_msg({json.dumps('暂未开启该平台')});")

        print('wechat完成！')

    # 千牛
    def qn_task(self,single_platform,stop_event):
        from qianniu.qianniu import QianNiu
        try:
            config_chose_type = single_platform['connect_type_id']
            config_token = single_platform['token']
            config_bot_id = single_platform['bot_id']
            config_platform = f"{single_platform['platform_type']}-{single_platform['id']}"
            config_transfer_keyword = single_platform['transfrom_keywork']
            config_designated_person = single_platform['designated_person']
            config_refresh_interval = single_platform['refresh_interval']
            config_name = f"{single_platform['platform_name']}-{single_platform['alias_name']}"
            config_transfer_name = single_platform['transfrom_name']
            transfer_name = split_string_by_commas(config_transfer_name)
            designated_person = split_string_by_commas(config_designated_person)
            transfer_keyword = split_string_by_commas(config_transfer_keyword)

            coze_util = None
            bailian_util = None
            fast_util = None
            llm_prefix = 'coze'
            if config_chose_type== 0:
                coze_util =CozeUtil(config_token,coze_api_base,config_bot_id)
            elif config_chose_type== 1:
                bailian_util = BalianUtil(config_token,config_bot_id)
                llm_prefix = 'bailian'
            elif config_chose_type== 2:
                fast_util = FastGPTClient(config_bot_id,config_token)
                llm_prefix = 'fastgpt'

            qianniu = QianNiu()
            global manual_intervention
            while not stop_event.is_set():
                msgs = []
                try:
                    # 持续监听消息，有消息则对接大模型进行回复 转人工依然获取 防止转机器后获取已经回复的
                    msgs = qianniu.GetNextNewMessage(checkRedMessage=not manual_intervention)
                except Exception as e:
                    self.updateWebView.emit(f"py_add_msg({json.dumps(str(e)[:50])});")
                print(msgs)
                # 人工 跳出
                if manual_intervention:
                    print('=====人工========')
                    time.sleep(wait)
                    time.sleep(wait)
                    continue
                if msgs:
                    # 初始化一个空列表用于存储非空的文本内容
                    contents = []
                    chat_name = ''
                    # 遍历messages列表
                    for message in msgs:
                        if (message['type'] == 'text' or message['type'] == 'card' or message['type'] == 'img') and message['content'].strip():  # 确保类型为text且内容不为空（去除首尾空白后）
                            chat_name = message['who']
                            contents.append(message['content'])
                            # 处理消息逻辑
                        else:
                            #未识别的消息
                            chat_name = message['who']
                            contents.append('你好')
                    # 使用逗号拼接所有非空的内容
                    receive_msg = ','.join(contents)
                    # 查看是否指定回复
                    if  receive_msg and designated_person and chat_name not in designated_person:
                        self.updateWebView.emit(f"py_add_msg({json.dumps('不在指定回复人中,默认不回复')});")
                        time.sleep(wait)
                        continue
                    self.updateWebView.emit(f"py_add_msg({json.dumps('===============')});")
                    js_receive_msg = f"{config_name}|收到消息::{receive_msg}"
                    self.updateWebView.emit(f"py_add_msg({json.dumps(js_receive_msg)});")
                    # 查看是否触发转交
                    if receive_msg and transfer_name and transfer_keyword and any(s in receive_msg for s in transfer_keyword):
                        def single_transfer(name):
                            self.updateWebView.emit(f"py_add_msg({json.dumps(config_name+'|正在转接给:'+name)});")
                        qianniu.transferOther(transfer_name,single_transfer)
                        time.sleep(wait)
                        continue

                    self.updateWebView.emit(f"py_add_msg({json.dumps(config_name+'|正在请求模型回复...')});")
                    #定义一个匿名函数（lambda）作为回调函数，包含两个逻辑
                    def message_handler(reply,js_reply):
                        if '#转交#' in reply and transfer_name:
                            def single_transfer(name):
                                self.updateWebView.emit(f"py_add_msg({json.dumps(config_name+'|模型判断转交给:'+name)});")
                            qianniu.transferOther(transfer_name,single_transfer)
                            # qianniu.transferOther(transfer_name)
                            # self.updateWebView.emit(f"py_add_msg({json.dumps(config_name+'|模型判断转交给'+transfer_name)});")
                        else:
                            try:
                                reply = reply+'  '+ random.choice(random_reply_word) + random.choice(random_reply_character)
                                qianniu.sendMsg(reply)
                            except Exception as e:
                                self.updateWebView.emit(f"py_add_msg({json.dumps(str(e)[:50])});")
                            self.updateWebView.emit(f"py_add_msg({json.dumps(config_name+'|'+js_reply)});")
                    try:
                        if config_chose_type==0:
                            # 调用 send_message_and_poll 方法并传递回调函数
                            coze_util.send_message_and_poll('qn_coze'+chat_name, receive_msg, message_handler,)
                        elif config_chose_type==1:
                            bailian_util.send_message_and_poll(config_platform+'_bl'+chat_name, receive_msg, message_handler)
                        elif config_chose_type==2:
                            fast_util.send_chat_completion('qn_fast'+chat_name, receive_msg, message_handler)
                    except Exception as e:
                        self.updateWebView.emit(f"py_add_msg({json.dumps('智能体平台报错:'+str(e)[:50])});")

                time.sleep(wait)
        except Exception as e:
            print('error==:'+str(e))
            logging.error(e)
            self.updateWebView.emit(f"py_set_platform_status({json.dumps(single_platform['id'])});")
            self.updateWebView.emit(f"py_add_msg({json.dumps(single_platform['platform_name']+'-'+single_platform['alias_name']+'平台报错停止:'+str(e))});")

    # 抖店
    def dd_task(self,single_platform,stop_event):
        from doudian.DouDian import DouDian
        try:
            config_chose_type = single_platform['connect_type_id']
            config_token = single_platform['token']
            config_bot_id = single_platform['bot_id']
            config_platform = f"{single_platform['platform_type']}-{single_platform['id']}"
            config_transfer_keyword = single_platform['transfrom_keywork']
            config_designated_person = single_platform['designated_person']
            config_refresh_interval = single_platform['refresh_interval']
            config_name = f"{single_platform['platform_name']}-{single_platform['alias_name']}"
            config_transfer_name = single_platform['transfrom_name']
            designated_person = split_string_by_commas(config_designated_person)
            transfer_keyword = split_string_by_commas(config_transfer_keyword)
            transfer_name = split_string_by_commas(config_transfer_name)
            config_checked_greetings = single_platform['checked_greetings']
            config_greetings = single_platform['greetings']
            config_checked_pwd_login = single_platform['checked_pwd_login']
            config_checked_feishu = single_platform['checked_feishu']
            config_feishu_url = single_platform['feishu_url']
            config_username = single_platform['username']
            config_pwd = single_platform['pwd']

            coze_util = None
            bailian_util = None
            fast_util = None
            llm_prefix = 'coze'
            if config_chose_type== 0:
                coze_util =CozeUtil(config_token,coze_api_base,config_bot_id)
            elif config_chose_type== 1:
                bailian_util = BalianUtil(config_token,config_bot_id)
                llm_prefix = 'bailian'
            elif config_chose_type== 2:
                fast_util = FastGPTClient(config_bot_id,config_token)
                llm_prefix = 'fastgpt'

            global manual_intervention
            # 持续监听消息，有消息则对接大模型进行回复
            dd = DouDian(storage_state_path=f"state_{config_platform}.json")
            dd.set_feishu_config(config_checked_feishu, config_feishu_url)
            dd.launchChat(config_checked_pwd_login, config_username, config_pwd)
            if not getattr(dd, 'login_state', False) or not hasattr(dd, 'page'):
                raise Exception("抖店页面未初始化，已停止任务")
            # 纪录时间 用于刷新
            last_refresh_time = time.time()
            product_cache = {}
            product_cache_ttl = 30 * 60
            product_intro_waiting = {}
            product_intro_wait_seconds = 2.0
            product_only_waiting = {}
            processed_transfer_signatures = set()
            product_only_wait_seconds = 30
            unreplied_since_by_session = {}
            unreplied_last_snapshot = {}
            product_markers = [
                '咨询商品:',
                '我要咨询商品名称:',
                '我浏览了商品:',
                '商品链接:',
                '商品标题:',
                '商品ID:',
                '价格:',
            ]
            def extract_product_id(text):
                if not text:
                    return ''
                m = re.search(r'商品ID\s*[:：]\s*([0-9]{6,})', text)
                if m:
                    return m.group(1)
                m = re.search(r'goods_id=([0-9]{6,})', text)
                if m:
                    return m.group(1)
                m = re.search(r'(?:\bid=|\bitem_id=|\bproduct_id=)([0-9]{6,})', text)
                if m:
                    return m.group(1)
                return ''

            def extract_product_title(text):
                if not text:
                    return ''
                for pattern in [
                    r'我要咨询商品名称[:：]\s*([^,\n|]+)',
                    r'商品标题[:：]\s*([^,\n|]+)',
                    r'咨询商品[:：]\s*([^,\n|]+)',
                    r'我浏览了商品[:：]\s*([^,\n|]+)',
                ]:
                    m = re.search(pattern, text)
                    if m:
                        title = m.group(1).strip()
                        title = re.sub(r'^用户正在查看商品[，,]?', '', title).strip()
                        title = re.sub(r'^来自电商小助手的推荐', '', title).strip()
                        title = re.sub(r'已售\s*\d+(?:\.\d+)?\s*(?:件|单|笔)?$', '', title).strip()
                        title = re.sub(r'\s*价格[:：].*$', '', title).strip()
                        title = re.sub(r'\s*用户问题[:：].*$', '', title).strip()
                        return title
                return ''

            id_question_patterns = [
                r'商品\s*id',
                r'商品编号',
                r'\bid\b',
            ]

            def update_product_context(cache_key, event, is_primary_source):
                prev = product_cache.get(cache_key) or {}
                version = int(prev.get('version', 0)) + 1
                product_cache[cache_key] = {
                    "ts": time.time(),
                    "text": event.get("text", ""),
                    "source": event.get("source", "text"),
                    "product_id": event.get("product_id", ""),
                    "version": version,
                    "locked_primary": bool(is_primary_source),
                }
                return product_cache[cache_key]

            def format_session_for_log(session_key):
                if not session_key:
                    return "-"
                return session_key if len(session_key) <= 64 else session_key[:64] + "..."

            def normalize_reply_text(raw_reply):
                reply = (raw_reply or '').replace('#转交#', '').strip()
                if any(m in reply for m in product_markers):
                    for prompt in [
                        '请您提供要咨询的商品链接哦。',
                        '请您提供要咨询的商品链接哦',
                        '请提供要咨询的商品链接哦。',
                        '请提供要咨询的商品链接哦',
                        '请您提供要咨询的商品链接。',
                        '请您提供要咨询的商品链接',
                        '请提供要咨询的商品链接。',
                        '请提供要咨询的商品链接',
                    ]:
                        reply = reply.replace(prompt, '').strip()
                reply = re.sub(r'已售\\s*\\d+(?:\\.\\d+)?\\s*(?:件|单|笔)?', '', reply)
                reply = re.sub(r'\\s{2,}', ' ', reply).strip()
                if not reply:
                    reply = '好的，已收到您的消息。'
                return reply + '  ' + random.choice(random_reply_word) + random.choice(random_reply_character)

            def is_stable_session_key(session_key):
                if not session_key or not isinstance(session_key, str):
                    return False
                if not session_key.startswith('conv::biz:'):
                    return False
                return bool(session_key[len('conv::biz:'):].strip())

            def send_reply_to_target(target_session_key, chat_name, reply_text):
                if not is_stable_session_key(target_session_key):
                    self.updateWebView.emit(
                        f"py_add_msg({json.dumps(config_name+'|会话ID缺失，未发送（避免串会话）:'+str(chat_name))});"
                    )
                    return False
                sent_ok = dd.sendMsgToSession(target_session_key, reply_text, switch_back=True)
                if not sent_ok:
                    self.updateWebView.emit(
                        f"py_add_msg({json.dumps(config_name+'|会话定位失败，未发送（避免串会话）:'+str(chat_name)+'@'+str(target_session_key))});"
                    )
                    return False
                return True

            def get_current_product_context(cache_key):
                cached = product_cache.get(cache_key)
                if not cached:
                    return None
                if time.time() - cached["ts"] > product_cache_ttl:
                    return None
                return cached

            def is_meaningful_product_event(event):
                if not event:
                    return False
                title = extract_product_title(event.get("text", ""))
                product_id = event.get("product_id", "")
                if title and title not in ("用户正在查看商品",):
                    return True
                return bool(product_id)

            def build_llm_user_key(cache_key):
                current_ctx = get_current_product_context(cache_key) or {}
                suffix = current_ctx.get("product_id") or (
                    f"v{current_ctx.get('version', 0)}" if current_ctx.get("version") else "session"
                )
                suffix = re.sub(r'[^0-9A-Za-z:_-]+', '_', str(suffix or "session"))[:64]
                return f"{config_platform}_{llm_prefix}_{cache_key}_{suffix}"[:180]

            llm_request_queue = queue.Queue()
            llm_result_queue = queue.Queue()
            llm_ready_sessions = deque()
            llm_ready_session_set = set()
            llm_inflight_sessions = set()
            llm_pending_by_session = {}
            llm_session_wait_since = {}
            llm_starvation_threshold_seconds = 8.0
            llm_session_coalesce_seconds = 1.5
            llm_grace_reply_remaining = 0
            fetch_inflight_sessions = set()
            fetch_cooldown_until = {}

            def get_session_waiting_count(session):
                pending_count = len(llm_pending_by_session.get(session, []))
                if session in llm_inflight_sessions:
                    pending_count += 1
                return pending_count

            def get_session_wait_anchor(session, fallback_ts=None):
                if session in unreplied_since_by_session:
                    return unreplied_since_by_session[session]
                if fallback_ts is not None:
                    return fallback_ts
                return time.time()

            def build_task_receive_msg(task):
                questions = [str(q or '').strip() for q in (task.get('user_questions') or []) if str(q or '').strip()]
                context_text = str(task.get('context_text') or '').strip()
                if context_text:
                    if not questions:
                        return context_text
                    if len(questions) == 1:
                        return f"{context_text}\n用户问题:{questions[0]}"
                    body = "\n".join(f"{idx + 1}. {question}" for idx, question in enumerate(questions))
                    return (
                        f"{context_text}\n"
                        "用户连续提问如下，请按顺序逐条回答，只回答用户明确提到的问题，"
                        "不要补充未被询问的信息，不要延伸介绍其他卖点：\n"
                        f"{body}"
                    )
                if not questions:
                    return str(task.get('receive_msg') or '').strip()
                if len(questions) == 1:
                    return questions[0]
                body = "\n".join(f"{idx + 1}. {question}" for idx, question in enumerate(questions))
                return (
                    "用户连续提问如下，请按顺序逐条回答，只回答用户明确提到的问题，"
                    "不要补充未被询问的信息：\n"
                    f"{body}"
                )

            def can_merge_session_task(existing_task, new_task):
                if not existing_task or not new_task:
                    return False
                if existing_task.get('fetch_only') or new_task.get('fetch_only'):
                    return False
                if existing_task.get('direct_reply') or new_task.get('direct_reply'):
                    return False
                if existing_task.get('priority') == 'urgent' or new_task.get('priority') == 'urgent':
                    return False
                if existing_task.get('target_session_key') != new_task.get('target_session_key'):
                    return False
                if existing_task.get('llm_user_key') != new_task.get('llm_user_key'):
                    return False
                if str(existing_task.get('context_text') or '') != str(new_task.get('context_text') or ''):
                    return False
                return True

            def merge_session_task(existing_task, new_task):
                merged_questions = [str(q or '').strip() for q in (existing_task.get('user_questions') or []) if str(q or '').strip()]
                merged_questions.extend(
                    [str(q or '').strip() for q in (new_task.get('user_questions') or []) if str(q or '').strip()]
                )
                existing_task['user_questions'] = merged_questions
                existing_task['receive_msg'] = build_task_receive_msg(existing_task)
                existing_task['chat_name'] = new_task.get('chat_name') or existing_task.get('chat_name', '')
                existing_task['queued_at'] = min(
                    float(existing_task.get('queued_at') or time.time()),
                    float(new_task.get('queued_at') or time.time())
                )
                existing_task['wait_since'] = min(
                    float(existing_task.get('wait_since') or existing_task.get('queued_at') or time.time()),
                    float(new_task.get('wait_since') or new_task.get('queued_at') or time.time())
                )
                latest_question_ts = float(new_task.get('last_question_ts') or new_task.get('queued_at') or time.time())
                existing_task['last_question_ts'] = max(
                    float(existing_task.get('last_question_ts') or existing_task.get('queued_at') or time.time()),
                    latest_question_ts
                )
                existing_task['coalesce_until'] = existing_task['last_question_ts'] + llm_session_coalesce_seconds
                return existing_task

            def sync_runtime_unreplied_sessions():
                now_ts = time.time()
                try:
                    snapshot = dd.get_runtime_unreplied_sessions()
                except Exception:
                    snapshot = []
                active_sessions = set()
                latest_snapshot = {}
                for item in snapshot:
                    session_key = item.get('session_key', '')
                    if not is_stable_session_key(session_key):
                        continue
                    active_sessions.add(session_key)
                    latest_snapshot[session_key] = item
                    if session_key not in unreplied_since_by_session:
                        unreplied_since_by_session[session_key] = now_ts
                        wait_hint = ''
                        if item.get('countdown_time'):
                            wait_hint = f" countdown={item.get('countdown_time')}"
                        self.updateWebView.emit(
                            f"py_add_msg({json.dumps(config_name+'|检测到未回复会话 session='+format_session_for_log(session_key)+' unread='+str(item.get('unread_count', 0))+wait_hint)});"
                        )
                    has_prefetched = session_key in getattr(dd, 'prefetched_session_batch_keys', set())
                    if (
                        session_key not in llm_pending_by_session
                        and session_key not in llm_inflight_sessions
                        and session_key not in fetch_inflight_sessions
                        and not has_prefetched
                        and now_ts >= float(fetch_cooldown_until.get(session_key, 0) or 0)
                    ):
                        queue_session_task({
                            'session_key': session_key,
                            'target_session_key': session_key,
                            'chat_name': '',
                            'fetch_only': True,
                            'priority': 'urgent_fetch',
                            'queued_at': now_ts,
                            'wait_since': get_session_wait_anchor(session_key, now_ts),
                        })
                latest_snapshot_keys = set(unreplied_last_snapshot.keys())
                for session_key in latest_snapshot_keys - active_sessions:
                    if session_key in llm_pending_by_session or session_key in llm_inflight_sessions:
                        continue
                    unreplied_since_by_session.pop(session_key, None)
                unreplied_last_snapshot.clear()
                unreplied_last_snapshot.update(latest_snapshot)

            def drain_same_session_messages(target_session_key, max_wait_seconds=2.2, idle_rounds=2):
                if not is_stable_session_key(target_session_key):
                    return []
                drained = []
                seen_keys = set()
                deadline = time.time() + max_wait_seconds
                idle_hits = 0
                while time.time() < deadline and idle_hits < idle_rounds:
                    time.sleep(min(wait, 0.35))
                    try:
                        current_session = dd.get_current_session_key()
                    except Exception:
                        current_session = ''
                    if current_session != target_session_key:
                        try:
                            if not dd._switch_to_session(target_session_key):
                                idle_hits += 1
                                continue
                        except Exception:
                            idle_hits += 1
                            continue
                    try:
                        extra_msgs = dd.readCurrentUnread(
                            config_checked_greetings,
                            config_greetings,
                        )
                    except Exception:
                        extra_msgs = []
                    if not extra_msgs:
                        idle_hits += 1
                        continue
                    appended = 0
                    for extra in extra_msgs:
                        key = f"{extra.get('index', '')}::{extra.get('type', '')}::{(extra.get('content') or '').strip()}"
                        if key in seen_keys:
                            continue
                        seen_keys.add(key)
                        drained.append(extra)
                        appended += 1
                    if appended:
                        idle_hits = 0
                    else:
                        idle_hits += 1
                return drained

            def final_drain_task_questions(task, max_wait_seconds=1.0, idle_rounds=1):
                if not task or task.get('fetch_only') or task.get('direct_reply'):
                    return task
                if task.get('priority') == 'urgent':
                    return task
                target_session_key = task.get('target_session_key', '')
                if not is_stable_session_key(target_session_key):
                    return task
                extra_msgs = drain_same_session_messages(
                    target_session_key,
                    max_wait_seconds=max_wait_seconds,
                    idle_rounds=idle_rounds,
                )
                if not extra_msgs:
                    return task
                existing_questions = [
                    str(q or '').strip()
                    for q in (task.get('user_questions') or [])
                    if str(q or '').strip()
                ]
                existing_set = set(existing_questions)
                appended_questions = []
                latest_question_ts = float(task.get('last_question_ts') or task.get('queued_at') or time.time())
                for extra in extra_msgs:
                    if extra.get('type') != 'text':
                        continue
                    question = str(extra.get('content') or '').strip()
                    if not question or question in existing_set:
                        continue
                    existing_set.add(question)
                    appended_questions.append(question)
                    latest_question_ts = max(
                        latest_question_ts,
                        float(time.time())
                    )
                    if extra.get('who'):
                        task['chat_name'] = extra.get('who')
                if not appended_questions:
                    return task
                existing_questions.extend(appended_questions)
                task['user_questions'] = existing_questions
                task['last_question_ts'] = latest_question_ts
                task['coalesce_until'] = latest_question_ts + llm_session_coalesce_seconds
                self.updateWebView.emit(
                    f"py_add_msg({json.dumps(config_name+'|发模型前最终收口，补充问题数:'+str(len(appended_questions)))});"
                )
                return task

            def fetch_unreplied_session_batch(target_session_key, max_wait_seconds=1.2, idle_rounds=1):
                if not is_stable_session_key(target_session_key):
                    return []
                previous_session = ''
                try:
                    previous_session = dd.get_current_session_key()
                except Exception:
                    previous_session = ''
                switched = previous_session == target_session_key
                if not switched:
                    try:
                        switched = dd._switch_to_session(target_session_key)
                    except Exception:
                        switched = False
                if not switched:
                    return []
                try:
                    current_session = dd.get_current_session_key()
                    if current_session != target_session_key:
                        return []
                    if previous_session == target_session_key:
                        msgs = dd.readCurrentUnread(config_checked_greetings, config_greetings)
                    else:
                        msgs = dd._getAfterSwitchMsg(config_checked_greetings, config_greetings)
                    if msgs:
                        extra_msgs = drain_same_session_messages(
                            target_session_key,
                            max_wait_seconds=max_wait_seconds,
                            idle_rounds=idle_rounds,
                        )
                        if extra_msgs:
                            msgs.extend(extra_msgs)
                    return msgs
                finally:
                    if previous_session and previous_session != target_session_key:
                        try:
                            dd._switch_to_session(previous_session)
                        except Exception:
                            pass

            def should_delay_for_coalesce(session, first_task, urgent_session='', starved_session=''):
                if not first_task:
                    return False
                if first_task.get('direct_reply'):
                    return False
                if first_task.get('priority') == 'urgent':
                    return False
                if urgent_session == session or starved_session == session:
                    return False
                coalesce_until = float(first_task.get('coalesce_until') or 0)
                if not coalesce_until:
                    return False
                anchor = float(llm_session_wait_since.get(session) or first_task.get('wait_since') or first_task.get('queued_at') or time.time())
                now_ts = time.time()
                if now_ts - anchor >= llm_starvation_threshold_seconds:
                    return False
                return now_ts < coalesce_until

            def get_oldest_starved_session(exclude_session=''):
                now_ts = time.time()
                starved_session = ''
                starved_since = None
                for session, pending_tasks in llm_pending_by_session.items():
                    if not pending_tasks:
                        continue
                    if session == exclude_session:
                        continue
                    waiting_since = llm_session_wait_since.get(session)
                    if waiting_since is None:
                        continue
                    if now_ts - waiting_since < llm_starvation_threshold_seconds:
                        continue
                    if starved_since is None or waiting_since < starved_since:
                        starved_session = session
                        starved_since = waiting_since
                return starved_session

            def get_oldest_waiting_session(exclude_session=''):
                waiting_session = ''
                waiting_since = None
                for session, pending_tasks in llm_pending_by_session.items():
                    if not pending_tasks:
                        continue
                    if session == exclude_session:
                        continue
                    anchor = llm_session_wait_since.get(session)
                    if anchor is None:
                        first_task = pending_tasks[0] if pending_tasks else {}
                        anchor = float(first_task.get('wait_since') or first_task.get('queued_at') or time.time())
                    if waiting_since is None or anchor < waiting_since:
                        waiting_session = session
                        waiting_since = anchor
                return waiting_session

            def get_oldest_urgent_session(exclude_session=''):
                urgent_session = ''
                urgent_since = None
                for session, pending_tasks in llm_pending_by_session.items():
                    if not pending_tasks:
                        continue
                    if session == exclude_session:
                        continue
                    urgent_task = None
                    for pending_task in pending_tasks:
                        if pending_task.get('priority') in ('urgent', 'urgent_fetch'):
                            urgent_task = pending_task
                            break
                    if not urgent_task:
                        continue
                    queued_at = float(urgent_task.get('queued_at') or time.time())
                    if urgent_since is None or queued_at < urgent_since:
                        urgent_session = session
                        urgent_since = queued_at
                return urgent_session

            def pop_ready_session():
                while llm_ready_sessions:
                    session = llm_ready_sessions.popleft()
                    llm_ready_session_set.discard(session)
                    if llm_pending_by_session.get(session):
                        return session
                    llm_pending_by_session.pop(session, None)
                return ''

            def remove_ready_session(session):
                if not session or session not in llm_ready_session_set:
                    return
                llm_ready_session_set.discard(session)
                try:
                    llm_ready_sessions.remove(session)
                except ValueError:
                    pass

            def mark_session_ready(session):
                if not session:
                    return
                if session in llm_inflight_sessions or session in llm_ready_session_set:
                    return
                if not llm_pending_by_session.get(session):
                    return
                llm_session_wait_since.setdefault(session, time.time())
                llm_ready_sessions.append(session)
                llm_ready_session_set.add(session)

            def dispatch_task(session, task):
                nonlocal llm_grace_reply_remaining
                if task.get('fetch_only'):
                    fetch_inflight_sessions.add(session)
                    try:
                        fetched_msgs = fetch_unreplied_session_batch(session, max_wait_seconds=1.2, idle_rounds=1)
                        if fetched_msgs:
                            dd._enqueue_prefetched_session_batch(session, fetched_msgs)
                            fetch_cooldown_until[session] = time.time() + 1.0
                            self.updateWebView.emit(
                                f"py_add_msg({json.dumps(config_name+'|未回复会话已取题 session='+format_session_for_log(session)+' 条数:'+str(len(fetched_msgs)))});"
                            )
                        else:
                            fetch_cooldown_until[session] = time.time() + 1.5
                    finally:
                        fetch_inflight_sessions.discard(session)
                    return False
                if 'direct_reply' in task:
                    direct_reply = task.get('direct_reply', '')
                    direct_chat = task.get('chat_name', '')
                    direct_session_key = task.get('target_session_key', '')
                    if direct_reply:
                        sent_ok = send_reply_to_target(direct_session_key, direct_chat, direct_reply)
                        if sent_ok and is_stable_session_key(direct_session_key):
                            unreplied_since_by_session.pop(direct_session_key, None)
                            unreplied_last_snapshot.pop(direct_session_key, None)
                        self.updateWebView.emit(f"py_add_msg({json.dumps(config_name+'|回复消息::'+direct_reply)});")
                    if llm_pending_by_session.get(session):
                        mark_session_ready(session)
                    return False

                task = final_drain_task_questions(task)
                task['receive_msg'] = build_task_receive_msg(task)
                llm_inflight_sessions.add(session)
                llm_session_wait_since.pop(session, None)
                llm_request_queue.put(task)
                self.updateWebView.emit(f"py_add_msg({json.dumps(config_name+'|正在请求模型回复...')});")
                return True

            def schedule_next_session_task(preferred_session=''):
                nonlocal llm_grace_reply_remaining
                if llm_inflight_sessions:
                    return
                while True:
                    urgent_session = get_oldest_urgent_session(exclude_session='')
                    starved_session = get_oldest_starved_session(exclude_session=preferred_session)
                    chosen_session = ''

                    if urgent_session and urgent_session != preferred_session:
                        chosen_session = urgent_session
                        llm_grace_reply_remaining = 0
                    elif preferred_session and llm_pending_by_session.get(preferred_session):
                        if starved_session:
                            if llm_grace_reply_remaining > 0:
                                chosen_session = preferred_session
                                llm_grace_reply_remaining -= 1
                            else:
                                chosen_session = starved_session
                                llm_grace_reply_remaining = 0
                        else:
                            chosen_session = preferred_session
                            llm_grace_reply_remaining = 0
                    else:
                        llm_grace_reply_remaining = 0
                        chosen_session = starved_session or pop_ready_session()

                    if not chosen_session:
                        return

                    remove_ready_session(chosen_session)
                    pending_tasks = llm_pending_by_session.get(chosen_session) or []
                    if not pending_tasks:
                        llm_pending_by_session.pop(chosen_session, None)
                        llm_session_wait_since.pop(chosen_session, None)
                        if chosen_session == preferred_session:
                            preferred_session = ''
                        continue

                    first_pending_task = pending_tasks[0]
                    if len(pending_tasks) == 1 and should_delay_for_coalesce(
                        chosen_session,
                        first_pending_task,
                        urgent_session=urgent_session,
                        starved_session=starved_session,
                    ):
                        mark_session_ready(chosen_session)
                        return

                    urgent_task_index = next(
                        (idx for idx, pending_task in enumerate(pending_tasks) if pending_task.get('priority') == 'urgent'),
                        None
                    )
                    if urgent_task_index is None:
                        task = pending_tasks.pop(0)
                    else:
                        task = pending_tasks.pop(urgent_task_index)
                    if pending_tasks:
                        llm_pending_by_session[chosen_session] = pending_tasks
                    else:
                        llm_pending_by_session.pop(chosen_session, None)
                        llm_session_wait_since.pop(chosen_session, None)

                    if dispatch_task(chosen_session, task):
                        return

                    if chosen_session == preferred_session and llm_pending_by_session.get(chosen_session):
                        continue

            def queue_session_task(task):
                session = task.get('session_key', '')
                if not session:
                    return
                task.setdefault('queued_at', time.time())
                task.setdefault('wait_since', get_session_wait_anchor(session, task.get('queued_at')))
                task.setdefault('last_question_ts', float(task.get('queued_at') or time.time()))
                task.setdefault('coalesce_until', float(task.get('last_question_ts') or time.time()) + llm_session_coalesce_seconds)
                pending_tasks = llm_pending_by_session.setdefault(session, [])
                if pending_tasks and can_merge_session_task(pending_tasks[-1], task):
                    merge_session_task(pending_tasks[-1], task)
                    self.updateWebView.emit(
                        f"py_add_msg({json.dumps(config_name+'|同会话连续问题已合并，当前合并条数:'+str(len(pending_tasks[-1].get('user_questions') or [])))});"
                    )
                    mark_session_ready(session)
                    schedule_next_session_task()
                    return
                was_empty = len(pending_tasks) == 0
                pending_tasks.append(task)
                if was_empty and session not in llm_inflight_sessions:
                    llm_session_wait_since[session] = float(task.get('wait_since') or get_session_wait_anchor(session, task.get('queued_at')) or time.time())
                was_waiting = (
                    session in llm_inflight_sessions
                    or session in llm_ready_session_set
                    or len(pending_tasks) > 1
                )
                mark_session_ready(session)
                if was_waiting:
                    self.updateWebView.emit(
                        f"py_add_msg({json.dumps(config_name+'|当前会话正在处理中，已排队问题数:'+str(get_session_waiting_count(session)))});"
                    )
                schedule_next_session_task()

            def llm_worker():
                while not stop_event.is_set():
                    try:
                        task = llm_request_queue.get(timeout=0.5)
                    except queue.Empty:
                        continue
                    if task is None:
                        llm_request_queue.task_done()
                        break
                    session = task.get('session_key', '')
                    try:
                        holder = {}

                        def _worker_handler(reply, js_reply):
                            holder['reply'] = reply
                            holder['js_reply'] = js_reply

                        if config_chose_type == 0:
                            coze_util.send_message_and_poll(task['llm_user_key'], task['receive_msg'], _worker_handler)
                        elif config_chose_type == 1:
                            bailian_util.send_message_and_poll(task['llm_user_key'], task['receive_msg'], _worker_handler)
                        elif config_chose_type == 2:
                            fast_util.send_chat_completion(task['llm_user_key'], task['receive_msg'], _worker_handler)
                        else:
                            raise Exception("未配置有效模型类型")

                        if not holder.get('js_reply'):
                            holder['js_reply'] = '回复消息::(空回复)'
                        llm_result_queue.put({
                            'session_key': session,
                            'chat_name': task.get('chat_name', ''),
                            'target_session_key': task.get('target_session_key', ''),
                            'reply': holder.get('reply', ''),
                            'js_reply': holder.get('js_reply', ''),
                            'error': '',
                        })
                    except Exception as e:
                        llm_result_queue.put({
                            'session_key': session,
                            'chat_name': task.get('chat_name', ''),
                            'target_session_key': task.get('target_session_key', ''),
                            'reply': '',
                            'js_reply': '',
                            'error': str(e),
                        })
                    finally:
                        llm_request_queue.task_done()

            llm_worker_thread = threading.Thread(target=llm_worker, daemon=True)
            llm_worker_thread.start()

            while not stop_event.is_set():  # 如果设置了停止事件，则退出循环
                while True:
                    try:
                        result = llm_result_queue.get_nowait()
                    except queue.Empty:
                        break
                    done_session = result.get('session_key', '')
                    if done_session:
                        llm_inflight_sessions.discard(done_session)
                    err_text = result.get('error', '')
                    if err_text:
                        self.updateWebView.emit(f"py_add_msg({json.dumps(config_name+'|'+err_text[:50])});")
                    else:
                        try:
                            final_reply = normalize_reply_text(result.get('reply', ''))
                            target_chat = result.get('chat_name', '')
                            target_session_key = result.get('target_session_key', '')
                            send_reply_to_target(target_session_key, target_chat, final_reply)
                            if is_stable_session_key(target_session_key):
                                unreplied_since_by_session.pop(target_session_key, None)
                                unreplied_last_snapshot.pop(target_session_key, None)
                        except Exception as e:
                            err_text = str(e)
                            logging.error(err_text)
                            if "图片路径不对或者没找到上传按钮" not in err_text:
                                self.updateWebView.emit(f"py_add_msg({json.dumps(config_name+'|报错:'+err_text[:50])});")
                        js_reply = result.get('js_reply', '')
                        if js_reply:
                            self.updateWebView.emit(f"py_add_msg({json.dumps(config_name+'|'+js_reply)});")
                    if done_session:
                        older_waiting_session = get_oldest_waiting_session(exclude_session=done_session)
                        if older_waiting_session:
                            llm_grace_reply_remaining = 0
                        elif get_oldest_starved_session(exclude_session=done_session):
                            llm_grace_reply_remaining = max(llm_grace_reply_remaining, 1)
                        if llm_pending_by_session.get(done_session):
                            mark_session_ready(done_session)
                        schedule_next_session_task(preferred_session=done_session)

                msgs = []
                current_time = time.time()
                if current_time - last_refresh_time > config_refresh_interval:
                    print("Refreshing the page...")
                    dd.pageReload()  # 刷新页面
                    last_refresh_time = current_time  # 更新最后刷新时间
                sync_runtime_unreplied_sessions()
                schedule_next_session_task()
                try:
                    # 持续监听消息，有消息则对接大模型进行回复 转人工依然获取 防止转机器后获取已经回复的
                    msgs = dd.getNextNewMessage(checkRedMessage=not manual_intervention,
                                                config_checked_greetings=config_checked_greetings,
                                                config_greetings=config_greetings)
                except Exception as e:
                    self.updateWebView.emit(f"py_add_msg({json.dumps(str(e)[:50])});")

                # 人工 跳出
                if manual_intervention:
                    print('=====人工========')
                    time.sleep(wait)
                    continue
                print('=====AI========')
                if msgs:
                    session_key = ''
                    try:
                        session_key = dd.get_current_session_key()
                    except Exception:
                        session_key = ''
                    try:
                        cache_key = dd.get_chat_cache_key()
                    except Exception:
                        cache_key = ''
                    cache_key = cache_key or session_key or f"{config_platform}_default"
                    target_session_key = ''
                    if is_stable_session_key(session_key):
                        target_session_key = session_key
                    if not target_session_key:
                        self.updateWebView.emit(f"py_add_msg({json.dumps(config_name+'|会话ID缺失，跳过本轮（避免串会话）')});")
                        time.sleep(wait)
                        continue
                    extra_same_session_msgs = drain_same_session_messages(target_session_key)
                    if extra_same_session_msgs:
                        msgs.extend(extra_same_session_msgs)
                    batch_chat_name = ''
                    saw_user_text = False
                    pending_auto_intro = None

                    for message in msgs:
                        msg_type = message.get('type', '')
                        msg_content = (message.get('content') or '').strip()
                        if not msg_content:
                            continue
                        chat_name = message.get('who', '') or batch_chat_name
                        if chat_name:
                            batch_chat_name = chat_name

                        if msg_type in ('card', 'from_info') and any(m in msg_content for m in product_markers):
                            if '没有咨询过宝贝' not in msg_content and '暂无咨询' not in msg_content and '暂无商品' not in msg_content:
                                source = message.get('source', '')
                                if msg_type == 'card':
                                    normalized_source = 'card'
                                elif source in ('link', 'system', 'panel'):
                                    normalized_source = source
                                else:
                                    normalized_source = 'text'
                                event = {
                                    "text": msg_content,
                                    "source": normalized_source,
                                    "product_id": extract_product_id(msg_content),
                                }
                                if is_meaningful_product_event(event):
                                    is_primary_source = normalized_source in ('card', 'link', 'system', 'text')
                                    current_ctx = product_cache.get(cache_key)
                                    if is_primary_source or not (current_ctx and current_ctx.get("locked_primary")):
                                        context_info = update_product_context(cache_key, event, is_primary_source=is_primary_source)
                                        self.updateWebView.emit(
                                            f"py_add_msg({json.dumps(config_name + '|商品上下文更新 session=' + format_session_for_log(cache_key) + ' source=' + context_info.get('source', '-') + ' id=' + (context_info.get('product_id', '-') or '-') + ' v=' + str(context_info.get('version', 1)))});"
                                        )
                                        if msg_type in ('card', 'from_info'):
                                            pending_auto_intro = {
                                                'chat_name': chat_name,
                                                'target_session_key': target_session_key,
                                            }

                    for message in msgs:
                        msg_type = message.get('type', '')
                        msg_content = (message.get('content') or '').strip()
                        if not msg_content:
                            continue
                        chat_name = message.get('who', '') or batch_chat_name
                        if chat_name:
                            batch_chat_name = chat_name

                        if msg_type != 'text':
                            continue

                        saw_user_text = True
                        pending_auto_intro = None
                        product_intro_waiting.pop(cache_key, None)
                        product_only_waiting.pop(cache_key, None)
                        latest_user_text = msg_content
                        curr_sig = f"{message.get('index', '')}::{latest_user_text}"
                        raw_receive_msg = re.sub(r'已售\\s*\\d+(?:\\.\\d+)?\\s*(?:件|单|笔)?', '', latest_user_text)
                        raw_receive_msg = re.sub(r'\\s{2,}', ' ', raw_receive_msg).strip()
                        current_ctx = get_current_product_context(cache_key)
                        receive_msg = raw_receive_msg or latest_user_text
                        if current_ctx and not any(m in receive_msg for m in product_markers):
                            receive_msg = f"{current_ctx['text']}\n用户问题:{latest_user_text}"
                            self.updateWebView.emit(
                                f"py_add_msg({json.dumps(config_name + '|复用商品上下文 session=' + format_session_for_log(cache_key) + ' source=' + current_ctx.get('source', '-') + ' id=' + (current_ctx.get('product_id', '-') or '-') + ' v=' + str(current_ctx.get('version', 1)))});"
                            )

                        if receive_msg and designated_person and chat_name not in designated_person:
                            self.updateWebView.emit(f"py_add_msg({json.dumps('不在指定回复人中,默认不回复')});")
                            time.sleep(wait)
                            continue

                        self.updateWebView.emit(f"py_add_msg({json.dumps('===============')});")
                        js_receive_msg = f"{config_name}|收到消息::{receive_msg}"
                        self.updateWebView.emit(f"py_add_msg({json.dumps(js_receive_msg)});")

                        if latest_user_text and transfer_name and transfer_keyword and any(s in latest_user_text for s in transfer_keyword):
                            transfer_sig = f"{cache_key}::{curr_sig or latest_user_text}"
                            if transfer_sig in processed_transfer_signatures:
                                self.updateWebView.emit(f"py_add_msg({json.dumps(config_name+'|重复转交触发，已忽略')});")
                                time.sleep(wait)
                                continue
                            processed_transfer_signatures.add(transfer_sig)

                            def single_transfer(name):
                                if str(name).startswith('未找到'):
                                    return
                                self.updateWebView.emit(f"py_add_msg({json.dumps(config_name+'|正在转接给:'+name)});")

                            dd.transferOther(transfer_name, single_transfer)
                            time.sleep(wait)
                            continue

                        if latest_user_text and any(re.search(p, latest_user_text, flags=re.IGNORECASE) for p in id_question_patterns):
                            local_ctx = receive_msg
                            current_ctx = get_current_product_context(cache_key)
                            if current_ctx:
                                local_ctx = f"{current_ctx.get('text', '')}\n{receive_msg}"
                            title = extract_product_title(local_ctx)
                            if title:
                                direct_reply = f"商品ID（商品标题）是“{title}”。"
                            else:
                                matched_id = extract_product_id(local_ctx)
                                if matched_id:
                                    direct_reply = f"商品ID是{matched_id}。"
                                else:
                                    direct_reply = "当前消息里未识别到商品标题，请再发一次商品卡片。"
                            direct_reply = direct_reply + '  ' + random.choice(random_reply_word) + random.choice(random_reply_character)
                            direct_task = {
                                'session_key': cache_key,
                                'chat_name': chat_name,
                                'target_session_key': target_session_key,
                                'direct_reply': direct_reply,
                                'wait_since': get_session_wait_anchor(cache_key),
                            }
                            queue_session_task(direct_task)
                            time.sleep(wait)
                            continue

                        task = {
                            'session_key': cache_key,
                            'chat_name': chat_name,
                            'target_session_key': target_session_key,
                            'receive_msg': receive_msg,
                            'context_text': current_ctx['text'] if current_ctx and not any(m in receive_msg for m in product_markers) else '',
                            'user_questions': [latest_user_text if current_ctx and not any(m in receive_msg for m in product_markers) else receive_msg],
                            'llm_user_key': build_llm_user_key(cache_key),
                            'wait_since': get_session_wait_anchor(cache_key),
                        }
                        queue_session_task(task)

                    if not saw_user_text and pending_auto_intro:
                        current_ctx = get_current_product_context(cache_key)
                        if current_ctx:
                            product_intro_waiting[cache_key] = {
                                'ts': time.time(),
                                'chat_name': pending_auto_intro.get('chat_name', batch_chat_name),
                                'target_session_key': pending_auto_intro.get('target_session_key', target_session_key),
                                'product_version': current_ctx.get('version', 0),
                            }
                            self.updateWebView.emit(
                                f"py_add_msg({json.dumps(config_name+'|仅收到商品信息，自动介绍降级等待'+str(int(product_intro_wait_seconds))+'s')});"
                            )

                if stop_event.is_set():
                    break
                now_ts = time.time()
                expired_intro = []
                for key, meta in list(product_intro_waiting.items()):
                    if now_ts - meta['ts'] < product_intro_wait_seconds:
                        continue
                    current_ctx = get_current_product_context(key)
                    if not current_ctx:
                        expired_intro.append(key)
                        continue
                    if meta.get('product_version') and current_ctx.get('version') != meta.get('product_version'):
                        expired_intro.append(key)
                        continue
                    chat_name = meta.get('chat_name', '')
                    if current_ctx.get('text') and designated_person and chat_name not in designated_person:
                        self.updateWebView.emit(f"py_add_msg({json.dumps('不在指定回复人中,默认不回复')});")
                        expired_intro.append(key)
                        continue
                    auto_intro = '请基于以上商品信息，先回复一句简短商品介绍，并邀请用户提问。'
                    receive_msg = f"{current_ctx.get('text', '')}\n用户问题:{auto_intro}"
                    self.updateWebView.emit(f"py_add_msg({json.dumps(config_name+'|仅收到商品信息，已自动按商品信息回复')});")
                    self.updateWebView.emit(f"py_add_msg({json.dumps('===============')});")
                    js_receive_msg = f"{config_name}|收到消息::{receive_msg}"
                    self.updateWebView.emit(f"py_add_msg({json.dumps(js_receive_msg)});")
                    task = {
                        'session_key': key,
                        'chat_name': chat_name,
                        'target_session_key': meta.get('target_session_key', ''),
                        'receive_msg': receive_msg,
                        'llm_user_key': build_llm_user_key(key),
                        'priority': 'urgent',
                        'queued_at': meta.get('ts', now_ts),
                        'wait_since': min(meta.get('ts', now_ts), get_session_wait_anchor(key, meta.get('ts', now_ts))),
                    }
                    queue_session_task(task)
                    expired_intro.append(key)
                for key in expired_intro:
                    product_intro_waiting.pop(key, None)

                expired_waiting = []
                for key, meta in list(product_only_waiting.items()):
                    if now_ts - meta['ts'] < product_only_wait_seconds:
                        continue
                    chat_target = meta.get('chat_name', '')
                    if not (config_checked_greetings == 1 and config_greetings):
                        expired_waiting.append(key)
                        continue
                    if not chat_target:
                        self.updateWebView.emit(f"py_add_msg({json.dumps(config_name+'|30s无提问，但无法定位会话，跳过问候语')});")
                        expired_waiting.append(key)
                        continue
                    try:
                        target_session_key = meta.get('target_session_key', '')
                        sent_ok = False
                        if is_stable_session_key(target_session_key):
                            sent_ok = dd.sendMsgToSession(target_session_key, config_greetings, switch_back=True)
                        if sent_ok:
                            self.updateWebView.emit(f"py_add_msg({json.dumps(config_name+'|30s无提问，已发送问候语:'+chat_target)});")
                            expired_waiting.append(key)
                        else:
                            # 会话暂时未找到，30秒后重试
                            meta['ts'] = now_ts
                            self.updateWebView.emit(f"py_add_msg({json.dumps(config_name+'|30s无提问，未找到会话，稍后重试:'+chat_target)});")
                    except Exception as e:
                        meta['ts'] = now_ts
                        self.updateWebView.emit(f"py_add_msg({json.dumps(config_name+'|发送问候语失败:'+str(e)[:50])});")
                for key in expired_waiting:
                    product_only_waiting.pop(key, None)

                time.sleep(wait)
            try:
                llm_request_queue.put_nowait(None)
            except Exception:
                pass
            try:
                llm_worker_thread.join(timeout=1)
            except Exception:
                pass
            dd.stopLaunch()
        except Exception as e:
            print(e)
            logging.error(e)
            try:
                llm_request_queue.put_nowait(None)
            except Exception:
                pass
            try:
                llm_worker_thread.join(timeout=1)
            except Exception:
                pass
            dd.stopLaunch()
            self.updateWebView.emit(f"py_set_platform_status({json.dumps(single_platform['id'])});")
            self.updateWebView.emit(f"py_add_msg({json.dumps(single_platform['platform_name']+'-'+single_platform['alias_name']+'平台报错停止:'+str(e))});")
            if config_checked_feishu==1 and config_feishu_url:
                send_feishu_message(config_feishu_url,single_platform['platform_name']+'-'+single_platform['alias_name']+'平台报错停止')


    # 拼多多
    def pdd_task(self,single_platform,stop_event):
        from pinduoduo.pinduoduo import PinDuoDuo
        try:
            config_chose_type = single_platform['connect_type_id']
            config_token = single_platform['token']
            config_bot_id = single_platform['bot_id']
            config_platform = f"{single_platform['platform_type']}-{single_platform['id']}"
            config_transfer_keyword = single_platform['transfrom_keywork']
            config_designated_person = single_platform['designated_person']
            config_refresh_interval = single_platform['refresh_interval']
            config_name = f"{single_platform['platform_name']}-{single_platform['alias_name']}"
            config_transfer_name = single_platform['transfrom_name']
            designated_person = split_string_by_commas(config_designated_person)
            transfer_keyword = split_string_by_commas(config_transfer_keyword)
            transfer_name = split_string_by_commas(config_transfer_name)
            config_checked_greetings = single_platform['checked_greetings']
            config_greetings = single_platform['greetings']
            config_checked_pwd_login = single_platform['checked_pwd_login']
            config_username = single_platform['username']
            config_pwd = single_platform['pwd']
            config_checked_feishu = single_platform['checked_feishu']
            config_feishu_url = single_platform['feishu_url']

            coze_util = None
            bailian_util = None
            fast_util = None
            if config_chose_type== 0:
                coze_util =CozeUtil(config_token,coze_api_base,config_bot_id)
            elif config_chose_type== 1:
                bailian_util = BalianUtil(config_token,config_bot_id)
            elif config_chose_type== 2:
                fast_util = FastGPTClient(config_bot_id,config_token)

            global manual_intervention
            # 持续监听消息，有消息则对接大模型进行回复
            pdd = PinDuoDuo(storage_state_path=f"state_{config_platform}.json")
            pdd.launchChat(config_checked_pwd_login,config_username,config_pwd)
            # 纪录时间 用于刷新
            last_refresh_time = time.time()
            while not stop_event.is_set():  # 如果设置了停止事件，则退出循环
                msgs = []
                current_time = time.time()
                if current_time - last_refresh_time > config_refresh_interval:
                    print("Refreshing the page...")
                    pdd.pageReload()  # 刷新页面
                    last_refresh_time = current_time  # 更新最后刷新时间
                try:
                    # 持续监听消息，有消息则对接大模型进行回复 转人工依然获取 防止转机器后获取已经回复的
                    msgs = pdd.getNextNewMessage(checkRedMessage=not manual_intervention,
                                                 config_checked_greetings=config_checked_greetings,
                                                 config_greetings=config_greetings)
                except Exception as e:
                    self.updateWebView.emit(f"py_add_msg({json.dumps(str(e)[:80])});")
                    if str(e)[:80] == 'Page.query_selector: Target page, context or browser has been closed' or str(e)[:80] ==  'Event loop is closed! Is Playwright already stopped?' or 'Page.reload:' in  str(e)[:80]:
                        raise Exception("浏览器异常消失,请勿自己关闭浏览器")
                    elif str(e)[:80] ==  '掉线跳转到登录页':
                        raise Exception("掉线跳转到登录页")
                 # 人工 跳出
                if manual_intervention:
                    print('=====人工========')
                    time.sleep(wait)
                    continue
                # print('=====AI========')
                if msgs:
                    # 初始化一个空列表用于存储非空的文本内容
                    contents = []
                    chat_name = ''
                    # 遍历messages列表
                    for message in msgs:
                        if (message['type'] == 'text' or message['type'] == 'card' or message['type'] == 'from_info' or message['type'] == 'img') and message['content'].strip():  # 确保类型为text且内容不为空（去除首尾空白后）
                            chat_name = message['who']
                            contents.append(message['content'])
                            # 处理消息逻辑
                        else:
                            #未识别的消息
                            chat_name = message['who']
                            contents.append('你好')
                    # 使用逗号拼接所有非空的内容
                    receive_msg = ','.join(contents)
                    if  receive_msg and designated_person and chat_name not in designated_person:
                        self.updateWebView.emit(f"py_add_msg({json.dumps('不在指定回复人中,默认不回复')});")
                        time.sleep(wait)
                        continue
                    self.updateWebView.emit(f"py_add_msg({json.dumps('===============')});")
                    js_receive_msg = f"{config_name}|收到消息::{receive_msg}"
                    self.updateWebView.emit(f"py_add_msg({json.dumps(js_receive_msg)});")
                    # 查看是否触发转交
                    if receive_msg and transfer_name and transfer_keyword and any(s in receive_msg for s in transfer_keyword):
                        def single_transfer(name):
                            self.updateWebView.emit(f"py_add_msg({json.dumps(config_name+'|正在转接给:'+name)});")
                        pdd.transferOther(transfer_name,single_transfer)
                        time.sleep(wait)
                        continue
                    self.updateWebView.emit(f"py_add_msg({json.dumps(config_name+'|正在请求模型回复...')});")
                    #定义一个匿名函数（lambda）作为回调函数，包含两个逻辑
                    def message_handler(reply,js_reply):
                        if '#转交#' in reply and transfer_name:
                            def single_transfer(name):
                                self.updateWebView.emit(f"py_add_msg({json.dumps(config_name+'|模型判断转交给:'+name)});")
                            pdd.transferOther(transfer_name,single_transfer)
                        else:
                            try:
                                reply = reply+'  '+ random.choice(random_reply_word) + random.choice(random_reply_character)
                                pdd.sendMsg(reply)
                            except Exception as e:
                                self.updateWebView.emit(f"py_add_msg({json.dumps(config_name+'|报错:'+str(e)[:50])});")
                            self.updateWebView.emit(f"py_add_msg({json.dumps(config_name+'|'+js_reply)});")
                    try:
                        # 调用 send_message_and_poll 方法并传递回调函数
                        if config_chose_type== 0:
                            # 调用 send_message_and_poll 方法并传递回调函数
                            coze_util.send_message_and_poll(config_platform+'_'+chat_name, receive_msg, message_handler,)
                        elif config_chose_type== 1:
                            bailian_util.send_message_and_poll(config_platform+'_bl'+chat_name, receive_msg, message_handler)
                        elif config_chose_type== 2:
                            fast_util.send_chat_completion(config_platform+'_fast'+chat_name, receive_msg, message_handler)
                    except Exception as e:
                        self.updateWebView.emit(f"py_add_msg({json.dumps(str(e)[:50])});")

                time.sleep(wait)
            pdd.stopLaunch()
        except Exception as e:
            print(e)
            logging.error(e)
            pdd.stopLaunch()
            self.updateWebView.emit(f"py_set_platform_status({json.dumps(single_platform['id'])});")
            self.updateWebView.emit(f"py_add_msg({json.dumps(single_platform['platform_name']+'-'+single_platform['alias_name']+'平台报错停止:'+str(e))});")
            if config_checked_feishu==1 and config_feishu_url:
                send_feishu_message(config_feishu_url,single_platform['platform_name']+'-'+single_platform['alias_name']+'平台报错停止')

    # 微信小店
    def wxxd_task(self,single_platform,stop_event):
        from wxxd.wxxd import WeiXiaoDian
        try:
            config_chose_type = single_platform['connect_type_id']
            config_token = single_platform['token']
            config_bot_id = single_platform['bot_id']
            config_platform = f"{single_platform['platform_type']}-{single_platform['id']}"
            config_transfer_keyword = single_platform['transfrom_keywork']
            config_designated_person = single_platform['designated_person']
            config_refresh_interval = single_platform['refresh_interval']
            config_name = f"{single_platform['platform_name']}-{single_platform['alias_name']}"
            transfer_name = single_platform['transfrom_name']
            designated_person = split_string_by_commas(config_designated_person)
            transfer_keyword = split_string_by_commas(config_transfer_keyword)

            coze_util = None
            bailian_util = None
            fast_util = None
            if config_chose_type== 0:
                coze_util =CozeUtil(config_token,coze_api_base,config_bot_id)
            elif config_chose_type== 1:
                bailian_util = BalianUtil(config_token,config_bot_id)
            elif config_chose_type== 2:
                fast_util = FastGPTClient(config_bot_id,config_token)

            global manual_intervention
            # 持续监听消息，有消息则对接大模型进行回复
            wxxd = WeiXiaoDian(storage_state_path=f"state_{config_platform}.json")
            wxxd.launchChat()
            # 纪录时间 用于刷新
            last_refresh_time = time.time()
            while not stop_event.is_set():  # 如果设置了停止事件，则退出循环
                current_time = time.time()
                if current_time - last_refresh_time > config_refresh_interval:
                    print("Refreshing the page...")
                    wxxd.pageReload()  # 刷新页面
                    last_refresh_time = current_time  # 更新最后刷新时间
                try:
                    # 持续监听消息，有消息则对接大模型进行回复 转人工依然获取 防止转机器后获取已经回复的
                    msgs = wxxd.getNextNewMessage(checkRedMessage=not manual_intervention)
                except Exception as e:
                    self.updateWebView.emit(f"py_add_msg({json.dumps(str(e)[:50])});")
                # 人工 跳出
                if manual_intervention:
                    print('=====人工========')
                    time.sleep(wait)
                    continue
                print('=====AI========')
                if msgs:
                    # 初始化一个空列表用于存储非空的文本内容
                    contents = []
                    chat_name = ''
                    # 遍历messages列表
                    for message in msgs:
                        if (message.type == 'text' or message.type == 'card') and message.content.strip():  # 确保类型为text且内容不为空（去除首尾空白后）
                            chat_name = message.who
                            contents.append(message.content)
                            # 处理消息逻辑
                        elif(message.type == 'image'):
                            chat_name = message.who
                            contents.append('[图片]')
                        else:
                            #未识别的消息
                            chat_name = message.who
                            contents.append('你好')
                            # 使用逗号拼接所有非空的内容
                    receive_msg = ','.join(contents)
                    if  receive_msg and designated_person and chat_name not in designated_person:
                        self.updateWebView.emit(f"py_add_msg({json.dumps('不在指定回复人中,默认不回复')});")
                        time.sleep(wait)
                        continue
                    self.updateWebView.emit(f"py_add_msg({json.dumps('===============')});")
                    js_receive_msg = f"{config_name}|收到消息::{receive_msg}"
                    self.updateWebView.emit(f"py_add_msg({json.dumps(js_receive_msg)});")
                    self.updateWebView.emit(f"py_add_msg({json.dumps(config_name+'|正在请求模型回复...')});")
                    # 定义一个匿名函数（lambda）作为回调函数，包含两个逻辑
                    message_handler = lambda reply, js_reply: (
                        wxxd.sendMsg(reply),
                        self.updateWebView.emit(f"py_add_msg({json.dumps(config_name+'|'+js_reply)});")
                    )
                    try:
                        # 调用 send_message_and_poll 方法并传递回调函数
                        if config_chose_type== 0:
                            # 调用 send_message_and_poll 方法并传递回调函数
                            coze_util.send_message_and_poll(config_platform+'_'+chat_name, receive_msg, message_handler,)
                        elif config_chose_type== 1:
                            bailian_util.send_message_and_poll(config_platform+'_bl'+chat_name, receive_msg, message_handler)
                        elif config_chose_type== 2:
                            fast_util.send_chat_completion(config_platform+'_fast'+chat_name, receive_msg, message_handler)
                    except Exception as e:
                        self.updateWebView.emit(f"py_add_msg({json.dumps(str(e)[:50])});")
                time.sleep(wait)
            wxxd.stopLaunch()
        except Exception as e:
            print(e)
            logging.error(e)
            wxxd.stopLaunch()
            self.updateWebView.emit(f"py_set_platform_status({json.dumps(single_platform['id'])});")
            self.updateWebView.emit(f"py_add_msg({json.dumps(single_platform['platform_name']+'-'+single_platform['alias_name']+'平台报错停止:'+str(e))});")


    # 视频号私信
    def sph_task(self,single_platform,stop_event):
        from shipinhao.shipinhao import ShiPinHao
        try:
            config_chose_type = single_platform['connect_type_id']
            config_token = single_platform['token']
            config_bot_id = single_platform['bot_id']
            config_platform = f"{single_platform['platform_type']}-{single_platform['id']}"
            config_transfer_keyword = single_platform['transfrom_keywork']
            config_designated_person = single_platform['designated_person']
            config_refresh_interval = single_platform['refresh_interval']
            config_name = f"{single_platform['platform_name']}-{single_platform['alias_name']}"
            transfer_name = single_platform['transfrom_name']
            designated_person = split_string_by_commas(config_designated_person)
            transfer_keyword = split_string_by_commas(config_transfer_keyword)

            coze_util = None
            bailian_util = None
            fast_util = None
            if config_chose_type== 0:
                coze_util =CozeUtil(config_token,coze_api_base,config_bot_id)
            elif config_chose_type== 1:
                bailian_util = BalianUtil(config_token,config_bot_id)
            elif config_chose_type== 2:
                fast_util = FastGPTClient(config_bot_id,config_token)
            global manual_intervention
            # 持续监听消息，有消息则对接大模型进行回复
            sph = ShiPinHao(storage_state_path=f"state_{config_platform}.json")
            sph.launchChat()
            # 纪录时间 用于刷新
            last_refresh_time = time.time()
            while not stop_event.is_set():  # 如果设置了停止事件，则退出循环
                    current_time = time.time()
                    if current_time - last_refresh_time > config_refresh_interval:
                        print("Refreshing the page...")
                        sph.pageReload()  # 刷新页面
                        last_refresh_time = current_time  # 更新最后刷新时间
                    msgs = sph.getNextNewMessage(checkRedMessage=not manual_intervention)
                    # 人工 跳出
                    if manual_intervention:
                        print('=====人工========')
                        time.sleep(wait)
                        continue
                    print('=====AI========')
                    # 如果没消息跳转tab
                    if not msgs:
                        sph.clickAutoSwitchTabs()
                        # pass
                    else:
                        # 初始化一个空列表用于存储非空的文本内容
                        contents = []
                        chat_name = ''
                        # 遍历messages列表
                        for message in msgs:
                            if message.type == 'text' and message.content.strip():  # 确保类型为text且内容不为空（去除首尾空白后）
                                chat_name = message.who
                                contents.append(message.content)
                                # 处理消息逻辑
                        else:
                            #未识别的消息
                            chat_name = message['who']
                            contents.append('你好')
                        # 使用逗号拼接所有非空的内容
                        receive_msg = ','.join(contents)
                        if  receive_msg and designated_person and chat_name not in designated_person:
                            self.updateWebView.emit(f"py_add_msg({json.dumps('不在指定回复人中,默认不回复')});")
                            time.sleep(wait)
                            continue
                        self.updateWebView.emit(f"py_add_msg({json.dumps('===============')});")
                        js_receive_msg =  f"{config_name}|收到消息::{receive_msg}"
                        self.updateWebView.emit(f"py_add_msg({json.dumps(js_receive_msg)});")
                        self.updateWebView.emit(f"py_add_msg({json.dumps(config_name+'|正在请求模型回复...')});")
                        # 定义一个匿名函数（lambda）作为回调函数，包含两个逻辑
                        message_handler = lambda reply, js_reply: (
                            sph.sendMsg(reply),
                            self.updateWebView.emit(f"py_add_msg({json.dumps(js_reply)});")
                        )
                        # 调用 send_message_and_poll 方法并传递回调函数
                        if config_chose_type== 0:
                            # 调用 send_message_and_poll 方法并传递回调函数
                            coze_util.send_message_and_poll(config_platform+'_'+chat_name, receive_msg, message_handler,)
                        elif config_chose_type== 1:
                            bailian_util.send_message_and_poll(config_platform+'_bl'+chat_name, receive_msg, message_handler)
                        elif config_chose_type== 2:
                            fast_util.send_chat_completion(config_platform+'_fast'+chat_name, receive_msg, message_handler)

                    time.sleep(wait)
            sph.stopLaunch()
        except Exception as e:
            print(e)
            logging.error(e)
            sph.stopLaunch()
            self.updateWebView.emit(f"py_set_platform_status({json.dumps(single_platform['id'])});")
            self.updateWebView.emit(f"py_add_msg({json.dumps(single_platform['platform_name']+'-'+single_platform['alias_name']+'平台报错停止:'+str(e))});")


    # 微信回复
    def wx_task(self,single_platform,stop_event):
        pass


def main():
    # 配置日志
    setup_logging()
    # 确认日志系统是否正常工作
    logging.info("开始启动应用程序")
    window = QApplication(sys.argv)
    TheWin = MainWindow()
    sys.exit(window.exec_())


if __name__ == '__main__':
    main()
