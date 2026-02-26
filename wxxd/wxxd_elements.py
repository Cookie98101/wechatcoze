class Message:
    def __init__(self,type,content,who='') -> None:
        self.type = type
        self.content = content
        self.who = who

    def __str__(self):
        return self.content

    def __repr__(self):
        return f"{{'type': '{self.type}', 'content': '{self.content}', 'who': '{self.who}'}}"

    def __iter__(self):
        # 返回一个迭代器对象
        return iter({'type': '{self.type}', 'content': '{self.content}', 'who': '{self.who}'})