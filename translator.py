# single Translator - hass init
# 1. translate the command to entity
# 2. translate the tap to automation yaml
from .utils.singleton import Singleton
from .utils.logs import _logger
from .utils.utils import append_file
import time
from .configs import CONFIG
from .context_assistant import find_entity_by_field_mac
import os
import requests


class Translator(metaclass=Singleton):
    def __init__(self, hass):
        self.hass = hass

    async def run_single_command(self, command_str: str):
        """用于将DeviceControler的命令翻译并执行."""
        print("执行命令：" + command_str)
        service_str = command_str.split("=")[0].strip()  # 等号左边的部分
        value_str = command_str.split("=")[1].strip()  # 等号右边的部分
        id_str, field_str = service_str.split(".", 1)

        # TODO 特殊情况：修改空调温度，目前只能修改mc2这台空调
        if field_str == "air_conditioner.target_temperature":
            print("执行一条修改空调温度的指令：" + command_str)
            await self.hass.services.async_call(
                "climate",
                "set_temperature",
                {
                    "entity_id": "climate.xiaomi_mc2_8cbf_air_conditioner",
                    "temperature": float(value_str),
                },
            )
            return

        id = int(id_str)

        miot_devices = CONFIG.hass_data["miot_devices"]

        mac_address = ""
        for device in miot_devices:
            if device.get("id", -1) == id:
                mac_address = device.get("mac_address", "")
                break

        parts = field_str.split(".")

        state = find_entity_by_field_mac(field_str, mac_address)

        if state is None and len(parts) == 3:
            field_str = f"{parts[1]}.{parts[2]}"  # 更新field_str再次搜索
            state = find_entity_by_field_mac(field_str, mac_address)
            if state is not None:  # 搜索成功
                parts = field_str.split(".")
            else:
                print(f"Can't find state with field_str {field_str}")
                return
        service_name = parts[0]
        property_name = ".".join(parts[1:])
        entity_id = state["entity_id"]

        for device in CONFIG.hass_data["all_context"]:
            if device.get("id", -1) == id:
                services = device.get("services", {})
                service = services[service_name]
                property = service[property_name]
                p_format = property["format"]

                if p_format == "bool":
                    value = value_str.lower() == "true"
                elif "int" in p_format:
                    value = int(value_str)
                elif "float" in p_format:
                    value = float(value_str)
                else:
                    value = value_str
                break

        _logger.debug("miot_set_property entity_id: {}".format(entity_id))
        _logger.debug("miot_set_property field_str: {}".format(field_str))
        _logger.debug("miot_set_property value: {}".format(value))

        service_data = {"entity_id": entity_id, "field": field_str, "value": value}

        await self.hass.services.async_call("xiaomi_miot", "set_property", service_data)

    async def _check_config(self):
        access_token = CONFIG.hass_data["access_token"]
        url = f"http://127.0.0.1:8123/api/config/core/check_config"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        try:

            def test():
                nonlocal url, headers
                response = requests.post(url=url, headers=headers)
                _logger.debug(f"response: {response}")
                if response.status_code == 200:
                    return response.json()["result"]
                else:
                    return f"failed_to_connect: {response.status_code}"

            response = await self.hass.async_add_executor_job(test)
            _logger.debug(f"response: {response}")
            return response
        except Exception as ex:
            _logger.error(f"Connection error was: {repr(ex)}")
            return "failed_to_connect"

    async def add_automation(self, new_automation: str):
        _logger.debug("add_automation")
        # config_path = "/config"
        # 李安：这里的config_path似乎有问题，我改为绝对路径，原先内容是上面这行
        config_path = "/workspaces/hahaha/config"
        # 以上是更改的地方-------------------------------------------------

        automation_file = os.path.join(config_path, "automations.yaml")
        # if there is only "[]" in automations.yaml, remove it first
        with open(automation_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        if len(lines) == 1 and lines[0] == "[]\n":
            with open(automation_file, "w", encoding="utf-8") as f:
                f.write("")

        # copy the automations.yaml for bak
        bak_file = os.path.join(config_path, "automations.yaml.bak")
        # print("已经创建bak文件")
        with open(automation_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        with open(bak_file, "w", encoding="utf-8") as f:
            f.writelines(lines)
            # print("已经写入bak文件")

        # Ensure the file starts with "---"
        if not lines:
            with open(automation_file, "w", encoding="utf-8") as f:
                f.write("---")
                f.writelines(lines)
        append_file(automation_file, new_automation)
        res_check = await self._check_config()
        if res_check == "valid":
            # print("配置文件检查通过")
            await self.hass.services.async_call("homeassistant", "reload_all")
            # print("重载配置文件完成")
        else:
            # replace the automations.yaml with the bak file
            _logger.error("invalid configuration, restore automations.yaml")
            with open(bak_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
            with open(automation_file, "w", encoding="utf-8") as f:
                f.writelines(lines)
                # print("已经写入automations.yaml文件")

    async def deploy_tap(self, runOnce: bool, user_input, TAP_json):
        _logger.debug("deploy_tap")
        miot_devices = CONFIG.hass_data["miot_devices"]
        triggers = TAP_json.get("trigger", "")
        actions = TAP_json.get("action", "")

        trigger_str = triggers
        action_str = actions
        _logger.info("trigger_str: {}".format(trigger_str))
        _logger.info("action_str: {}".format(action_str))

        # ---------------------------解析action_str----------------------------
        try:
            action_service_str = action_str.split("=")[0].strip()
            action_value_str = action_str.split("=")[1].strip()
            action_id_str, action_field_str = action_service_str.split(".", 1)
            action_service_name, *action_property_parts = action_field_str.split(".")
            action_property_name = ".".join(action_property_parts)
            action_id = int(action_id_str)
        except ValueError as e:
            print(f"解析错误: {e}")

        action_mac_address = ""
        for device in miot_devices:
            if device.get("id", -1) == action_id:
                action_mac_address = device.get("mac_address", "")
                break
        # print(action_field_str)
        # print(action_mac_address)
        action_entity = find_entity_by_field_mac(action_field_str, action_mac_address)
        if action_entity is None:  # 如果三段结构的field_str找不到，用后两段继续搜索
            parts = action_field_str.split(".")
            if len(parts) == 3:
                action_field_str = f"{parts[1]}.{parts[2]}"
                action_entity = find_entity_by_field_mac(
                    action_field_str, action_mac_address
                )
            if action_entity is None:  # 还是找不到，打印错误信息
                print(f"unable to find entity with field_str:{action_field_str}")
            else:  # 如果能找到，其他内容也要更新
                action_service_name, *action_property_parts = action_field_str.split(
                    "."
                )
                action_property_name = ".".join(action_property_parts)
        _logger.info("action_entity: {}".format(action_entity))

        action_entity_id = action_entity["entity_id"]

        for device in CONFIG.hass_data["all_context"]:
            if device.get("id", -1) == action_id:
                services = device.get("services", {})
                service = services[action_service_name]
                # print(service)
                property = service[action_property_name]
                p_format = property["format"]

                if p_format == "bool":
                    action_value = action_value_str.lower() == "true"
                elif "int" in p_format:
                    action_value = int(action_value_str)
                elif "float" in p_format:
                    action_value = float(action_value_str)
                else:
                    action_value = action_value_str
                break

        ops = ["==", ">", "<"]
        for op in ops:
            if op in trigger_str:
                break

        # ---------------------------解析trigger_str----------------------------
        trigger_service_str = trigger_str.split(op)[0].strip()  # trigger对应的服务
        trigger_value_str = trigger_str.split(op)[1].strip()  # trigger对应的值

        # 检查自动化是否与时间相关
        time_triggers = ["Date", "Time", "Time & Date"]
        time_related = False
        if trigger_service_str in time_triggers:
            time_related = True

        # 处理并非以时间为trigger的自动化
        if not time_related:
            try:
                trigger_id_str, trigger_field_str = trigger_service_str.split(".", 1)
                trigger_service_name, *trigger_property_parts = trigger_field_str.split(
                    "."
                )
                trigger_property_name = ".".join(trigger_property_parts)
                trigger_id = int(trigger_id_str)
            except ValueError as e:
                print(f"解析错误: {e}")

            if trigger_id == -1:
                pass
            else:
                trigger_mac_address = ""
                for device in miot_devices:
                    if device.get("id", -1) == trigger_id:
                        trigger_mac_address = device.get("mac_address", "")
                        break
                if trigger_field_str == "illumination_sensor.illumination":
                    trigger_field_str = "illumination-2-1"
                trigger_entity = find_entity_by_field_mac(
                    trigger_field_str, trigger_mac_address
                )
                if (
                    trigger_entity is None
                ):  # 如果三段形式的field_str找不到，用后两段再次尝试搜索
                    parts = trigger_field_str.split(".")
                    if len(parts) == 3:
                        trigger_field_str = f"{parts[1]}.{parts[2]}"
                        trigger_entity = find_entity_by_field_mac(
                            trigger_field_str, trigger_mac_address
                        )
                    if trigger_entity is None:  # 如果还是找不到，打印错误信息
                        print(f"unable to find entity: {trigger_field_str}")
                    else:  # 如果能找到，其他部分也要更新
                        trigger_service_name, *trigger_property_parts = (
                            trigger_field_str.split(".")
                        )
                        trigger_property_name = ".".join(trigger_property_parts)
                _logger.info("trigger_entity: {}".format(trigger_entity))
                trigger_entity_id = trigger_entity["entity_id"]
                for device in CONFIG.hass_data["all_context"]:
                    if device.get("id", -1) == trigger_id:
                        services = device.get("services", {})
                        service = services[trigger_service_name]
                        property = service[trigger_property_name]
                        p_format = property["format"]

                        if p_format == "bool":
                            bool_value = trigger_value_str.lower() == "true"
                            if bool_value:
                                trigger_value = 1
                            else:
                                trigger_value = 0
                        elif "int" in p_format or "float" in p_format:
                            trigger_value = int(trigger_value_str)
                        else:
                            trigger_value = trigger_value_str
                        break

        # 生成自动化中的trigger部分
        if op == "==":
            # trigger与时间无关
            if not time_related:
                trigger_yaml = f"""trigger: numeric_state
      entity_id: {trigger_entity_id}
      attribute: {trigger_field_str}
      above: {trigger_value - 1}
      below: {trigger_value + 1}"""

            # trigger与时间相关
            else:
                if trigger_service_str == "Date":
                    trigger_entity_id = "sensor.date"
                elif trigger_service_str == "Time":
                    trigger_entity_id = "sensor.time"
                else:
                    trigger_entity_id = "sensor.time_date"
                trigger_yaml = f"""platform: state
      entity_id: {trigger_entity_id}
      to: '{trigger_value_str}'"""

        elif op == ">":
            trigger_yaml = f"""platform: numeric_state
      entity_id: {trigger_entity_id}
      attribute: {trigger_field_str}
      above: {trigger_value}"""

        elif op == "<":
            trigger_yaml = f"""- platform: numeric_state
      entity_id: {trigger_entity_id}
      attribute: {trigger_field_str}
      below: {trigger_value}"""

        timestamp = int(time.time() * 1000)
        # 只运行一次的自动化啊alias必须和id一致，便于后续关闭
        alias = user_input
        if runOnce:
            alias = timestamp

        new_automation = f"""
- id: '{timestamp}'
  alias: {alias}
  trigger:
      {trigger_yaml}
  action:
    - service: xiaomi_miot.set_property
      data:
        entity_id: {action_entity_id}
        field: {action_field_str}
        value: {action_value}"""

        run_once_part = f"""
    - service: automation.turn_off
      target:
        entity_id: automation.{timestamp}"""

        if runOnce:
            # 如果该自动化只希望运行一次，添加run_once部分
            new_automation += run_once_part
        _logger.info("new automation yaml: {}".format(new_automation))
        await self.add_automation(new_automation)
