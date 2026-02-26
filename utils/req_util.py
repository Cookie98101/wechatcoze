import requests
import json
from utils.db_utils import DatabaseManager   

base_http_api_url='http://test'

db_manager = DatabaseManager()

def login_user(username, password,is_insert=True):
        data = {'username': username, 'password': password}
        try:
            response = requests.post(f'{base_http_api_url}/login', json=data)
            if response.status_code == 200:
                if is_insert:
                    result1 = db_manager.delete_user()
                    result2 = db_manager.insert_user(username,password)  
                    if result1 and result2:  
                        return {'code':'success','message':json.loads(response.text)['user_id']}
                    else:
                        return {'code':'error','message':'用户插入错误'}
                else:
                    return {'code':'success','message':json.loads(response.text)['user_id']}
            else:
                return {'code':'error','message':json.loads(response.text)['message']}
        except requests.RequestException as e:
            return {'code':'error','message':'服务器错误'}  


def heart_beat(id,random_value):
        data = {'user_id': id, 'random_value': str(random_value)}
        try:
            response = requests.post(f'{base_http_api_url}/heartbeat', json=data)
            if response.status_code == 200:
               print(json.loads(response.text)['message'])
            else:
               print('服务器心跳其他状态码错误')
        except requests.RequestException as e:
            print('服务器错误')