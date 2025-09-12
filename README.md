# DomusGPT
## Introduction
本项目是东南大学SRTP（Student Research Training Program）项目：面向智能家居的物联网智能体生成技术研究。本项目开发了DomusGPT，一个可用于HomeAssistant智能家居平台的智能助手集成。
## Installation
### Install HomeAssistant
### Install DomusGPT
1. 确保HomeAssistantOS中config/custom_components/目录存在。
2. 在终端运行以下命令
```bash
cd config/custom_components/
git clone https://github.com/seuProgramApe/DomusGPT.git
```
3. 重新启动HomeAssistant.在HomeAssistant GUI中打开设置/设备与服务/添加集成。点击DomusGPT开始配置集成。你需要1.LLM API Key 2.彩云天气 API Key 3.高德地图 API Key以支持DomusGPT的所有服务。
4. HomeAssistant GUI中打开设置/语音助手/添加助手，选择DomusGPT作为对话代理。
## Connect to devices
DomusGPT目前仅支持控制接入MIoT auto集成的设备。请确保所有希望DomusGPT控制的设备已经接入MIoT auto集成。你可以询问DomusGPT所有可以控制的设备。
## Start Using!
DomusGPT支持多重约束条件下的设备控制、TAP（Trigger-action Programm）生成和智能家居系统信息问答。并支持多任务处理。