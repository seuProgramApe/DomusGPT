from .llm import LLM
import json
import aiohttp
import ast
from abc import ABC
from .context_assistant import get_all_states, find_entity_by_entity_id
from datetime import datetime, timedelta
import json


class tool_agent(ABC):
    profile: str
    function: str
    argument: str
    llm = LLM()
    role_prompt: str

    def __init__(self):
        pass

    @classmethod
    def run(self, request: str):
        pass

    def parse_output(self, output: str) -> dict:
        if output.startswith("```json"):
            output = output[7:]
            output = output[:-3]
            return json.loads(output.strip())
        if output.startswith("```"):
            output = output[3:]
            output = output[:-3]
            return json.loads(output.strip())
        return json.loads(output.strip())


class weather_tool_agent(tool_agent):
    def __init__(self):
        self.profile = "WeatherInformation"
        self.function = "Return the weather conditions/climate information including temperature, humidity, precipitation, sunrise and sunset times, wind speed, etc."
        self.argument = ""

    async def run(self, request):
        await get_all_states()  # 刷新states.json
        zone_home = find_entity_by_entity_id("zone.home")
        la = zone_home["attributes"]["latitude"]
        laf = f"{la:.2f}"
        lo = zone_home["attributes"]["longitude"]
        lof = f"{lo:.2f}"
        winfo = await self.fetch_weather(
            laf, lof
        )  # 从配置信息中获取用户家所在位置的经纬度坐标
        return "用户家所在区域的气象信息是\n" + str(winfo)

    async def fetch_weather(self, latitude=31.2304, longitude=118.7966):
        """获取给定经纬度地区的天气信息，仅返回 result 部分，并将 key 翻译为中文."""
        api_key = "pyO14zYLps7PLRpr"
        url = (
            f"https://api.caiyunapp.com/v2.6/{api_key}/{longitude},{latitude}/realtime"
        )

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    if "result" in data:
                        return self._translate_keys(data["result"])
                    return {"错误": "API返回数据不包含 result 部分"}
                return {"错误": f"无法获取数据，状态码 {response.status}"}

    def _translate_keys(self, result):
        """翻译 result 字段的 key."""
        translation_map = {
            "realtime": "实时天气",
            "status": "状态",
            "temperature": "气温（℃）",
            "humidity": "相对湿度（%）",
            "cloudrate": "总云量（0.0-1.0）",
            "skycon": "天气现象",
            "visibility": "能见度（公里）",
            "dswrf": "向下短波辐射通量（W/m²）",
            "wind": "风速与风向",
            "speed": "风速（m/s）",
            "direction": "风向（°）",
            "pressure": "气压（Pa）",
            "apparent_temperature": "体感温度（℃）",
            "precipitation": "降水情况",
            "local": "本地降水",
            "intensity": "降水强度（mm/h）",
            "nearest": "最近降水",
            "distance": "最近降水距离（m）",
            "air_quality": "空气质量",
            "pm25": "PM2.5 浓度（μg/m³）",
            "pm10": "PM10 浓度（μg/m³）",
            "o3": "臭氧浓度（μg/m³）",
            "so2": "二氧化硫浓度（μg/m³）",
            "no2": "二氧化氮浓度（μg/m³）",
            "co": "一氧化碳浓度（mg/m³）",
            "aqi": "空气质量指数",
            "chn": "空气质量指数（国标）",
            "usa": "美国 AQI",
            "description": "空气质量描述",
            "life_index": "生活指数",
            "ultraviolet": "紫外线指数",
            "index": "指数",
            "desc": "描述",
            "comfort": "舒适度",
            "primary": "主要天气类型",
        }

        def translate(d):
            if isinstance(d, dict):
                return {translation_map.get(k, k): translate(v) for k, v in d.items()}
            if isinstance(d, list):
                return [translate(i) for i in d]
            return d

        return translate(result)


class time_tool_agent(tool_agent):
    def __init__(self):
        self.profile = "Time"
        self.function = "Return the current date and time."
        self.argument = ""

    async def run(self, request):
        """运行time_tool_agent并返回时间信息."""
        now = datetime.now() + timedelta(hours=8)  # 正式发布时可能需要修改时区
        formatted_time = now.strftime("%Y-%m-%d %H:%M:%S")
        return "当前时间是：" + formatted_time


class map_tool_agent(tool_agent):
    def __init__(self):
        self.profile = "PathPlanning"
        self.function = "Return the travel time and the optimal route from the provided starting location to the provided destination using a given mode of transportation. Both the starting location and destination must be explicitly provided as parameters. The mode of transportation (such as driving, walking, or public transit) should also be specified."
        self.argument = "[<starting location>, <destination>, <mode of transportation>]"

    async def run(self, request):
        rsp = self.normalize_llm_output(request)
        start = rsp[0]
        dest = rsp[1]
        mode = rsp[2]
        if mode == "driving":
            return await self.fetch_traffic(start, dest, mode)
        return "Error: this mode of transportation is currently not available."

    async def fetch_traffic(self, start: str, dest: str, mode: str):
        """高德API获取路径规划(异步版本)."""
        api_key = "ba232242633f94c98b5d197e325ca699"
        origin_longitude = 118.927494
        origin_latitude = 32.093479  # 尚东花园北门
        dest_longitude = 118.756486
        dest_latitude = 32.077751  # 南师附中正门
        url = f"https://restapi.amap.com/v5/direction/driving?origin={origin_longitude},{origin_latitude}&destination={dest_longitude},{dest_latitude}&key={api_key}&show_fields=cost"

        async with aiohttp.ClientSession() as session:  # noqa: SIM117
            async with session.get(url) as response:
                if response.status == 200:
                    rsp_json = await response.json()
                    try:
                        paths = rsp_json["route"]["paths"]
                        time = paths[0]["cost"]["duration"]
                        optimal_route = []
                        for instruction in paths[0]["steps"]:
                            optimal_route.append(instruction["instruction"])
                        return f"根据当前的交通状况，从{start}到{dest}驾车所需时间为：{int(time) / 60}分钟。\n最优路径是{optimal_route!s}"
                    except (KeyError, IndexError):
                        return "Error: Invalid response format from API."
                return f"Error: Unable to fetch data, status code {response.status}"

    def normalize_llm_output(self, output: str):
        if isinstance(output, list):
            return output  # 如果已经是列表，直接返回
        if isinstance(output, str):
            try:
                return ast.literal_eval(output)  # 安全地解析字符串为 Python 对象
            except (ValueError, SyntaxError):
                pass
        return []  # 解析失败时返回空列表
