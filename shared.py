# from PyQt5.QtCore import *

# class JsBridge(QObject):
#     '''
#     共享类  js调用python方法
#     '''
#     @pyqtSlot(str, result=int)
#     def test_str_int(self, one_str):
#         print(one_str)
#         try:
#             r = int(one_str)
#         except Exception:
#             return -1
#         return r

#     @pyqtSlot(int, result=str)
#     def test_int_str(self, num):
#         return str(num + 111)