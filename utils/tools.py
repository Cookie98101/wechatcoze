import hashlib
import  re
import sys
import logging
import os
from datetime import datetime, date

def check_expiry():
    """
    检查当前日期是否超过2026年8月1日。
    如果超过，返回'plug error'；否则返回False。
    """
    # 定义目标日期：2026年8月1日
    target_date = date(2026, 8, 1)

    # 获取当前日期（忽略时间部分）
    current_date = datetime.now().date()

    # 比较日期
    if current_date > target_date:
        return True
    else:
        return False

def generate_stable_id(nickname: str) -> str:
    """
    根据用户昵称生成一个稳定的唯一标识符。

    # 示例调用
    nickname = "用户昵称@123!@#"
    stable_id = generate_stable_id(nickname)
    print(f"Generated Stable ID: {stable_id}")

    :param nickname: 用户的昵称
    :return: 基于昵称生成的固定哈希值
    """
    # 使用SHA-256算法对昵称进行哈希处理
    hash_object = hashlib.sha256(nickname.encode('utf-8'))

    # 返回哈希值的十六进制表示形式
    return hash_object.hexdigest()

def split_string_by_commas(input_string):
    """
    根据逗号分隔 成数组
    """
    # 检查是否为 None 或者空字符串
    if input_string is None or input_string == '':
        return []
    # 将中文逗号替换为英文逗号
    normalized_string = input_string.replace('，', ',')
    # 使用英文逗号分割字符串
    result_array = normalized_string.split(',')
    # 去除每个元素两端的空白字符
    result_array = [item.strip() for item in result_array]
    return result_array

# 识别coze返回的图片
def replace_image_tag_with_word(text):
    # # 原始文本
    # text = '这是图片1地址<图片>(D:\123.png)</ 图片 >这是图片2地址<图片>(D:\123.png)</ 图片 >'
    #
    # # 正则表达式匹配图片标签并捕获路径
    # pattern = r'<图片>$(.*?)$<\/\s*图片>'
    #
    # # 提取所有图片路径
    # image_paths = re.findall(pattern, text)
    #
    # # 替换所有图片标签为空字符
    # cleaned_text = re.sub(pattern, '', text)
    #
    # print("提取的图片地址:", image_paths)
    # print("清理后的文本:", cleaned_text)
    #
    # return cleaned_text , image_paths
    # 定义匹配模式，用于查找形如 [text](url) 的内容
    pattern = r'!\[([^\]]*)\]\(([^)]+)\)'

    # 存储找到的文本和URL
    found_items = []

    # 查找所有匹配项并存储
    for match in re.finditer(pattern, text):
        alt_text = match.group(1)
        url = match.group(2)
        found_items.append(url)
        print(f"Found alt text: {alt_text}, URL: {url}")

    # 使用re.sub进行替换，将所有匹配项替换为“图片”
    result = re.sub(pattern, '图片', text)

    return result, found_items

def setup_logging():
    try:
        # 获取当前执行文件的绝对路径
        if getattr(sys, 'frozen', False):
            # 如果是打包成一个exe，sys.executable将是那个exe的路径
            executable_path = sys.executable
        else:
            # 如果是作为脚本运行，__file__会指向该脚本的位置
            executable_path = __file__

        # 打印当前工作目录和可执行文件路径用于调试
        print(f"Current Working Directory: {os.getcwd()}")
        print(f"Executable Path: {executable_path}")

        base_dir = os.path.dirname(os.path.abspath(executable_path))
        log_file_path = os.path.join(base_dir, 'cs_app.log')  # 日志文件放在脚本所在目录

        print(f"Attempting to write log to: {log_file_path}")  # 打印日志文件路径

        # 获取根记录器
        logger = logging.getLogger()
        logger.setLevel(logging.ERROR)  # 设置最低日志级别为DEBUG

        # 创建文件处理器并设置格式
        file_handler = logging.FileHandler(log_file_path, mode='a', encoding='utf-8')
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)

        # 将处理器添加到根记录器
        logger.addHandler(file_handler)

        logging.info("日志系统已初始化")
        print("日志配置完成")

    except Exception as e:
        print(f"无法设置日志配置: {e}")