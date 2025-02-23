import asyncio
import json
import re

from ..actions.action import Action
from ..configs import CONFIG
from ..llm import LLM
from ..message import Message
from ..tool_agent import time_tool_agent, weather_tool_agent, map_tool_agent
from ..translator import Translator
from ..utils.logs import _logger

SYSTEM_MESSAGE = """
You are DeviceControler, your role is to interpret user requests into device commands.

# Command Format
Commands must follow this format:
id.service.property = <value>
Device hierarchy must be respected (e.g., speaker is a sub-service of television, so volume must be under 3.television.speaker, not 3.television).
Specially, if you want to modify the airconditioner target temperature, you should generate command with content: id.air_conditioner.target_temperature = <value>

# Input
1. User Request: The user's command or query.
2. Device List: Information on devices, including ID, type, area, and available services. Each service has specific properties.
3. Tool List: Available tools with their functions and required arguments.
4. Sensor Data: The current data from all sensors attached to indoor devices. Each set of sensor information has an ID that matches the device ID to which the sensors belong.

# Solution
1. Generate commands based on the user's request only when you have sufficient information to judge all the premises.
2. If insufficient information available, take one of the following actions:
    1.Ask the user for clarification.
    2.Call a tool for assistance.
3. You can only generate commands for user requests that need to be executed immediately. If you find that device control is not to be executed immediately (e.g., the user's request involves waiting for a device's status to change before controlling another device or waiting for a period of time before controlling a device), you need to seek help from other agents. In this case, you should choose the SeekHelp Action type.

# Action Types
Finish: Execute the command and confirm with the user.
AskUser: Request more information.
CallTools: Use an external tool for assistance.
SeekHelp: Request help from other agents only when the user's request cannot be executed immediately.

# Output Format(In JSON type)
AskUser :
{"Action_type": "AskUser", "Thought": "Reason for requesting input", "Say_to_user": "Message in user's language"}
CallTools:
{"Action_type": "CallTools", "Thought": "Reason for calling the tool", "Arguments": "Arguments required", "Target_tool": "Exact tool name"}
Finish:
{"Action_type": "Finish", "Thought": "Reason for action", "Commands": ["Generated commands"], "Say_to_user": "Response in user's language"}
SeekHelp:
{"Action_type": "SeekHelp", "Thought": "Reason for seeking help"}

# Example
Example 1:
User: 我现在开车从学校出发，如果晚上九点五十到不了家而且今天气温比较低的话，先帮我打开卧室的空调。
DeviceControler: {\n    "Action_type": "CallTools",\n    "Thought": "The user requested the air conditioner to be turned on at 9:50 PM if they are not home and it\'s cold outside. First, I need to determine if the user will be late arriving home at that time.",\n    "Arguments": "["school", "home", "driving"]",\n    "Target_tool": "PathPlanning"\n}
Observation: 从用户的家到目的地驾车所需时间为：26.35分钟
DeviceControler: {\n    "Action_type": "CallTools",\n    "Thought": "The user has previously requested that if they are not home by 9:50 PM and it is cold outside, the bedroom air conditioner should be turned on. Since the user\'s travel time from school to home is about 26.35 minutes, I need to calculate the actual time of arrival based on their departure time and compare it with 9:50 PM. I also need to check the weather conditions at the user\'s home to determine if it is indeed cold.",\n    "Arguments": "",\n    "Target_tool": "Time"\n}
Observation: 当前时间是：2025-01-31 21:47:41
DeviceControler: {\n    "Action_type": "CallTools",\n    "Thought": "To determine if it is cold outside, I need to call the WeatherInformation tool to get the current temperature at the user\'s home location.",\n    "Arguments": "",\n    "Target_tool": "WeatherInformation"\n}
Observation: 用户家所在区域的气象信息是<省略的具体气象信息>
DeviceControler: All the conditions have been met, issue the command and notify the user.

Example 2:
User: 十五分钟后关闭电视。
DeviceControler: {\n    "Action_type": "SeekHelp",\n    "Thought": "The user requested the TV to be turned off in fifteen minutes. Since the command is not to be executed immediately, I need to seek help from other agents.",\n}

# Important Notes
1. Only one action per response. If multiple inputs are needed, request them incrementally.
2. Only modify properties with 'write' access. Inform the user if a property is read-only.
3. Carefully analyze every premise in the user's request and ensure that all premises are sufficiently supported by evidence before issuing a command. Never assume any information.
4. Always call the tool Time if you want to check the current time.
5. Sensor data intelligently reflects indoor environmental data but cannot represent weather conditions.
"""

USER_MESSAGE = """
User request: {user_request}
Device list: {device_list}
Tool list: {tool_list}
Sensor data: {sensor_data}
"""


class ControlDevice(Action):
    def __init__(self, name="DeviceControler", context=None):
        super().__init__(name, context)
        self.llm = LLM()
        # TODO Agent不能准确识别需要调用时间工具的情况，考虑将时间直接输入
        self.tool_agent = [weather_tool_agent(), time_tool_agent(), map_tool_agent()]
        self.tool_list = self.tool_agent_to_tool_list()
        self.tool_dict = self.tool_agent_to_tool_dict()

    def parse_output(self, output: str) -> dict:
        """将LLM的输出转换为JSON字符串."""
        match = re.search(r"```json\s*(.*?)\s*```", output, re.DOTALL)
        if match:
            return json.loads(match.group(1).strip())
        return json.loads(output.strip())

    async def run(self, history_msg: list[Message], user_input: Message) -> Message:
        _logger.info(f"DeviceControler run: {user_input}")
        user_request = user_input.content
        self.llm.add_system_msg(SYSTEM_MESSAGE)
        all_context = CONFIG.hass_data["all_context"]
        sensor_data = CONFIG.hass_data["all_sensor_data"]
        self.llm.add_user_msg(
            USER_MESSAGE.format(
                user_request=user_request,
                device_list=all_context,
                tool_list=self.tool_list,
                sensor_data=sensor_data,
            )
        )
        loop = asyncio.get_running_loop()
        rsp = await loop.run_in_executor(
            None, self.llm.chat_completion_text_v1, self.llm.history
        )
        _logger.info(f"ControlDevice response: {rsp}")
        print(rsp)
        rsp_json = self.parse_output(rsp)
        self.llm.add_assistant_msg(rsp)  # llm的回复加入记忆
        _logger.info(f"DeviceControler rsp: {rsp}")

        if rsp_json["Action_type"] == "Finish":
            # 结束任务，执行命令，返回信息发给用户（发布到环境中）
            self.llm.reset()
            say_to_user = rsp_json["Say_to_user"]
            if "Commands" in rsp_json:
                commands = rsp_json["Commands"]
                TRANSLATOR = Translator()
                for command in commands:
                    await TRANSLATOR.run_single_command(command)
            return Message(
                role=self.name,
                content=say_to_user,
                sent_from="DeviceControler",
                send_to=["User"],
                cause_by="Finish",
            )

        if rsp_json["Action_type"] == "AskUser":
            # 询问用户，返回信息发给用户（发布到环境中）
            say_to_user = rsp_json["Say_to_user"]
            return Message(
                role=self.name,
                content=say_to_user,
                sent_from="DeviceControler",
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
                        send_to=["DeviceControler"],
                        cause_by="UserResponse",
                        attachment=Message(
                            role="DeviceControler",
                            content=rsp,
                            sent_from="DeviceControler",
                            send_to=["Tool"],
                            cause_by="AskUser",
                            attachment=None,
                        ),
                    )
            # 若没有找到对应的工具：返回工具不可用的信息
            return Message(
                role="Tool",
                content=f"Observation: no available tool named {target_tool}",
                sent_from="SYSTEM",
                send_to=["DeviceControler"],
                cause_by="SYSTEM",
            )

        if rsp_json["Action_type"] == "SeekHelp":
            # 用户需求不是可以立即执行的命令，请求帮助，将信息发给TAPGenerator尝试执行
            return Message(
                role=self.name,
                content=user_request,
                sent_from="DeviceControler",
                send_to=["TAPGenerator"],
                cause_by="UserInput",
                attachment=Message(
                    role=self.name,
                    content="TAP only run once",
                    sent_from="DeviceControler",
                    send_to=["TAPGenerator"],
                    cause_by="SYSTEM",
                ),
            )

        # 处理不正确的Action_type，让LLM重新生成回复
        return Message(
            role="SYSTEM",
            content="Incorrect action type, please generate correct response.",
            sent_from="SYSTEM",
            send_to=["DeviceControler"],
            cause_by="SYSTEM",
        )

    def reset(self):
        self.llm.reset()
        _logger.info(f"{self.name} reset.")
