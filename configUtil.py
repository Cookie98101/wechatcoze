import os
import sys
from configparser import ConfigParser

def get_config_path(config_filename="config.ini"):
    if getattr(sys, 'frozen', False):
        # 打包后的环境，使用.exe所在的目录
        basedir = os.path.dirname(sys.executable)
    else:
        # 开发环境，使用.py文件所在的目录
        basedir = os.path.dirname(os.path.abspath(__file__))

    return os.path.join(basedir, config_filename)

def read_config():
    config_path = get_config_path()
    config = ConfigParser()

    print(f"Attempting to read configuration from: {config_path}")

    # 如果配置文件不存在，则创建一个默认配置文件
    if not os.path.exists(config_path):
        print("Configuration file not found. Creating default configuration...")
        create_default_config(config_path)
    else:
        print("Configuration file found.")

    config.read(config_path)
    return config

def set_config_option(section, option, value):
    """
    设置配置文件中的某个选项值。

    :param section: 配置文件中的部分名称（如 'DEFAULT'）
    :param option: 要设置的选项名（如 'transfer_name'）
    :param value: 选项的新值
    """
    config_path = get_config_path()
    config = ConfigParser()

    # 检查配置文件是否存在，并读取现有配置
    if os.path.exists(config_path):
        config.read(config_path)
    else:
        print("Configuration file not found. Please ensure the configuration file exists before setting options.")
        return False

    # 如果不是'DEFAULT'部分且该部分不存在，则添加
    if section != 'DEFAULT' and not config.has_section(section):
        config.add_section(section)

    # 更新或设置选项值
    config.set(section, option, value)

    try:
        with open(config_path, 'w') as configfile:
            config.write(configfile)
        print(f"Updated {option} in section [{section}] to: {value}")
        return True
    except Exception as e:
        print(f"Failed to update configuration: {e}")
        return False

def create_default_config(config_path):
    config = ConfigParser()
    config['DEFAULT'] = {
        'bot_id': '',
        'token': '',
        'bailian_key' : '',
        'bailian_app_id' : '',
        'fastgpt_url':'',
        'fastgpt_token':'',
        'chose_type' : 0,
        'transfer_name':'',
        'transfer_keyword':''
    }
    try:
        with open(config_path, 'w') as configfile:
            config.write(configfile)
        print(f"Default configuration written to: {config_path}")
    except Exception as e:
        print(f"Failed to write default configuration: {e}")

if __name__ == '__main__':
    try:
        config = read_config()
        # 注意：这里尝试访问的配置项需要存在于配置文件中
        print("Language:", config.get('DEFAULT', 'language', fallback='Not Set'))
        print("Theme:", config.get('DEFAULT', 'theme', fallback='Not Set'))
    except Exception as e:
        print(f"An error occurred: {e}")