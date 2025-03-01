import asyncio  # noqa: D100
import json

from .actions.action import Action
from .llm import LLM
from .utils.logs import _logger

SYSTEM_MESSAGE = """
# Role
你是智能家居系统中的工程师，你需要将智能家居系统中多个智能体分别完成子任务后返回的信息进行整合，并输出最终的反馈信息。

# Input
Response list: 一个由多个智能体返回的信息组成的列表，列表中每个元素是对应的子任务完成时，该执行该任务的智能体返回的信息。

# Output
你需要返回一个JSON字符串，包含以下字段：
{
    "content": <content>,
}
其中content是一个字符串，表示最终的反馈信息。

# Examples
Example1:
Input: [{"content": "好的，已经为您将空调开到制热模式，27度。"}, {"content": "好的，已经为您设置好，客厅的灯将在晚上7点自动打开。"}]
Output: {"content": "好的，已经为您将空调开到制热模式，27度。同时，已经为您设置好，客厅的灯将在晚上7点自动打开。"}

# Important Notes
1. 你需要对返回信息进行有逻辑的整合，而不是简单的拼接。你不能擅自删去任何信息。你要努力确保返回后的信息的完整性和逻辑性，同时尽量不要让用户意识到其请求是由多个智能体完成的。
2. 单个智能体的返回信息中可能包含“好的，我已经为您”等开头的通用信息，你需要将这些通用信息去除，只保留具体的操作信息。最后，只在最终的反馈信息中添加一次“好的”等表示已经完成的通用信息即可。
"""

USER_MESSAGE = """user_request: {user_request}"""


class Synthesizer(Action):
    def __init__(self, name="Synthesizer", context=None):
        super().__init__(name, context)
        self.llm = LLM()

    async def run(self, user_request: str) -> list:
        self.llm.add_system_msg(SYSTEM_MESSAGE)
        self.llm.add_user_msg(USER_MESSAGE.format(user_request=user_request))
        loop = asyncio.get_running_loop()
        rsp = await loop.run_in_executor(
            None, self.llm.chat_completion_text_v1, self.llm.history
        )
        _logger.info(f"Synthesizer response: {rsp}")
        self.llm.reset()

        rsp_json = self.parse_output(rsp)
        print("Synthesizer.run():\n" + rsp)
        return rsp_json["content"]

    def parse_output(self, output: str) -> dict:
        """将LLM的输出转换为JSON字符串."""
        # TODO error handling
        if output.startswith("```json"):
            output = output[7:]
            output = output[:-3]
            return json.loads(output.strip())
        if output.startswith("```"):
            output = output[3:]
            output = output[:-3]
            return json.loads(output.strip())
        output = output.replace("}{", "},{")
        return json.loads(output.strip())

    def reset(self):
        self.llm.reset()
        _logger.info(f"{self.name} reset.")
