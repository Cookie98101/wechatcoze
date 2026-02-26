import shelve
import time

# 使用shelve进行简单的键值存储
db_path = 'conversation_ids.db'

def get_conversation_id(user_id, ttl_seconds=None):
    """从存储中获取conversation_id，支持过期时间"""
    with shelve.open(db_path) as db:
        entry = db.get(user_id)
        if entry is None:
            return None
        if isinstance(entry, dict):
            conversation_id = entry.get("conversation_id")
            ts = entry.get("ts")
            if ttl_seconds and ts and time.time() - ts > ttl_seconds:
                del db[user_id]
                return None
            return conversation_id
        return entry

def save_conversation_id(user_id, conversation_id):
    """将conversation_id保存到存储"""
    with shelve.open(db_path) as db:
        db[user_id] = {"conversation_id": conversation_id, "ts": time.time()}

def delete_conversation_id(user_id):
    """从存储中删除conversation_id"""
    with shelve.open(db_path) as db:
        if user_id in db:
            del db[user_id]
            print(f"Conversation ID for user {user_id} deleted successfully.")
        else:
            print(f"No conversation ID found for user {user_id}.")
