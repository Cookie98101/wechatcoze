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
            if config_chose_type== 0:
                coze_util =CozeUtil(config_token,coze_api_base,config_bot_id)
            elif config_chose_type== 1:
                bailian_util = BalianUtil(config_token,config_bot_id)
            elif config_chose_type== 2:
                fast_util = FastGPTClient(config_bot_id,config_token)

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
            if config_chose_type== 0:
                coze_util =CozeUtil(config_token,coze_api_base,config_bot_id)
            elif config_chose_type== 1:
                bailian_util = BalianUtil(config_token,config_bot_id)
            elif config_chose_type== 2:
                fast_util = FastGPTClient(config_bot_id,config_token)

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
            product_only_waiting = {}
            last_user_msg_signature = {}
            processed_msg_signatures = {}
            processed_transfer_signatures = set()
            product_only_wait_seconds = 30
            duplicate_text_cooldown_seconds = 3
            processed_msg_ttl_seconds = 6 * 3600
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

            def send_reply_to_target(chat_name, reply_text):
                if chat_name:
                    sent_ok = dd.sendMsgToChat(chat_name, reply_text, switch_back=True)
                    if sent_ok:
                        return True
                    current_chat = ''
                    try:
                        current_chat = dd.getCurrentChatName()
                    except Exception:
                        current_chat = ''
                    if current_chat and (current_chat in chat_name or chat_name in current_chat):
                        dd.sendMsg(reply_text)
                        return True
                    self.updateWebView.emit(f"py_add_msg({json.dumps(config_name+'|会话定位失败，未发送（避免串会话）:'+str(chat_name))});")
                    return False
                dd.sendMsg(reply_text)
                return True

            def build_msg_signature(msg):
                msg_type = str(msg.get('type', ''))
                content = re.sub(r'\s+', ' ', str(msg.get('content', '') or '').strip())
                source = str(msg.get('source', ''))
                src = str(msg.get('src', ''))
                product_link = str(msg.get('product_link', ''))
                if msg_type == 'from_info':
                    return f"{msg_type}|{source}|{content}|{product_link}"
                return f"{msg_type}|{msg.get('index', '')}|{content}|{src}|{product_link}"

            llm_request_queue = queue.Queue()
            llm_result_queue = queue.Queue()
            llm_inflight_sessions = set()
            llm_pending_by_session = {}

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
                            'reply': holder.get('reply', ''),
                            'js_reply': holder.get('js_reply', ''),
                            'error': '',
                        })
                    except Exception as e:
                        llm_result_queue.put({
                            'session_key': session,
                            'chat_name': task.get('chat_name', ''),
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
                            send_reply_to_target(target_chat, final_reply)
                        except Exception as e:
                            err_text = str(e)
                            logging.error(err_text)
                            if "图片路径不对或者没找到上传按钮" not in err_text:
                                self.updateWebView.emit(f"py_add_msg({json.dumps(config_name+'|报错:'+err_text[:50])});")
                        js_reply = result.get('js_reply', '')
                        if js_reply:
                            self.updateWebView.emit(f"py_add_msg({json.dumps(config_name+'|'+js_reply)});")
                    if done_session:
                        pending_tasks = llm_pending_by_session.get(done_session, [])
                        while pending_tasks:
                            pending_task = pending_tasks.pop(0)
                            if pending_task.get('direct_reply'):
                                direct_reply = pending_task.get('direct_reply', '')
                                direct_chat = pending_task.get('chat_name', '')
                                if direct_reply:
                                    send_reply_to_target(direct_chat, direct_reply)
                                    self.updateWebView.emit(f"py_add_msg({json.dumps(config_name+'|回复消息::'+direct_reply)});")
                                continue
                            llm_inflight_sessions.add(done_session)
                            llm_request_queue.put(pending_task)
                            break
                        if not pending_tasks:
                            llm_pending_by_session.pop(done_session, None)

                msgs = []
                current_time = time.time()
                if current_time - last_refresh_time > config_refresh_interval:
                    print("Refreshing the page...")
                    dd.pageReload()  # 刷新页面
                    last_refresh_time = current_time  # 更新最后刷新时间
                try:
                    # 持续监听消息，有消息则对接大模型进行回复 转人工依然获取 防止转机器后获取已经回复的
                    msgs = dd.getNextNewMessage(checkRedMessage=not manual_intervention,
                                                config_checked_greetings=config_checked_greetings,
                                                config_greetings=config_greetings)
                except Exception as e:
                    self.updateWebView.emit(f"py_add_msg({json.dumps(str(e)[:50])});")
                if msgs:
                    # 给客户连续发送“链接+问题”一个短聚合窗口，尽量同批处理，减少前后错位回复
                    try:
                        time.sleep(0.7)
                        extra_msgs = dd.getNextNewMessage(checkRedMessage=False,
                                                          config_checked_greetings=config_checked_greetings,
                                                          config_greetings=config_greetings)
                        if extra_msgs:
                            seen = {(m.get('index'), m.get('type'), m.get('content')) for m in msgs}
                            for m in extra_msgs:
                                sig = (m.get('index'), m.get('type'), m.get('content'))
                                if sig not in seen:
                                    seen.add(sig)
                                    msgs.append(m)
                    except Exception:
                        pass

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

                    now_sig_ts = time.time()
                    seen_map = processed_msg_signatures.setdefault(cache_key, {})
                    fresh_msgs = []
                    skipped_count = 0
                    for message in msgs:
                        sig = build_msg_signature(message)
                        if not sig:
                            fresh_msgs.append(message)
                            continue
                        last_seen_ts = seen_map.get(sig)
                        if last_seen_ts and now_sig_ts - last_seen_ts < processed_msg_ttl_seconds:
                            skipped_count += 1
                            continue
                        seen_map[sig] = now_sig_ts
                        fresh_msgs.append(message)
                    if seen_map:
                        for sig, ts in list(seen_map.items()):
                            if now_sig_ts - ts >= processed_msg_ttl_seconds:
                                seen_map.pop(sig, None)
                    if skipped_count > 0:
                        self.updateWebView.emit(f"py_add_msg({json.dumps(config_name+'|过滤历史重复消息:'+str(skipped_count))});")
                    if not fresh_msgs:
                        time.sleep(wait)
                        continue
                    msgs = fresh_msgs

                    # 初始化一个空列表用于存储非空的文本内容
                    contents = []
                    chat_name = ''
                    product_events_primary = []
                    product_events_panel = []
                    user_texts = []
                    user_text_signatures = []
                    # 遍历messages列表
                    for message in msgs:
                        if (message['type'] == 'text' or message['type'] == 'card' or message['type'] == 'from_info' or message['type'] == 'img') and message['content'].strip():  # 确保类型为text且内容不为空（去除首尾空白后）
                            chat_name = message['who']
                            contents.append(message['content'])
                            if message['type'] in ('text', 'card', 'from_info') and any(m in message['content'] for m in product_markers):
                                if '没有咨询过宝贝' not in message['content'] and '暂无咨询' not in message['content'] and '暂无商品' not in message['content']:
                                    source = message.get('source', '')
                                    if message['type'] == 'card':
                                        normalized_source = 'card'
                                    elif source in ('link', 'system', 'panel'):
                                        normalized_source = source
                                    else:
                                        normalized_source = 'text'
                                    event = {
                                        "text": message['content'],
                                        "source": normalized_source,
                                        "product_id": extract_product_id(message['content']),
                                    }
                                    if normalized_source in ('card', 'link', 'system', 'text'):
                                        product_events_primary.append(event)
                                    elif normalized_source == 'panel':
                                        product_events_panel.append(event)
                            if message['type'] == 'text':
                                user_texts.append(message['content'])
                                user_text_signatures.append(f"{message.get('index','')}::{message['content']}")
                            # 处理消息逻辑
                        else:
                            #未识别的消息
                            chat_name = message['who']
                            contents.append('你好')
                    # 原始聚合内容（仅用于解析/调试），模型输入后续会压缩为“最新问题+商品上下文”
                    raw_receive_msg = ','.join(contents)
                    receive_msg = raw_receive_msg
                    user_question = user_texts[-1].strip() if user_texts else ''
                    cache_key = cache_key or chat_name or f"{config_platform}_default"
                    latest_user_text = user_texts[-1].strip() if user_texts else ''
                    curr_sig = " | ".join(user_text_signatures)
                    if user_texts:
                        prev_sig_info = last_user_msg_signature.get(cache_key)
                        if (
                            prev_sig_info
                            and prev_sig_info.get("sig") == curr_sig
                            and now_sig_ts - prev_sig_info.get("ts", 0) < duplicate_text_cooldown_seconds
                        ):
                            self.updateWebView.emit(f"py_add_msg({json.dumps(config_name+'|检测到重复客户消息，跳过本轮')});")
                            time.sleep(wait)
                            continue
                        last_user_msg_signature[cache_key] = {"sig": curr_sig, "ts": now_sig_ts}
                        product_only_waiting.pop(cache_key, None)
                    # 防止“已售xx件”进入模型上下文，避免回复夹带销量信息
                    raw_receive_msg = re.sub(r'已售\\s*\\d+(?:\\.\\d+)?\\s*(?:件|单|笔)?', '', raw_receive_msg)
                    raw_receive_msg = re.sub(r'\\s{2,}', ' ', raw_receive_msg).strip()
                    receive_msg = raw_receive_msg
                    selected_primary_event = product_events_primary[-1] if product_events_primary else None
                    selected_panel_event = product_events_panel[-1] if product_events_panel else None
                    selected_product_event = selected_primary_event or selected_panel_event
                    context_info = None
                    if selected_primary_event:
                        context_info = update_product_context(cache_key, selected_primary_event, is_primary_source=True)
                    elif selected_panel_event:
                        current_ctx = product_cache.get(cache_key)
                        if not (current_ctx and current_ctx.get("locked_primary")):
                            context_info = update_product_context(cache_key, selected_panel_event, is_primary_source=False)
                    elif any(m in raw_receive_msg for m in product_markers):
                        if '没有咨询过宝贝' in raw_receive_msg or '暂无咨询' in raw_receive_msg or '暂无商品' in raw_receive_msg:
                            pass
                        else:
                            current_ctx = product_cache.get(cache_key)
                            if not (current_ctx and current_ctx.get("locked_primary")):
                                fallback_event = {
                                    "text": raw_receive_msg,
                                    "source": "text",
                                    "product_id": extract_product_id(raw_receive_msg),
                                }
                                context_info = update_product_context(cache_key, fallback_event, is_primary_source=False)
                    if context_info:
                        self.updateWebView.emit(
                            f"py_add_msg({json.dumps(config_name + '|商品上下文更新 session=' + format_session_for_log(cache_key) + ' source=' + context_info.get('source', '-') + ' id=' + (context_info.get('product_id', '-') or '-') + ' v=' + str(context_info.get('version', 1)))});"
                        )
                    if user_texts and not any(m in raw_receive_msg for m in product_markers):
                        cached = product_cache.get(cache_key)
                        if cached and time.time() - cached["ts"] <= product_cache_ttl:
                            receive_msg = f"{cached['text']}\n用户问题:{user_question or latest_user_text or raw_receive_msg}"
                            self.updateWebView.emit(
                                f"py_add_msg({json.dumps(config_name + '|复用商品上下文 session=' + format_session_for_log(cache_key) + ' source=' + cached.get('source', '-') + ' id=' + (cached.get('product_id', '-') or '-') + ' v=' + str(cached.get('version', 1)))});"
                            )
                        else:
                            receive_msg = latest_user_text or user_question or raw_receive_msg
                    if user_texts and any(m in raw_receive_msg for m in product_markers):
                        if selected_product_event:
                            receive_msg = f"{selected_product_event.get('text', raw_receive_msg)}\n用户问题:{latest_user_text or user_question or raw_receive_msg}"
                        else:
                            cached = product_cache.get(cache_key)
                            if cached and time.time() - cached["ts"] <= product_cache_ttl:
                                receive_msg = f"{cached.get('text', raw_receive_msg)}\n用户问题:{latest_user_text or user_question or raw_receive_msg}"
                            else:
                                receive_msg = latest_user_text or user_question or raw_receive_msg
                    if not user_texts and selected_product_event:
                        product_only_waiting[cache_key] = {
                            'ts': time.time(),
                            'chat_name': chat_name
                        }
                        self.updateWebView.emit(f"py_add_msg({json.dumps(config_name+'|仅收到商品信息，等待用户提问(30s)')});")
                        time.sleep(wait)
                        continue
                    if  receive_msg and designated_person and chat_name not in designated_person:
                        self.updateWebView.emit(f"py_add_msg({json.dumps('不在指定回复人中,默认不回复')});")
                        time.sleep(wait)
                        continue
                    self.updateWebView.emit(f"py_add_msg({json.dumps('===============')});")
                    js_receive_msg = f"{config_name}|收到消息::{receive_msg}"
                    self.updateWebView.emit(f"py_add_msg({json.dumps(js_receive_msg)});")
                    # 只使用客户文本触发转交，避免商品卡片里的售后词误触发
                    transfer_source_text = latest_user_text or ''
                    if transfer_source_text and transfer_name and transfer_keyword and any(s in transfer_source_text for s in transfer_keyword):
                        transfer_sig = f"{cache_key}::{curr_sig or transfer_source_text}"
                        if transfer_sig in processed_transfer_signatures:
                            self.updateWebView.emit(f"py_add_msg({json.dumps(config_name+'|重复转交触发，已忽略')});")
                            time.sleep(wait)
                            continue
                        processed_transfer_signatures.add(transfer_sig)
                        def single_transfer(name):
                            if str(name).startswith('未找到'):
                                return
                            self.updateWebView.emit(f"py_add_msg({json.dumps(config_name+'|正在转接给:'+name)});")
                        dd.transferOther(transfer_name,single_transfer)
                        time.sleep(wait)
                        continue

                    # 商品ID类问题优先走本地确定性回复，避免模型空答/乱答
                    if latest_user_text and any(re.search(p, latest_user_text, flags=re.IGNORECASE) for p in id_question_patterns):
                        local_ctx = receive_msg
                        cached = product_cache.get(cache_key)
                        if cached and time.time() - cached["ts"] <= product_cache_ttl:
                            local_ctx = f"{cached.get('text', '')}\n{receive_msg}"
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
                            'direct_reply': direct_reply,
                        }
                        if cache_key in llm_inflight_sessions:
                            pending_tasks = llm_pending_by_session.setdefault(cache_key, [])
                            pending_tasks.append(direct_task)
                            self.updateWebView.emit(f"py_add_msg({json.dumps(config_name+'|当前会话正在处理中，已排队问题数:'+str(len(pending_tasks)))});")
                        else:
                            send_reply_to_target(chat_name, direct_reply)
                            self.updateWebView.emit(f"py_add_msg({json.dumps(config_name+'|回复消息::'+direct_reply)});")
                        time.sleep(wait)
                        continue

                    llm_prefix = 'coze'
                    if config_chose_type == 1:
                        llm_prefix = 'bailian'
                    elif config_chose_type == 2:
                        llm_prefix = 'fastgpt'
                    llm_user_key = f"{config_platform}_{llm_prefix}_{cache_key}"
                    task_payloads = [receive_msg]
                    if user_texts and len(user_texts) > 1:
                        clean_questions = [q.strip() for q in user_texts if q and q.strip()]
                        if clean_questions:
                            context_text = ''
                            if selected_product_event:
                                context_text = selected_product_event.get('text', '')
                            else:
                                cached = product_cache.get(cache_key)
                                if cached and time.time() - cached["ts"] <= product_cache_ttl:
                                    context_text = cached.get('text', '')
                            if context_text:
                                task_payloads = [f"{context_text}\n用户问题:{q}" for q in clean_questions]
                            else:
                                task_payloads = clean_questions
                            self.updateWebView.emit(f"py_add_msg({json.dumps(config_name+'|检测到连续提问，逐条入队:'+str(len(task_payloads)))});")

                    for payload in task_payloads:
                        task = {
                            'session_key': cache_key,
                            'chat_name': chat_name,
                            'receive_msg': payload,
                            'llm_user_key': llm_user_key,
                        }
                        if cache_key in llm_inflight_sessions:
                            pending_tasks = llm_pending_by_session.setdefault(cache_key, [])
                            pending_tasks.append(task)
                            self.updateWebView.emit(f"py_add_msg({json.dumps(config_name+'|当前会话正在处理中，已排队问题数:'+str(len(pending_tasks)))});")
                        else:
                            llm_inflight_sessions.add(cache_key)
                            llm_request_queue.put(task)
                            self.updateWebView.emit(f"py_add_msg({json.dumps(config_name+'|正在请求模型回复...')});")

                if stop_event.is_set():
                    break
                now_ts = time.time()
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
                        sent_ok = dd.sendMsgToChat(chat_target, config_greetings, switch_back=True)
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
