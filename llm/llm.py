from playwright.sync_api import sync_playwright
import time
import uuid

def main():
    # 获取 MAC 地址（整数形式）
    mac_int = uuid.getnode()

    # 转换为十六进制字符串
    mac_hex = hex(mac_int)[2:]  # 去掉 "0x" 前缀

    # 格式化为标准 MAC 地址格式
    mac_address = ":".join(mac_hex[i:i+2] for i in range(0, 12, 2))

    print("MAC 地址:", mac_address)
    # with sync_playwright() as p:
    #     browser = p.chromium.connect_over_cdp("http://localhost:9222")
    #     page = browser.contexts[0].new_page()
    #     page.goto("https://www.browserscan.net/")
    #     # 查找类名为 _ckhczt 的元素
    #     time.sleep(3)
    #     element = page.query_selector("span._ckhczt")
    #
    #     if element:
    #         # 获取元素的文本内容并打印
    #         text_content = element.text_content()
    #         print(f"Element content: {text_content}")
    #
    #         # 点击该元素
    #         element.click()
    #     # 业务逻辑...
    #     browser.close()

if __name__ == "__main__":
    main()