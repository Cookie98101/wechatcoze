from PyQt5.QtSql import QSqlDatabase, QSqlQuery
import  json
class DatabaseManager:
    def __init__(self, db_path="app_database.db"):
        self.db_path = db_path

    def _open(self):
        self.db = QSqlDatabase.addDatabase("QSQLITE")
        self.db.setDatabaseName(self.db_path)
        if not self.db.open():
            raise Exception("无法打开数据库")

    def _close(self):
        if self.db.isOpen():
            self.db.close()

    def create_tables(self):
        self._open()
        query = QSqlQuery(self.db)

        # 创建 tokens 表
        query.exec_(
            """
            CREATE TABLE IF NOT EXISTS tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token TEXT NOT NULL,
                bot_id TEXT NOT NULL,
                other TEXT,
                type_id INTEGER,
                type_name TEXT
            )
            """
        )

        # 创建 platforms 表
        '''
                platform_name 拼多多,
                platform_type 拼多多类型,
                alias_name 别名,
                transfrom_name 转交人,
                transfrom_keywork 转交关键词,
                designated_person 指定回复人,
                connect_type_id 对接的是扣子还是fastgpt的类型id,
                token_id token的id ,
                token token的值,
                bot_id bot_id/appid的值,
                refresh_interval INTEGER
        '''
        query.exec_(
            """
            CREATE TABLE IF NOT EXISTS platforms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform_name TEXT,
                platform_type TEXT,
                alias_name TEXT,
                transfrom_name TEXT,
                transfrom_keywork TEXT,
                designated_person TEXT,
                connect_type_id INTEGER,
                token_id INTEGER ,
                token TEXT,
                bot_id TEXT,
                refresh_interval INTEGER
            )
            """
        )
        # 定义需要添加的字段（字段名, 数据类型, 是否为布尔类型）
        fields_to_add = [
            ("checked_greetings", "INTEGER"),
            ("greetings", "TEXT"),
            ("checked_pwd_login", "INTEGER"),
            ("username", "TEXT"),
            ("pwd", "TEXT"),
            ("checked_feishu", "INTEGER"),
            ("feishu_url", "TEXT"),
        ]
        # 检查并添加缺失的字段
        for field_name, field_type in fields_to_add:
            # 检查字段是否已存在
            query.exec_(f"PRAGMA table_info(platforms);")
            exists = False
            while query.next():
                if query.value(1) == field_name:  # 1 表示字段名列
                    exists = True
                    break

            # 如果字段不存在，则添加
            if not exists:
                query.exec_(f"ALTER TABLE platforms ADD COLUMN {field_name} {field_type};")
        # query.exec_("PRAGMA table_info(platforms);")
        # while query.next():
        #     print(query.value(1))  # 输出所有字段名

        # 创建用户表
        query.exec_(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                password TEXT NOT NULL,
                random_value TEXT
            )
            """
        )
        self._close()

    def delete_user(self):
        self._open()
        query = QSqlQuery(self.db)
        query.prepare("DELETE FROM users")
        success = query.exec_()
        self._close()
        return success
        
    def insert_user(self, username, password):
        self._open()
        query = QSqlQuery(self.db)
        query.prepare("INSERT INTO users (username, password) VALUES (?, ?)")
        query.addBindValue(username)
        query.addBindValue(password)
        success = query.exec_()
        self._close()
        return success

    def get_first_user(self):
        self._open()
        query = QSqlQuery("SELECT * FROM users LIMIT 1", self.db)
        user_data = None
        if query.exec_():
            if query.next():
                record = query.record()
                user_data = {}
                for i in range(record.count()):
                    column_name = record.fieldName(i)
                    value = record.value(i)
                    user_data[column_name] = value
        else:
            print("查询用户失败:", query.lastError().text())
        self._close()
        return user_data

    # --- tokens 表操作 ---
    def insert_token(self, token, bot_id, other=None,type_id=None,type_name=None):
        self._open()
        query = QSqlQuery(self.db)
        query.prepare("INSERT INTO tokens (token, bot_id, other,type_id, type_name) VALUES (?, ?, ?, ?,?)")
        query.addBindValue(token)
        query.addBindValue(bot_id)
        query.addBindValue(other if other else "")
        query.addBindValue(type_id)
        query.addBindValue(type_name if type_name else "")
        success = query.exec_()
        self._close()
        return success

    def delete_token(self, token_id):
        self._open()
        query = QSqlQuery(self.db)
        query.prepare("DELETE FROM tokens WHERE id = ?")
        query.addBindValue(token_id)
        success = query.exec_()
        self._close()
        return success

    def update_token(self, token_id, **kwargs):
        set_clause = []
        params = []
        for key in ['token', 'bot_id', 'other', 'type_id','type_name']:
            if key in kwargs:
                set_clause.append(f"{key} = ?")
                params.append(kwargs[key])

        if not set_clause:
            return False  # 没有需要更新的字段

        query_str = f"UPDATE tokens SET {', '.join(set_clause)} WHERE id = ?"
        params.append(token_id)

        self._open()
        query = QSqlQuery(self.db)
        query.prepare(query_str)
        for p in params:
            query.addBindValue(p)
        success = query.exec_()
        self._close()
        return success

    def get_tokens(self):
        self._open()
        query = QSqlQuery("SELECT * FROM tokens", self.db)
        data = []
        if query.exec_():
            while query.next():
                record = query.record()
                row = {}
                for i in range(record.count()):
                    column_name = record.fieldName(i)
                    value = record.value(i)
                    row[column_name] = value
                data.append(row)
        else:
            print("查询失败:", query.lastError().text())
        self._close()
        return data

    # --- platforms 表操作 ---
    def insert_platform(self, platform_name, platform_type=None,alias_name=None, transfrom_name=None,
                        transfrom_keywork=None, designated_person=None,connect_type_id =None,token_id=None,
                        token=None, bot_id=None,refresh_interval=None,greetings=None,username=None,pwd=None,feishu_url=None,
                        checked_greetings=0,checked_pwd_login=0,checked_feishu=0):
        self._open()
        query = QSqlQuery(self.db)
        query.prepare(
            "INSERT INTO platforms (platform_name, platform_type,alias_name, transfrom_name, transfrom_keywork, "
            "designated_person,connect_type_id,token_id,token,bot_id, refresh_interval,greetings,username,pwd,checked_greetings,checked_pwd_login,checked_feishu,feishu_url) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,?, ?, ?, ?, ?, ?, ?)"
        )
        query.addBindValue(platform_name)
        query.addBindValue(platform_type)
        query.addBindValue(alias_name)
        query.addBindValue(transfrom_name)
        query.addBindValue(transfrom_keywork)
        query.addBindValue(designated_person)
        query.addBindValue(connect_type_id)
        query.addBindValue(token_id)
        query.addBindValue(token)
        query.addBindValue(bot_id)
        query.addBindValue(refresh_interval)
        query.addBindValue(greetings)
        query.addBindValue(username)
        query.addBindValue(pwd)
        query.addBindValue(checked_greetings)
        query.addBindValue(checked_pwd_login)
        query.addBindValue(checked_feishu)
        query.addBindValue(feishu_url)
        success = query.exec_()
        if not success:
            # 获取并返回错误信息
            error = query.lastError()
            error_message = f"插入失败: {error.text()} (SQL: {query.lastQuery()})"
            self._close()
            raise Exception(error_message)  # 或者返回错误信息而不是抛出异常
        self._close()
        return success

    def delete_platform(self, platform_id):
        self._open()
        query = QSqlQuery(self.db)
        query.prepare("DELETE FROM platforms WHERE id = ?")
        query.addBindValue(platform_id)
        success = query.exec_()
        self._close()
        return success

    def update_platform(self, platform_id, **kwargs):
        set_clause = []
        params = []
        for key in [
            'platform_name', 'platform_type','alias_name', 'transfrom_name',
            'transfrom_keywork', 'designated_person','connect_type_id','token_id','token','bot_id',
            'refresh_interval','greetings','username','pwd','checked_greetings','checked_pwd_login',
            'checked_feishu','feishu_url'
        ]:
            if key in kwargs:
                set_clause.append(f"{key} = ?")
                params.append(kwargs[key])

        if not set_clause:
            return False

        query_str = f"UPDATE platforms SET {', '.join(set_clause)} WHERE id = ?"
        params.append(platform_id)

        self._open()
        query = QSqlQuery(self.db)
        query.prepare(query_str)
        for p in params:
            query.addBindValue(p)
        success = query.exec_()
        self._close()
        return success

    def get_platforms(self):
        self._open()
        query = QSqlQuery("SELECT * FROM platforms", self.db)
        data = []
        if query.exec_():
            while query.next():
                record = query.record()
                row = {}
                for i in range(record.count()):
                    column_name = record.fieldName(i)
                    value = record.value(i)
                    row[column_name] = value
                data.append(row)
        else:
            print("查询失败:", query.lastError().text())

        self._close()
        return data

    def get_platform_by_id(self, platform_id):
        """
        根据平台 ID 查找单个平台的信息。

        :param platform_id: 平台的唯一标识符 (id)
        :return: 包含平台信息的字典，如果未找到则返回 None
        """
        self._open()
        query = QSqlQuery(self.db)
        query.prepare("SELECT * FROM platforms WHERE id = ?")
        query.addBindValue(platform_id)

        if not query.exec_():
            print("查询失败:", query.lastError().text())
            self._close()
            return None

        platform_data = None
        if query.next():  # 如果有结果
            record = query.record()
            platform_data = {}
            for i in range(record.count()):
                column_name = record.fieldName(i)
                value = record.value(i)
                platform_data[column_name] = value

        self._close()
        return platform_data

