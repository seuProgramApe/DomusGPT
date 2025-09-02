"""Constants for the DomusGPT Conversation integration."""

DOMAIN = "DomusGPT"
INTEGRATION_VERSION = "2025.2.12"

CONF_PROVIDER = "provider"
CONF_API_KEY = "api_key"
CONF_BASE_URL = "base_url"
CONF_TEMPERATURE = "temperature"
CONF_MAX_TOKENS = "max_tokens"
CONF_ACCESS_TOKEN = "access_token"
CONF_WEATHER_API_KEY = "Weather Service API Key"
CONF_TRAFFIC_API_KEY = "Traffic Service API Key"

PROVIDERS = [
    "gpt-4-turbo",
    "deepseek-chat",
    "gpt-3.5-turbo-0125",
    "gpt-4o",
    "moonshot-v1-8k",
]

DEFAULT_PROVIDER = PROVIDERS[0]
DEFAULT_API_KEY = ""
DEFAULT_WEATHER_API_KEY = ""
DEFAULT_TRAFFIC_API_KEY = ""
DEFAULT_BASE_URL = "https://api.openai-proxy.org/v1"
DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_TOKENS = 1024
DEFAULT_ACCESS_TOKEN = ""
DATA_PATH = "DomusGPT_data"  # 这里做了修改
# 原先内容是 DATA_PATH = "/config/.storage/chatiot_conversation"
WORK_PATH = "/config/custom_components/DomusGPT"
