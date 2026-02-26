from wechatauto import uiautomation as uia
from .utils import *
from .elements import *
import time
import os
import re

class QianNiu(QianNiuBase):
      """千牛UI自动化实例"""
      def __init__(self,debug: bool = False) -> None:
          self.chat_control = None
          self.usedmsgid = []
          self.qian_niu_window = None
          self.first_launch = True
          self.user_name='' #用于判断是否是机器人点击新窗口还是人为点击新窗口

      #     点击消息框
      def check_and_handle_message(self):
                  # 从桌面（根）开始查找
            desktop = uia.GetRootControl()

            # 查找具有特定 AutomationId 的 TreeControl 控件，这里是消息提示框
            self.msg_tree_control = desktop.TreeControl(AutomationId="MessageMergeNotifyView.messageMergeList", ClassName='UITreeView')

            if self.msg_tree_control.Exists(0, 0):  # 检查是否存在此控件
                  print("找到了消息提示框。")

                  # 找到第一个 TreeItemControl，即第一个消息
                  first_tree_item = self.msg_tree_control.GetFirstChildControl()

                  if first_tree_item.Exists(0, 0):
                        # 记录用户名，这里通过 Name 属性获取
                        user_name = first_tree_item.Name
                        print(f"第一个消息的用户名是：{user_name}")
                        # 点击第一个消息
                        first_tree_item.Click()
                        return user_name
                        print("已点击第一个消息。")
                  else:
                        print("未能找到任何消息项。")
            else:
                  print("未找到消息提示框。请检查控件的自动化属性是否正确。")
            return  None

      #获取接待台消息容器
      def find_qianniu_chat(self):
            # 从桌面（根）开始查找
            desktop = uia.GetRootControl()

            # 查找千牛接待台窗口
            self.qian_niu_window = desktop.WindowControl(searchDepth=1, ClassName='MutilChatView', Name='千牛接待台')

            if not self.qian_niu_window.Exists(0, 0):
                  print("未找到千牛接待台窗口。")
                  return None

            print("找到了千牛接待台窗口。")

            # 使用 searchDepth 查找名为“千牛消息聊天”的 DocumentControl
            # 这里我们假设它不会超过第5层，根据实际情况调整 searchDepth
            self.chat_control = self.qian_niu_window.DocumentControl(searchDepth=5, Name="千牛消息聊天")

            if self.chat_control.Exists(0, 0):
                  print(f"找到了千牛消息聊天控件: {self.chat_control.Name}")
                  return self.chat_control
            else:
                  print("未能找到千牛消息聊天控件。")
                  return None

      def get_first_child_at_each_level(self,control, level=1):
            """
            递归获取每一层的第一个子控件

            :param control: 当前层的控件
            :param level: 当前层数，默认为1表示第一层
            :return: 最深层的第一个子控件
            """
            print(f"进入第 {level} 层")
            # 尝试获取当前控件的第一个子控件
            first_child = control.GetFirstChildControl()

            if first_child is None:
                  # 如果没有子控件，则返回当前控件作为最深控件
                  print("已到达最后一层，无更多子控件")
                  return control
            else:
                  # 如果有子控件，则继续向下一层递归
                  return self.get_first_child_at_each_level(first_child, level + 1)


      def get_chat_messages(self):
            msg_list = self.chat_control.Control(AutomationId='J_msg_list', Depth=5)
            messages = []

            for msg_item in msg_list.GetChildren():
                  try:
                        if  not msg_item.GetChildren():
                              continue

                        type,sender, content , is_friend,run_time_id = None,"", "",False,''
                        who = ''
                        for child in msg_item.GetChildren():
                              if child.ControlType == uia.ControlType.TextControl:
                                    name = child.Name.strip()
                                    # 定义日期时间模式
                                    datetime_pattern = r'\d{4}-\d{1,2}-\d{1,2}\s\d{1,2}:\d{1,2}:\d{1,2}'
                                    # 检查日期时间是否在字符串开头 是就是我的消息
                                    if re.match(r'^' + datetime_pattern, name):
                                          who = name
                                          is_friend = False
                                    # 检查日期时间是否在字符串结尾  结尾是对方的消息
                                    else:
                                         # 正则表达式模式，用于匹配日期时间之前的所有字符 就是用户昵称
                                          pattern = r'^(.*?)(\d{4}-\d{1,2}-\d{1,2}\s\d{1,2}:\d{1,2}:\d{1,2})'
                                          # 使用re.search找到匹配项
                                          match = re.search(pattern, name)
                                          if match:
                                                # 提取出日期时间之前的名称部分
                                                who = match.group(1).strip()
                                          is_friend = True

                              elif child.ControlType == uia.ControlType.GroupControl:
                                    try:
                                          if child.GetChildren():
                                                one_level = child.GetFirstChildControl()
                                                if one_level.Name and one_level.Name=='图片消息':
                                                      type='img'
                                                      content = '[图片]'
                                                      run_time_id = ''.join([str(i) for i in one_level.GetRuntimeId()])
                                                      break
                                                elif one_level.GetChildren():
                                                      two_level = one_level.GetFirstChildControl()
                                                      three_level_childern = two_level.GetChildren()
                                                      if three_level_childern:
                                                            zixun = three_level_childern[1]
                                                            if zixun.Name == '月销':
                                                                  type ='card'
                                                                  content = '我要咨询这个规格的商品:'+ one_level.Name
                                                                  run_time_id = ''.join([str(i) for i in one_level.GetRuntimeId()])
                                                                  break

                                                      else:
                                                            type ='text'
                                                            content = getattr(two_level, 'Name', '').strip() or '未知消息' if two_level else '未知消息'
                                                            run_time_id = ''.join([str(i) for i in one_level.GetRuntimeId()])
                                                            break
                                    except Exception as e:
                                          type ='text'
                                          content='未知消息'
                                          print(e)
                        if content:
                              messages.append({
                                    'who':who,
                                    'run_time_id':run_time_id,
                                    'sender': name,
                                    'type':type,
                                    'content': content,
                                    'is_friend':is_friend
                              })
                  except Exception as e:
                        print('error========查找消息失败')
                        print(e)
                        raise e

            return messages

      def set_usedmsgid(self,all_msg):
            self.usedmsgid = [message['run_time_id'] for message in all_msg if message.get('is_friend')]


      def GetNextNewMessage(self,checkRedMessage=True):
            # 如果是第一次启动
            if self.first_launch:
                  # 接待台已经打开
                  self.first_launch = False
                  if self.find_qianniu_chat():
                        return self.checkCurrentChatNew(checkRedMessage)

            # 如果停留在当前页面
            if self.find_qianniu_chat():
                  all_msg = self.get_chat_messages()
                  tmp_msgid = [message['run_time_id'] for message in all_msg if message.get('is_friend')]
                  # 提前对话框里第一个朋友的消息 用于比对是否是人随便切了聊天框
                  first_freind_msg = None
                  for item in all_msg:
                        if item["is_friend"]:
                              first_freind_msg = item
                              break
                  # username不是自动点击的 是人随便切换的页面
                  if first_freind_msg and first_freind_msg['who']!=self.user_name:
                        self.user_name = first_freind_msg['who']
                        self.set_usedmsgid(all_msg)

                  if tmp_msgid == self.usedmsgid:
                        return self.checkNewNotice() if checkRedMessage else []
                  else:
                        # 提取不在self.usedmsgid_set里的tmp_msgid元素
                        not_read_msgid =  [msgid for msgid in tmp_msgid if msgid not in self.usedmsgid]
                        not_msg = [msg for msg in all_msg if msg['run_time_id'] in not_read_msgid]
                        self.set_usedmsgid(all_msg)
                        return not_msg if checkRedMessage else []
            else:
                 return self.checkNewNotice() if checkRedMessage else []

      def checkCurrentChatNew(self,checkRedMessage=True):
            self.find_qianniu_chat()
            all_msgs = self.get_chat_messages()
            # 取出最后我回复的之后的客服的消息
            last_false_index = -1  # 最后一个is_friend为False的索引，默认设置为-1表示未找到
            # 找到最后一个is_friend为False的元素的索引
            for i, msg in enumerate(all_msgs):
                  if 'is_friend' in msg and msg['is_friend'] == False and ':服务助手' not in msg['sender']:
                        last_false_index = i

            result = []
            # 如果找到了is_friend为False的元素，则从其后的第一个元素开始找is_friend=True的元素
            start_index = last_false_index + 1
            for i in range(start_index, len(all_msgs)):
                  if 'is_friend' in all_msgs[i] and all_msgs[i]['is_friend'] == True:
                        result.append(all_msgs[i])
            # 更新msgid
            self.set_usedmsgid(all_msgs)
            return result if checkRedMessage else []

      def checkNewNotice(self):
            # 检查消息框 有 点击 获取用户名
            user_name = self.check_and_handle_message()
            if user_name:
                  time.sleep(1)
                  self.user_name = user_name
                  return self.checkCurrentChatNew()
            else:
                  return []

      # 转交消息
      def transferOther(self,other,single_transfer):
            try:
                  # 从桌面开始
                  desktop = uia.GetRootControl()

                  # 假设"千牛接待台"是直接在桌面上的一个窗口，我们先找到这个窗口
                  kwtk_window = desktop.WindowControl(searchDepth=1, ClassName='MutilChatView', Name='千牛接待台')

                  if kwtk_window.Exists(0, 0):
                        # 根据祖先元素列表逐级向下查找，这里简化处理，实际情况可能需要根据具体属性进行搜索
                        # 找到包含目标控件的自定义控件或者组，这里以自动化ID为例
                        custom_control = kwtk_window.Control(searchDepth=10, AutomationId="UIWindow.mutilcentralwidget.stackedWidget.SingleChatView.centralwidget.stackedWidget.SubChatView.ChatDisplayWidget")

                        if custom_control.Exists(0, 0):
                              # 继续向下查找直到找到目标控件
                              target_control = custom_control.ButtonControl(Name='转发当前用户')

                              if target_control.Exists(0, 0):
                                    target_control.Click()
                                    time.sleep(1)
                                    kwtk_window_refresh = desktop.WindowControl(searchDepth=1, ClassName='MutilChatView', Name='千牛接待台')
                                    is_find_transfer = False
                                    for name in other:
                                          single_transfer(name)
                                          transfer_person_tab = None
                                          if name and name.startswith("[组]"):
                                                transfer_person_tab  = kwtk_window_refresh.TextControl(ClassName='QLabel',Name='转交到组')
                                                name = name[3:].strip()
                                                if not name:
                                                      continue
                                          else:
                                                transfer_person_tab  = kwtk_window_refresh.TextControl(ClassName='QLabel',Name='转交到人')

                                          if transfer_person_tab.Exists(0,0):
                                                transfer_person_tab.Click()
                                          transfer_parent = kwtk_window_refresh.CustomControl(ClassName='QStackedWidget')
                                          if transfer_parent.Exists(0,0):
                                                print("找到transfer_parent控件:", transfer_parent)
                                                transfer_edit =  transfer_parent.EditControl(ClassName='QLineEdit')
                                                if transfer_edit.Exists(0,0):
                                                       print("找到transfer_edit控件:", transfer_edit)
                                                       transfer_edit.SetFocus()
                                                       time.sleep(0.5)  # 等待控件聚焦
                                                       transfer_edit.SendKeys('{Ctrl}a', waitTime=0)
                                                       transfer_edit.SendKeys(name, waitTime=0.5)  # waitTime 参数是可选的，用于控制输入后的等待时间
                                                       # 找第一个转接人
                                                       tree_transfer = transfer_parent.TreeControl(ClassName='UITreeView')
                                                       if tree_transfer.Exists(0,0):
                                                             print("找到tree_transfer控件:", tree_transfer)
                                                             all_transfer = tree_transfer.GetChildren()
                                                             for item in all_transfer:
                                                                   if name  in item.Name:
                                                                         print('点击：：'+item.Name)
                                                                         is_find_transfer = True
                                                                         item.Click()
                                                                         break
                                                             time.sleep(0.5)
                                          if  is_find_transfer:
                                                break
                              if not is_find_transfer:
                                          self.sendMsg('未找到转交人')

                        else:
                              raise Exception("未能找到转发按钮父组件")
                  else:
                        raise Exception("未能找到转发按钮的千牛工作台")
            except Exception as e:
                  raise e

      # 发送消息
      def sendMsg(self,msg):
            try:
                  # 从桌面开始
                  desktop = uia.GetRootControl()

                  # 假设"千牛接待台"是直接在桌面上的一个窗口，我们先找到这个窗口
                  kwtk_window = desktop.WindowControl(searchDepth=1, ClassName='MutilChatView', Name='千牛接待台')

                  if kwtk_window.Exists(0, 0):
                      # 根据祖先元素列表逐级向下查找，这里简化处理，实际情况可能需要根据具体属性进行搜索
                      # 找到包含目标控件的自定义控件或者组，这里以自动化ID为例
                      custom_control = kwtk_window.Control(searchDepth=10, AutomationId="UIWindow.mutilcentralwidget.stackedWidget.SingleChatView.centralwidget.stackedWidget.SubChatView.ChatDisplayWidget")

                      if custom_control.Exists(0, 0):
                          # 继续向下查找直到找到目标控件
                          target_control = custom_control.EditControl(AutomationId="UIWindow.mutilcentralwidget.stackedWidget.SingleChatView.centralwidget.stackedWidget.SubChatView.ChatDisplayWidget.ChatContentView.splitter.sendMsgWidget.chatInputArea.plainTextEdit")

                          if target_control.Exists(0, 0):
                                print("找到控件:", target_control)
                                      # 确保控件处于激活状态（聚焦）
                                target_control.SetFocus()

                                # 向编辑框中写入内容
                                target_control.SendKeys(msg, waitTime=0.5)  # waitTime 参数是可选的，用于控制输入后的等待时间
                                time.sleep(0.5)
                                target_control.SetFocus()
                                target_control.SendKeys('{Enter}', waitTime=0.5)
                          else:
                                raise Exception("未能找到发送按钮")
                      else:
                            raise Exception("未能找到发送按钮父组件")
                  else:
                        raise Exception("未能找到发送按钮的千牛工作台")
            except Exception as e:
                  raise e

