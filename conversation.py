from __future__ import annotations
from .utils.logs import _logger
import traceback
from typing import Literal
from homeassistant.components.conversation import (
    ConversationInput,
    ConversationResult,
    AbstractConversationAgent,
    ConversationEntity,
)
from homeassistant.components import assist_pipeline, conversation as ha_conversation
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import ulid
from .const import (
    DOMAIN,
    CONF_PROVIDER,
    PROVIDERS,
    DEFAULT_PROVIDER,
    WORK_PATH,
    DATA_PATH,
)
import sys

sys.path.append(WORK_PATH)
from .configs import CONFIG
from .context_assistant import (
    download_instance,
    get_miot_info,
    get_miot_devices,
    get_all_states,
    get_all_context,
    get_all_sensor_data,
)
from .utils.utils import delete_all_files_in_folder


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> bool:
    """Set up SmartHomeAgent Conversation from a config entry."""

    def create_agent(provider):
        agent_cls = None

        if provider in PROVIDERS:
            agent_cls = GenericOpenAIAPIAgent
        else:
            _logger.error(f"Unsupported provider: {provider}")
            raise ValueError(f"Unsupported provider: {provider}")

        return agent_cls(hass, entry)

    provider = entry.data.get(CONF_PROVIDER, DEFAULT_PROVIDER)
    agent = await hass.async_add_executor_job(create_agent, provider)

    await agent._async_load_configuration(entry)

    async_add_entities([agent])

    return True


class LocalLLMAgent(ConversationEntity, AbstractConversationAgent):
    """Base Local LLM conversation agent."""

    hass: HomeAssistant
    entry_id: str
    history: dict[str, list[dict]]

    _attr_has_entity_name = True

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the agent."""
        self._attr_name = entry.title
        self._attr_unique_id = entry.entry_id
        self._attr_supported_features = (
            ha_conversation.ConversationEntityFeature.CONTROL
        )

        self.hass = hass
        self.entry_id = entry.entry_id
        self.history = {}

    async def async_added_to_hass(self) -> None:
        """When entity is added to Home Assistant."""
        await super().async_added_to_hass()
        assist_pipeline.async_migrate_engine(
            self.hass, "conversation", self.entry.entry_id, self.entity_id
        )
        ha_conversation.async_set_agent(self.hass, self.entry, self)

    async def async_will_remove_from_hass(self) -> None:
        """When entity will be removed from Home Assistant."""
        ha_conversation.async_unset_agent(self.hass, self.entry)
        await super().async_will_remove_from_hass()

    @property
    def entry(self) -> ConfigEntry:
        try:
            return self.hass.data[DOMAIN][self.entry_id]
        except KeyError as ex:
            raise Exception("Attempted to use self.entry during startup.") from ex

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        """Return a list of supported languages."""
        return MATCH_ALL

    async def async_process(self, user_input: ConversationInput) -> ConversationResult:
        _logger.debug(f"Processing conversation: {user_input.text}")

        if user_input.conversation_id:
            conversation_id = user_input.conversation_id
        else:
            conversation_id = ulid.ulid()

        _logger.debug(f"user_input: {user_input}")

        conversation = []
        conversation.append({"role": "user", "message": user_input.text})

        # 对话入口
        try:
            _logger.debug(f"conversation_id: {conversation_id}")
            _logger.debug(f"conversation: {conversation}")
            response = await self._async_generate(
                conversation
            )  # 这里调用了子类GenericOpenAIAPIAgent的_async_generate方法
            _logger.debug(f"response: {response}")

        except Exception as err:
            _logger.error("There was a problem talking to the backend")

            intent_response = intent.IntentResponse(language=user_input.language)
            intent_response.async_set_error(
                intent.IntentResponseErrorCode.FAILED_TO_HANDLE,
                f"Sorry, there was a problem talking to the backend: {repr(err)}",
            )
            return ConversationResult(
                response=intent_response, conversation_id=conversation_id
            )

        conversation.append({"role": "assistant", "message": response})

        if conversation_id not in self.history:  # self.history: dict[str, list[dict]]
            self.history[conversation_id] = conversation
        else:
            self.history[conversation_id].extend(conversation)

        intent_response = intent.IntentResponse(language=user_input.language)
        intent_response.async_set_speech(response.strip())

        return ConversationResult(
            response=intent_response, conversation_id=conversation_id
        )


class GenericOpenAIAPIAgent(LocalLLMAgent):
    """Generic OpenAI API conversation agent."""

    async def _async_load_configuration(self, entry: ConfigEntry) -> None:
        # 加载各项API配置
        CONFIG.configs_llm["provider"] = entry.data[CONF_PROVIDER]
        CONFIG.configs_llm["api_key"] = entry.data["api_key"]
        CONFIG.configs_llm["base_url"] = entry.data["base_url"]
        CONFIG.configs_llm["temperature"] = entry.data["temperature"]
        CONFIG.configs_llm["max_tokens"] = entry.data["max_tokens"]
        CONFIG.hass_data["access_token"] = entry.data["access_token"]
        CONFIG.hass_data["Weather Service API Key"] = entry.data[
            "Weather Service API Key"
        ]
        CONFIG.hass_data["Traffic Service API Key"] = entry.data[
            "Traffic Service API Key"
        ]
        _logger.debug(f"configs_llm: {CONFIG.configs_llm}")
        _logger.debug(f"hass_data: {CONFIG.hass_data}")

        # 初始化设备信息、实体信息、传感器数据等
        import os

        if os.path.exists(f"{DATA_PATH}/temp"):
            await self.hass.async_add_executor_job(
                delete_all_files_in_folder,
                f"{DATA_PATH}/temp",
            )
        await self.hass.async_add_executor_job(get_miot_devices)
        await self.hass.async_add_executor_job(download_instance)
        await self.hass.async_add_executor_job(get_miot_info)
        await get_all_states()
        await self.hass.async_add_executor_job(get_all_context)
        await self.hass.async_add_executor_job(get_all_sensor_data)

        from .Supervisor import SUPERVISOR

        self.supervisor = SUPERVISOR

        from .translator import Translator

        self.translator = Translator(self.hass)

    async def _async_generate(self, conversation: list[dict]) -> str:
        try:
            result = await self.supervisor.run(
                conversation[-1]["message"]
            )  # Agent处理对话的入口
            _logger.debug(f"result: {result}")
            return result
        except Exception as err:
            _logger.error(f"Error generating response: {err}")
            _logger.error(f"Traceback: {traceback.format_exc()}")
            return f"Error generating response: {err}"
