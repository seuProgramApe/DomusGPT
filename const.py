"""Constants for the DomusGPT Conversation integration."""

DOMAIN = "DomusGPT"
INTEGRATION_VERSION = "2025.2.12"

CONF_PROVIDER = "provider"
CONF_API_KEY = "api_key"
CONF_BASE_URL = "base_url"
CONF_TEMPERATURE = "temperature"
CONF_MAX_TOKENS = "max_tokens"
CONF_ACCESS_TOKEN = "access_token"
CONF_WEATHER_API_KEY = "Weather API Key"
CONF_TRAFFIC_API_KEY = "Traffic API Key"

PROVIDERS = [
    "gpt-4-turbo",
    "deepseek-chat",
    "gpt-3.5-turbo-0125",
    "gpt-4o",
    "moonshot-v1-8k",
]

DEFAULT_PROVIDER = PROVIDERS[0]
DEFAULT_API_KEY = "sk-cFE86o4ceVxhrbdayNpZXY8RvKby6Mvt09PGHEzn77fOO5nh"
DEFAULT_BASE_URL = "https://api.openai-proxy.org/v1"
DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_TOKENS = 1024
DEFAULT_ACCESS_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJjM2E1MzkxZDBiZjc0NWE5ODkwOTIxYmZhNTAzYjk0OCIsImlhdCI6MTc0MDgwNjc3NCwiZXhwIjoyMDU2MTY2Nzc0fQ.8jWO-hVJLrBKy84d8gAvb7rWMh1uMMmUEWtn3IpB0bo"
DATA_PATH = "DomusGPT_data"  # 李安：这里做了修改
# 李安：原先的内容是 DATA_PATH = "/config/.storage/chatiot_conversation"
WORK_PATH = "/config/custom_components/DomusGPT"
