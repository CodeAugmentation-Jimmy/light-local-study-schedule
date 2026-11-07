# 学习日程

一个用于安排课程、记录学习时长和查看进度的桌面与安卓应用。

## 下载与安装

[下载最新安装包](https://github.com/CodeAugmentation-Jimmy/light-local-study-schedule/releases/latest)

本次发布包含 Windows 1.2.3 与安卓 1.2，两端支持局域网同步。

| 平台 | 安装包 | 系统要求 |
| --- | --- | --- |
| Windows | [StudySchedule-Setup-1.2.3.exe](https://github.com/CodeAugmentation-Jimmy/light-local-study-schedule/releases/download/v1.2.3/StudySchedule-Setup-1.2.3.exe) | Windows 10 2004 及以上／Windows 11，x64 |
| 安卓 | [StudySchedule-android-1.2.apk](https://github.com/CodeAugmentation-Jimmy/light-local-study-schedule/releases/download/v1.2.3/StudySchedule-android-1.2.apk) | Android 8.0 及以上 |

文件校验值见同一发行版中的 [SHA256SUMS.txt](https://github.com/CodeAugmentation-Jimmy/light-local-study-schedule/releases/download/v1.2.3/SHA256SUMS.txt)。

- Windows 下载 `.exe` 后运行中文安装向导。安装后从桌面或开始菜单打开“学习日程”。
- 安卓将 `.apk` 传至手机后安装，按系统提示允许此次文件来源安装应用（忽略手机可能的境外应用提醒）。
- 更新已有版本时，先正常关闭应用，再覆盖安装到原位置，会自动保留原有学习记录。
- GitHub 自动提供的 `Source code` 压缩包是源码，日常使用请下载上述 `.exe` 或 `.apk`。

## 特色功能
- 轻量化（安卓版44KB,Windows11MB），并且有极高的自定义空间
- 按每天、单数日、双数日或指定星期安排课程，并根据系统日期自动切换。
- 手动开始、暂停、继续和停止学习计时，可设置专注轮次。
- 查看历史记录、近 7／30 天统计与连续学习天数，电脑版支持 CSV 导出。
- 电脑和安卓通过可信局域网手动合并课程、目标与学习记录。
- Windows 提供主窗口内导航、迷你计时窗口和置顶选项。
- 界面优美有现代感。

## 快速使用

1. 添加课程，填写名称和学习目标分钟数。
2. 选择每天、单数日、双数日或指定星期上课。例如英语设单数日，数学设双数日。
3. 在今日课程中选中一门课，手动开始计时，休息时暂停，学习结束后停止。
4. 在“学习日程”预览未来课程，在“统计分析”查看学习记录。Windows 左侧导航在同一主窗口切换页面。
5. 更多功能请自行探索……

单双日按每月日期判断，31 日和下月 1 日均为单数日。未安排课程的日期不会计入当日课程目标。

## 电脑与手机同步

1. 电脑和手机接入同一个可信局域网。
2. 电脑进入“局域网同步”，点击“开启同步”，查看电脑地址和配对码。
3. 安卓进入“局域网同步”，输入电脑显示的地址及 12 位配对码，点击“立即同步”。
4. 显示同步成功后，两端拥有合并后的课程、目标和学习记录。以后需要更新时再次手动同步。

两端均需 1.2 或更新版本，系统日期与时区应保持一致。电脑程序需保持打开且同步已开启。
两端计时独立，同一段学习若同时在两端计时，合并后时长会累加。

## 数据保存与备份

源码版数据保存在项目目录，Windows 安装版数据保存在 `%LOCALAPPDATA%\StudySchedule`。
关闭程序后，可备份“学习记录.json”“同步设置.json”和“桌面设置.json”，保留记录、配对信息与桌面偏好。
请妥善保管备份，避免将含个人学习记录和配对码的文件公开上传。

## 从源码运行电脑版

在 Windows 安装带 Tkinter 的 Python 3，运行 `日程程序.py`，或双击 `启动日程程序.bat`。

## 测试

在项目目录运行 `python -m unittest discover -s tests -v`。
安卓 Java 互操作测试需要本地 JDK、Android SDK 和 JSON 测试库，缺少时会跳过对应测试。

## 当前验证范围

- Windows 已通过 36 项回归测试和打包后程序自检，包括主窗口导航、课程表、计时与局域网同步。
- 安卓已通过编译、APK 签名校验及 Java 逻辑／跨端协议测试。项目维护者已在 Android 17 环境完成真机验收。
- Windows 安装包未做商业代码签名，系统可能显示发布者未知。安卓发行包沿用项目本地调试签名。

## 使用与同步说明

请参阅 [电脑版安装说明](电脑版安装说明.txt) 和 [安卓与同步说明](安卓使用与同步说明.md)。
同步使用带配对码的局域网 HTTP，适用于可信网络。两端均需 1.2 或更新版本。

## 发行与依赖

第三方许可说明位于 `windows/THIRD_PARTY_NOTICES.txt`。
项目代码采用 [MIT 许可证](LICENSE)，允许使用、修改、分发和商用，需保留许可与版权声明。
第三方依赖仍遵循各自的许可条款。
