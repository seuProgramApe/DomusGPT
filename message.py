from pydantic import BaseModel
from typing import Optional


class Message(BaseModel):
    role: str
    content: str
    cause_by: str
    sent_from: str
    send_to: list  # 明确类型，send_to 是一个字符串列表
    attachment: Optional["Message"] = None  # 允许附加另一个 Message

    def __str__(self):
        return f"{self.content}"

    def to_dict(self):
        return {
            "role": self.role,
            "content": self.content,
            "cause_by": self.cause_by,
            "sent_from": self.sent_from,
            "send_to": self.send_to,
        }

    def to_Str(self):
        attachment_str = f" -> {self.attachment.to_Str()}" if self.attachment else ""
        return f"{self.content}{attachment_str}"  # 递归拼接
