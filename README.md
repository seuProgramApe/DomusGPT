# DomusGPT
## Introduction
东南大学SRTP项目（No.202509091）：面向智能家居的物联网智能体生成技术研究。本项目开发了DomusGPT，一款可用于Home Assistant平台的智能家居助手集成。
## Installation
### Install Home Assistant
DomusGPT是运行在Home Assistant平台上的集成，依赖Home Assistant平台控制智能家电。你需要首先安装Home Assistant方可使用DomusGPT。
### Install DomusGPT
1. 确保Home Assistant中config/custom_components/目录存在。
2. 在终端运行以下命令
```bash
cd config/custom_components/
git clone https://github.com/seuProgramApe/DomusGPT.git
```
3. 重启Home Assistant。在Home Assistant中依次点击设置、设备与服务、添加集成。选择DomusGPT并配置该集成。你需要
   1.DomusGPT支持的任一LLM的API Key
   2.彩云天气API Key
   3.高德地图API Key
4. 在Home Assistant中依次点击设置、语音助手、添加助手，选择DomusGPT作为对话代理。
## Connect to Devices
DomusGPT目前仅支持控制接入MIoT auto集成的设备。请确保所有希望DomusGPT控制的设备已经接入MIoT auto集成。你可以通过询问DomusGPT获知所有可以被控制的设备。
## Start Using!
DomusGPT能够处理多重约束条件下的设备控制、TAP（Trigger-action Programm）脚本生成、综合信息问答等复杂任务。
