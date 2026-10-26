Stockfish 19（官方 Windows x64 universal 构建）
================================================

文件：stockfish.exe
来源：https://github.com/official-stockfish/Stockfish/releases/tag/sf_19
      资源：stockfish-windows-x86-64-universal.zip
      解压后：stockfish/stockfish-windows-x86-64-universal.exe → 重命名为 stockfish.exe

说明：
- universal 构建在启动时自动检测 CPU 指令集（AVX2 / BMI2 / SSE4.1 等），无需手动挑版本。
- 许可：GPLv3，完整文本见同目录 Copying.txt，作者列表见 AUTHORS。
- 本项目通过 UCI 协议以子进程方式调用它，未修改其源码。

默认参数（由 ChessFloat 启动时下发）：
    Threads = 2
    Hash    = 64 (MB)
    每次分析 Limit(time=0.8s)，可在设置里调整。

替换引擎：把新的 stockfish.exe 覆盖本文件即可，或在浮窗 ⚙ 设置里指定其它路径。
