1：安装Python3.X
2：安装依赖 执行安装requirments
3：打包命令
pyinstaller --windowed  --add-data "static_src;static_src" --add-data "F:\code\study\ai\wechatcoze\playwright;playwright/" --add-data "hui.ico;." main.py
4：uiautomation打印桌面元素
python test.py -t3 -c

5：升级时会下载最近版本，并覆盖到桌面快捷方式
