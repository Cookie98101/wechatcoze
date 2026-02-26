from wechatauto import uiautomation as uia
import datetime
import time
import os
import re
from .utils import *

class WxParam:
    SYS_TEXT_HEIGHT = 33
    TIME_TEXT_HEIGHT = 34
    RECALL_TEXT_HEIGHT = 45
    CHAT_TEXT_HEIGHT = 52
    CHAT_IMG_HEIGHT = 117
    DEFALUT_SAVEPATH = os.path.join(os.getcwd(), '自动保存图片')

class QianNiuBase:

    def _split(self, MsgItem):
        uia.SetGlobalSearchTimeout(0)
        MsgItemName = MsgItem.Name
        if MsgItem.BoundingRectangle.height() == WxParam.SYS_TEXT_HEIGHT:
            Msg = ['SYS', MsgItemName, ''.join([str(i) for i in MsgItem.GetRuntimeId()])]
        elif MsgItem.BoundingRectangle.height() == WxParam.TIME_TEXT_HEIGHT:
            Msg = ['Time', MsgItemName, ''.join([str(i) for i in MsgItem.GetRuntimeId()])]
        elif MsgItem.BoundingRectangle.height() == WxParam.RECALL_TEXT_HEIGHT:
            if '撤回' in MsgItemName:
                Msg = ['Recall', MsgItemName, ''.join([str(i) for i in MsgItem.GetRuntimeId()])]
            else:
                Msg = ['SYS', MsgItemName, ''.join([str(i) for i in MsgItem.GetRuntimeId()])]
        else:
            Index = 1
            User = MsgItem.ButtonControl(foundIndex=Index)
            try:
                while True:
                    if User.Name == '':
                        Index += 1
                        User = MsgItem.ButtonControl(foundIndex=Index)
                    else:
                        break
                winrect = MsgItem.BoundingRectangle
                mid = (winrect.left + winrect.right)/2
                if User.BoundingRectangle.left < mid:
                    if MsgItem.TextControl().Exists(0.1) and MsgItem.TextControl().BoundingRectangle.top < User.BoundingRectangle.top:
                        name = (User.Name, MsgItem.TextControl().Name)
                    else:
                        name = (User.Name, User.Name)
                else:
                    name = 'Self'
                Msg = [name, MsgItemName, ''.join([str(i) for i in MsgItem.GetRuntimeId()])]
            except:
                Msg = ['SYS', MsgItemName, ''.join([str(i) for i in MsgItem.GetRuntimeId()])]
        uia.SetGlobalSearchTimeout(10.0)
        return ParseMessage(Msg, MsgItem, self)

class Message:
    type = 'message'

    def __getitem__(self, index):
        return self.info[index]

    def __str__(self):
        return self.content

    def __repr__(self):
        return str(self.info[:2])


class SysMessage(Message):
    type = 'sys'

    def __init__(self, info, control, wx):
        self.info = info
        self.control = control
        self.wx = wx
        self.sender = info[0]
        self.content = info[1]
        self.id = info[-1]
        wxlog.debug(f"【系统消息】{self.content}")

    # def __repr__(self):
    #     return f'<wxauto SysMessage at {hex(id(self))}>'


class TimeMessage(Message):
    type = 'time'

    def __init__(self, info, control, wx):
        self.info = info
        self.control = control
        self.wx = wx
        self.time = ParseWeChatTime(info[1])
        self.sender = info[0]
        self.content = info[1]
        self.id = info[-1]
        wxlog.debug(f"【时间消息】{self.time}")

    # def __repr__(self):
    #     return f'<wxauto TimeMessage at {hex(id(self))}>'


class RecallMessage(Message):
    type = 'recall'

    def __init__(self, info, control, wx):
        self.info = info
        self.control = control
        self.wx = wx
        self.sender = info[0]
        self.content = info[1]
        self.id = info[-1]
        wxlog.debug(f"【撤回消息】{self.content}")

    # def __repr__(self):
    #     return f'<wxauto RecallMessage at {hex(id(self))}>'


class SelfMessage(Message):
    type = 'self'

    def __init__(self, info, control, obj):
        self.info = info
        self.control = control
        self._winobj = obj
        self.sender = info[0]
        self.content = info[1]
        self.id = info[-1]
        self.chatbox = obj.ChatBox if hasattr(obj, 'ChatBox') else obj.UiaAPI
        wxlog.debug(f"【自己消息】{self.content}")

    # def __repr__(self):
    #     return f'<wxauto SelfMessage at {hex(id(self))}>'

    def quote(self, msg):
        """引用该消息

        Args:
            msg (str): 引用的消息内容

        Returns:
            bool: 是否成功引用
        """
        wxlog.debug(f'发送引用消息：{msg}  --> {self.sender} | {self.content}')
        self._winobj._show()
        headcontrol = [i for i in self.control.GetFirstChildControl().GetChildren() if i.ControlTypeName == 'ButtonControl'][0]
        RollIntoView(self.chatbox.ListControl(), headcontrol, equal=True)
        xbias = int(headcontrol.BoundingRectangle.width()*1.5)
        headcontrol.RightClick(x=-xbias, simulateMove=False)
        menu = self._winobj.UiaAPI.MenuControl(ClassName='CMenuWnd')
        quote_option = menu.MenuItemControl(Name="引用")
        if not quote_option.Exists(maxSearchSeconds=0.1):
            wxlog.debug('该消息当前状态无法引用')
            return False
        quote_option.Click(simulateMove=False)
        editbox = self.chatbox.EditControl(searchDepth=15)
        t0 = time.time()
        while True:
            if time.time() - t0 > 10:
                raise TimeoutError(f'发送消息超时 --> {msg}')
            SetClipboardText(msg)
            editbox.SendKeys('{Ctrl}v')
            if editbox.GetValuePattern().Value.replace('\r￼', ''):
                break
        editbox.SendKeys('{Enter}')
        return True

    def forward(self, friend):
        """转发该消息

        Args:
            friend (str): 转发给的好友昵称、备注或微信号

        Returns:
            bool: 是否成功转发
        """
        wxlog.debug(f'转发消息：{self.sender} --> {friend} | {self.content}')
        self._winobj._show()
        headcontrol = [i for i in self.control.GetFirstChildControl().GetChildren() if i.ControlTypeName == 'ButtonControl'][0]
        RollIntoView(self.chatbox.ListControl(), headcontrol, equal=True)
        xbias = int(headcontrol.BoundingRectangle.width()*1.5)
        headcontrol.RightClick(x=-xbias, simulateMove=False)
        menu = self._winobj.UiaAPI.MenuControl(ClassName='CMenuWnd')
        forward_option = menu.MenuItemControl(Name="转发...")
        if not forward_option.Exists(maxSearchSeconds=0.1):
            wxlog.debug('该消息当前状态无法转发')
            return False
        forward_option.Click(simulateMove=False)
        SetClipboardText(friend)
        contactwnd = self._winobj.UiaAPI.WindowControl(ClassName='SelectContactWnd')
        contactwnd.SendKeys('{Ctrl}a', waitTime=0)
        contactwnd.SendKeys('{Ctrl}v')
        checkbox = contactwnd.ListControl().CheckBoxControl()
        if checkbox.Exists(1):
            checkbox.Click(simulateMove=False)
            contactwnd.ButtonControl(Name='发送').Click(simulateMove=False)
            return True
        else:
            contactwnd.SendKeys('{Esc}')
            raise Exception(f'未找到好友：{friend}')

    def parse(self):
        """解析合并消息内容，当且仅当消息内容为合并转发的消息时有效"""
        wxlog.debug(f'解析合并消息内容：{self.sender} | {self.content}')
        self._winobj._show()
        headcontrol = [i for i in self.control.GetFirstChildControl().GetChildren() if i.ControlTypeName == 'ButtonControl'][0]
        RollIntoView(self.chatbox.ListControl(), headcontrol, equal=True)
        xbias = int(headcontrol.BoundingRectangle.width()*1.5)
        headcontrol.Click(x=-xbias, simulateMove=False)
        chatrecordwnd = uia.WindowControl(ClassName='ChatRecordWnd', searchDepth=1)
        msgitems = chatrecordwnd.ListControl().GetChildren()
        msgs = []
        for msgitem in msgitems:
            textcontrols = [i for i in GetAllControl(msgitem) if i.ControlTypeName == 'TextControl']
            who = textcontrols[0].Name
            time = textcontrols[1].Name
            try:
                content = textcontrols[2].Name
            except IndexError:
                content = ''
            msgs.append(([who, content, ParseWeChatTime(time)]))
        chatrecordwnd.SendKeys('{Esc}')
        return msgs

class FriendMessage(Message):
    type = 'friend'

    def __init__(self, info, control, obj):
        self.info = info
        self.control = control
        self._winobj = obj
        self.sender = info[0][0]
        self.sender_remark = info[0][1]
        self.content = info[1]
        self.id = info[-1]
        self.info[0] = info[0][0]
        self.chatbox = obj.ChatBox if hasattr(obj, 'ChatBox') else obj.UiaAPI
        if self.sender == self.sender_remark:
            wxlog.debug(f"【好友消息】{self.sender}: {self.content}")
        else:
            wxlog.debug(f"【好友消息】{self.sender}({self.sender_remark}): {self.content}")

    # def __repr__(self):
    #     return f'<wxauto FriendMessage at {hex(id(self))}>'

    def quote(self, msg):
        """引用该消息

        Args:
            msg (str): 引用的消息内容

        Returns:
            bool: 是否成功引用
        """
        wxlog.debug(f'发送引用消息：{msg}  --> {self.sender} | {self.content}')
        self._winobj._show()
        headcontrol = [i for i in self.control.GetFirstChildControl().GetChildren() if i.ControlTypeName == 'ButtonControl'][0]
        RollIntoView(self.chatbox.ListControl(), headcontrol, equal=True)
        xbias = int(headcontrol.BoundingRectangle.width()*1.5)
        headcontrol.RightClick(x=xbias, simulateMove=False)
        menu = self._winobj.UiaAPI.MenuControl(ClassName='CMenuWnd')
        quote_option = menu.MenuItemControl(Name="引用")
        if not quote_option.Exists(maxSearchSeconds=0.1):
            wxlog.debug('该消息当前状态无法引用')
            return False
        quote_option.Click(simulateMove=False)
        editbox = self.chatbox.EditControl(searchDepth=15)
        t0 = time.time()
        while True:
            if time.time() - t0 > 10:
                raise TimeoutError(f'发送消息超时 --> {msg}')
            SetClipboardText(msg)
            editbox.SendKeys('{Ctrl}v')
            if editbox.GetValuePattern().Value.replace('\r￼', ''):
                break
        editbox.SendKeys('{Enter}')
        return True

    def forward(self, friend):
        """转发该消息

        Args:
            friend (str): 转发给的好友昵称、备注或微信号

        Returns:
            bool: 是否成功转发
        """
        wxlog.debug(f'转发消息：{self.sender} --> {friend} | {self.content}')
        self._winobj._show()
        headcontrol = [i for i in self.control.GetFirstChildControl().GetChildren() if i.ControlTypeName == 'ButtonControl'][0]
        RollIntoView(self.chatbox.ListControl(), headcontrol, equal=True)
        xbias = int(headcontrol.BoundingRectangle.width()*1.5)
        headcontrol.RightClick(x=xbias, simulateMove=False)
        menu = self._winobj.UiaAPI.MenuControl(ClassName='CMenuWnd')
        forward_option = menu.MenuItemControl(Name="转发...")
        if not forward_option.Exists(maxSearchSeconds=0.1):
            wxlog.debug('该消息当前状态无法转发')
            return False
        forward_option.Click(simulateMove=False)
        SetClipboardText(friend)
        contactwnd = self._winobj.UiaAPI.WindowControl(ClassName='SelectContactWnd')
        contactwnd.SendKeys('{Ctrl}a', waitTime=0)
        contactwnd.SendKeys('{Ctrl}v')
        checkbox = contactwnd.ListControl().CheckBoxControl()
        if checkbox.Exists(1):
            checkbox.Click(simulateMove=False)
            contactwnd.ButtonControl(Name='发送').Click(simulateMove=False)
            return True
        else:
            contactwnd.SendKeys('{Esc}')
            raise FriendNotFoundError(f'未找到好友：{friend}')

    def parse(self):
        """解析合并消息内容，当且仅当消息内容为合并转发的消息时有效"""
        wxlog.debug(f'解析合并消息内容：{self.sender} | {self.content}')
        self._winobj._show()
        headcontrol = [i for i in self.control.GetFirstChildControl().GetChildren() if i.ControlTypeName == 'ButtonControl'][0]
        RollIntoView(self.chatbox.ListControl(), headcontrol, equal=True)
        xbias = int(headcontrol.BoundingRectangle.width()*1.5)
        headcontrol.Click(x=xbias, simulateMove=False)
        chatrecordwnd = uia.WindowControl(ClassName='ChatRecordWnd', searchDepth=1)
        msgitems = chatrecordwnd.ListControl().GetChildren()
        msgs = []
        for msgitem in msgitems:
            textcontrols = [i for i in GetAllControl(msgitem) if i.ControlTypeName == 'TextControl']
            who = textcontrols[0].Name
            time = textcontrols[1].Name
            try:
                content = textcontrols[2].Name
            except IndexError:
                content = ''
            msgs.append(([who, content, ParseWeChatTime(time)]))
        chatrecordwnd.SendKeys('{Esc}')
        return msgs



message_types = {
    'SYS': SysMessage,
    'Time': TimeMessage,
    'Recall': RecallMessage,
    'Self': SelfMessage
}

def ParseMessage(data, control, wx):
    return message_types.get(data[0], FriendMessage)(data, control, wx)