# 学习日程

一个用于安排课程、记录学习时长和查看进度的桌面与安卓应用。

## 功能

- 按每天、单数日、双数日或指定星期安排课程，并根据系统日期自动切换。
- 手动开始、暂停、继续和停止学习计时，可设置专注轮次。
- 查看历史记录、近 7／30 天统计与连续学习天数，电脑版支持 CSV 导出。
- 电脑和安卓通过可信局域网手动合并课程、目标与学习记录。
- Windows 提供主窗口内导航、迷你计时窗口和置顶选项。

## 运行电脑版

在 Windows 安装带 Tkinter 的 Python 3，运行 `日程程序.py`，或双击 `启动日程程序.bat`。
源码版数据保存在项目目录，Windows 安装版数据保存在 `%LOCALAPPDATA%\StudySchedule`。

## 安卓与构建

- 安卓源码位于 `android/`，支持 Android 8.0 及以上。
- 可用 Android Studio 打开 `android/`，或运行 `android/build-apk.ps1` 并提供本地 JDK 17 和 Android SDK。
- Windows 打包入口为 `windows/build-windows.ps1`，需要 Python、PyInstaller 和 Inno Setup。
- 构建工具、安装包、个人学习记录、配对码和签名密钥不纳入源码仓库。
- 首次自行构建安卓包会使用新的本地签名密钥，覆盖已有安装时需要匹配原签名。

## 测试

在项目目录运行 `python -m unittest discover -s tests -v`。
安卓 Java 互操作测试需要本地 JDK、Android SDK 和 JSON 测试库，缺少时会跳过对应测试。

## 使用与同步说明

请参阅 [电脑版安装说明](电脑版安装说明.txt) 和 [安卓与同步说明](安卓使用与同步说明.md)。
同步使用带配对码的局域网 HTTP，适用于可信网络。两端均需 1.2 或更新版本。

## 发行与依赖

第三方许可说明位于 `windows/THIRD_PARTY_NOTICES.txt`。
项目代码采用 [MIT 许可证](LICENSE)，允许使用、修改、分发和商用，需保留许可与版权声明。
第三方依赖仍遵循各自的许可条款。
