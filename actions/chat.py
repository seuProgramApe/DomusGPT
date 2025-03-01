from ..actions.action import Action
from ..configs import CONFIG
from ..message import Message
from ..utils.logs import _logger
from ..llm import LLM
import json
from ..tool_agent import time_tool_agent, weather_tool_agent, map_tool_agent
import asyncio

SYSTEM_MESSAGE = """
# Role
你是智能家居系统DomusGPT中的一个智能体Chatbot， 你的任务是友善地解答用户提出的问题。
但当且仅当用户的问题是关于室内的环境数据（例如室内的各种传感器可以获取的数据）或其他环境数据（例如天气情况、交通情况）或其他百科知识（例如询问某种事物、某位名人的信息）时。

# Input
用户需求（User Request）
工具列表 （Tool list）：一个列表，记录了可用的工具，包括工具的名称（name）、功能（function）、必须的参数（arguments）
设备列表（Device list)：家中可用的设备信息
传感器数据（Data from sensors）：当前所有家中可用的设备上安装的传感器的数据。每组传感器信息都有一个与设备ID匹配的ID。

# Solution
针对用户提出的不同请求，你可以采取以下3种行动（Action_type）之一：
1. **Finish**：
当用户提出的问题清晰明确，并且基于你已有的知识或提供给你的传感器数据可以直接回答，你将回答用户的问题。或当用户的输入是无意义的内容（例如：简单的问候等），礼貌地回复。
2. **AskUser**
当用户提出的问题不够清晰明确，你不能准确理解**问题本身**，你将询问用户以获得更多问题细节，直到你能回答该问题。
3. **CallTools**
当基于你已有的知识或提供给你的传感器数据不足以回答用户的问题，你可以选择调用工具列表中的一个工具，观察工具的返回结果，并结合返回结果继续采取行动。

# 特别注意
1. 每一次行动，你只能**调用1种工具**，如果你需要多个工具的返回结果，你将分多次调用工具。
2. 当用户请求中包含多个问题时，你需要确保能够回答所有问题后，**一次性输出**所有问题的答案。
3. 当用户询问有关你的信息时，你需要站在整个智能家居系统的角度回答用户的问题，而不是站在你自己的角度回答。具体来说，你需要介绍自己是DomusGPT，是智能家居系统的控制核心。

# Output
你需要将结果通过一个JSON字符串输出。
1. 当Action_type是Finish，输出：
{
    "Action_type": "Finish",
    "Thought": <你输出此内容的推理过程>,
    "Say_to_user": <回复用户的内容，必须**和用户输入为同一种语言**>,
}

2. 当Action_type是AskUser，输出：
{
    "Action_type": "AskUser",
    "Thought": <你输出此内容的推理过程>,
    "Say_to_user": <回复用户的内容，必须**和用户输入为同一种语言**>,
}

3. 当Action_type是CallTools，输出：
{
    "Action_type": "CallTools",
    "Thought": <你输出此内容的推理过程>,
    "Arguments": <输入工具的参数>,
    "Target_tool": <准确的工具名称>,
}

# Example:
Example1:
User Input: 请告诉我今天的天气状况？
tool list:[{"name": "WeatherInformation", "function": "提供用户家附近的天气信息/气象数据", arguments:[]}]
Chatbot:
{
    "Action_type": "CallTools",
    "Thought": "用户需要获取今天的天气信息，我可以通过调用WeatherInformation这个工具来获得天气信息。",
    "Arguments": [],
    "Target_tool": "WeatherInformation",
}
Observation: “用户家所在区域今日的气象信息是：<省略具体的气象信息>”
{
    "Action_type": "Finish",
    "Thought": "结合工具的返回信息，我已经获得了今日的天气信息，我可以回答用户提出的问题",
    "Say_to_user": "今日的天气信息是：<省略具体的气象信息>",
}

Example2:
User Input: Introduce yourself.
Chatbot:
{
    "Action_type": "Finish",
    "Thought": "用户询问我自己的信息，我需要站在整个智能家居系统DomusGPT的角度回答用户的问题。",
    "Say_to_user": "Hello! I am DomusGPT, your smart home assistant. I am designed to help you manage and control various devices in your home, from lighting and temperature to security sensors. I can provide real-time data from these devices, execute your commands to control them, and even fetch external information like weather or traffic details when needed. My goal is to make your home management effortless and intuitive.",
}

# 请注意：你的回答必须和用户输入（User request）是同一种语言，例如：中文、英文等。
"""

USER_MESSAGE = """
User request: {user_request}
Tool list: {tool_list}
Device list: {device_list}
Data from sensors: {sensor_data}
"""

TOOL_MESSAGE = """
Tool return information: {tool_return}
"""


class Chat(Action):
    def __init__(self, name="Chatbot", context=None):
        super().__init__(name, context)
        self.llm = LLM()
        self.tool_agent = [weather_tool_agent(), time_tool_agent(), map_tool_agent()]
        self.tool_list = self.tool_agent_to_tool_list()
        self.tool_dict = self.tool_agent_to_tool_dict()

    def parse_output(self, output: str) -> dict:
        try:
            # 如果输出以 "```json" 或 "```" 开头，移除这些标记
            if output.startswith("```json"):
                output = output[7:]
                output = output[:-3]
                return json.loads(output.strip())
            elif output.startswith("```"):
                output = output[3:]
                output = output[:-3]
                return json.loads(output.strip())
            else:
                # 尝试直接解析为JSON格式
                return json.loads(output.strip())
        except json.JSONDecodeError:
            # 如果输出不是合法的JSON格式，包装成默认的JSON结构
            return {
                "Say_to_user": output,  # LLM的原始输出
                "Action_type": "ContinueChat",  # 默认Action_type为ContinueChat
                "Thought": "User wants to continue chatting.",  # 默认Thought内容
            }

    async def run(self, history_msg: list[Message], user_input: Message) -> Message:
        _logger.info(f"Chat run: {user_input}")
        user_request = user_input.content

        if not self.llm.sysmsg_added:
            self.llm.add_system_msg(SYSTEM_MESSAGE)

        if user_input.role == "Tool":
            self.llm.add_user_msg(TOOL_MESSAGE.format(tool_return=user_request))
        else:
            self.llm.add_user_msg(
                USER_MESSAGE.format(
                    user_request=user_request,
                    device_list=CONFIG.hass_data["all_context"],
                    sensor_data=CONFIG.hass_data["all_sensor_data"],
                    tool_list=self.tool_list,
                )
            )

        loop = asyncio.get_running_loop()
        rsp = await loop.run_in_executor(
            None, self.llm.chat_completion_text_v1, self.llm.history
        )
        _logger.info(f"Chat response: {rsp}")
        print(rsp)
        rsp_json = self.parse_output(rsp)
        self.llm.add_assistant_msg(rsp)
        if rsp_json["Action_type"] == "Finish":
            # 结束任务，执行命令，返回信息发给用户（发布到环境中）
            self.llm.reset()
            say_to_user = rsp_json["Say_to_user"]
            return Message(
                role=self.name,
                content=say_to_user,
                sent_from="Chatbot",
                send_to=["User"],
                cause_by="Finish",
            )

        if rsp_json["Action_type"] == "AskUser":
            # 询问用户，返回信息发给用户（发布到环境中）
            say_to_user = rsp_json["Say_to_user"]
            return Message(
                role=self.name,
                content=say_to_user,
                sent_from="Chatbot",
                send_to=["User"],
                cause_by="AskUser",
            )

        if rsp_json["Action_type"] == "CallTools":
            # 调用工具，工具返回的信息作为观察（observation）发回给自己
            target_tool = rsp_json["Target_tool"]
            arguments = rsp_json["Arguments"]
            for tool in self.tool_list:
                if tool["name"] == target_tool:
                    # 调用tool
                    tool_rsp = await self.tool_dict[target_tool].run(arguments)
                    return Message(
                        role="Tool",
                        content="Observation:" + tool_rsp,
                        sent_from=target_tool,
                        send_to=["Chatbot"],
                        cause_by="UserResponse",
                    )
            return Message(
                role="Tool",
                content=f"Observation: no available tool named {target_tool}",
                sent_from="SYSTEM",
                send_to=["Chatbot"],
                cause_by="UserResponse",
            )
        return None

    def reset(self):
        self.llm.reset()
        _logger.info(f"{self.name} reset.")
