# DomusGPT

## 项目简介
东南大学SRTP项目（No. 202509091）：面向智能家居的物联网智能体生成技术研究。本项目开发了DomusGPT，一款可用于Home Assistant平台的智能家居助手集成。

## 安装指南

### 1. 安装Home Assistant
DomusGPT运行在Home Assistant平台上，请首先安装Home Assistant。

### 2. 安装DomusGPT
1. 在Home Assistant的`config/`目录下创建目录`custom_components/`（若该目录存在可忽略）。
2. 使用以下命令将DomusGPT克隆到该目录：
    ```bash
    cd config/custom_components/
    git clone https://github.com/seuProgramApe/DomusGPT.git
    ```
3. 重启Home Assistant。
4. 在Home Assistant中，依次点击 **设置 > 设备与服务 > 添加集成**，选择**DomusGPT**进行配置，配置时需要提供以下API Key：
   - 任一支持的大语言模型的API Key（提供列表供选择）
   - 彩云天气API Key
   - 高德地图API Key

### 3. 启用语音助手
在Home Assistant中，依次点击**设置 > 语音助手 > 添加助手**，选择**DomusGPT**作为对话代理。

## 设备连接
DomusGPT当前仅支持控制接入**MIoT auto**集成的设备。请确保所有设备已经通过该集成接入Home Assistant。你可通过询问DomusGPT获知所有可控制的设备列表。

## 开始使用
DomusGPT支持多重约束条件下的设备控制、TAP脚本生成以及复杂的信息问答任务。

