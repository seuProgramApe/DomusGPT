# DomusGPT
## Introduction
东南大学SRTP（Student Research Training Program）项目：面向智能家居的物联网智能体生成技术研究。本项目开发了DomusGPT，一个可用于Home Assistant平台的智能家居助手集成（Integration）。
## Installation
### Install Home Assistant
DomusGPT是运行在Home Assistant中的集成（integration）。DomusGPT依托Home Assistant作为控制智能家居设备的平台。你需要首先安装Home Assistant以支持DomusGPT的运行。
### Install DomusGPT
1. 确保Home Assistant中config/custom_components/目录存在。
2. 在终端运行以下命令
```bash
cd config/custom_components/
git clone https://github.com/seuProgramApe/DomusGPT.git
```
3. 重新启动Home Assistant。在Home Assistant中依次点击设置、设备与服务、添加集成。选择DomusGPT并配置该集成。你需要1.大语言模型API Key 2.彩云天气API Key 3.高德地图API Key以获取DomusGPT支持的所有服务。
4. 在Home Assistant中依次点击设置、语音助手、添加助手，选择DomusGPT作为对话代理。
## Connect to Devices
DomusGPT目前仅支持控制接入MIoT auto集成的设备。请确保所有希望DomusGPT控制的设备已经接入MIoT auto集成。你可以通过询问DomusGPT获知所有可以被控制的设备。
## Start Using!
DomusGPT支持多重约束条件下的设备控制、TAP（Trigger-action Programm）脚本生成和智能家居系统信息问答。并支持多任务处理。