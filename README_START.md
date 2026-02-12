# 快速启动指南

## 问题解决

### 问题：项目无法启动，提示 `ModuleNotFoundError: No module named 'qrcode'`

**原因：** 系统使用的是全局 Python 环境，而不是项目的虚拟环境。

**解决方案：**

#### 方法 1：使用启动脚本（推荐）

**Windows:**
```bash
start.bat
```

**Linux/Mac:**
```bash
./start.sh
```

#### 方法 2：手动指定虚拟环境

**Windows:**
```bash
.venv\Scripts\python.exe main.py
```

**Linux/Mac:**
```bash
.venv/bin/python main.py
```

#### 方法 3：使用 uv run

```bash
uv run python main.py
```

#### 方法 4：激活虚拟环境后启动

**Windows:**
```bash
.venv\Scripts\activate
python main.py
```

**Linux/Mac:**
```bash
source .venv/bin/activate
python main.py
```

---

## 完整启动流程

### 1. 首次安装依赖

```bash
uv sync
```

### 2. 启动服务

使用启动脚本（推荐）：

**Windows:**
```bash
start.bat
```

**Linux/Mac:**
```bash
./start.sh
```

或者手动启动：

```bash
.venv\Scripts\python.exe main.py  # Windows
.venv/bin/python main.py          # Linux/Mac
```

### 3. 访问服务

- **本地访问：** http://localhost:8000
- **局域网访问：** http://192.168.x.x:8000（查看启动日志获取实际IP）
- **手机访问：** 点击页面右上角 📱 按钮扫码

---

## 常见问题

### Q1: 为什么直接运行 `python main.py` 会报错？

**A:** 因为系统的 `python` 命令指向的是全局 Python 环境（如 miniconda），而不是项目的虚拟环境。项目依赖（如 qrcode）只安装在虚拟环境中。

**解决方法：**
- 使用启动脚本
- 或者明确指定虚拟环境的 Python：`.venv\Scripts\python.exe main.py`

### Q2: 手机无法访问怎么办？

**A:** 检查以下几点：
1. 手机和电脑是否在同一 WiFi 网络
2. 防火墙是否允许 8000 端口
3. 服务是否使用 `--host 0.0.0.0` 启动（启动脚本已自动配置）

### Q3: 如何修改端口？

**A:** 编辑 `.env` 文件：
```
SERVER_HOST=0.0.0.0
SERVER_PORT=8000  # 修改为你想要的端口
```

### Q4: 如何在后台运行？

**Windows (使用 start):**
```bash
start /B .venv\Scripts\python.exe main.py
```

**Linux/Mac (使用 nohup):**
```bash
nohup .venv/bin/python main.py > server.log 2>&1 &
```

---

## 环境检查

### 检查虚拟环境

```bash
# Windows
.venv\Scripts\python.exe -c "import sys; print(sys.executable)"

# Linux/Mac
.venv/bin/python -c "import sys; print(sys.executable)"
```

### 检查依赖安装

```bash
# Windows
.venv\Scripts\python.exe -c "import qrcode; print('qrcode installed')"

# Linux/Mac
.venv/bin/python -c "import qrcode; print('qrcode installed')"
```

### 查看已安装的包

```bash
uv pip list
```

---

## 开发模式

如果需要自动重载（代码修改后自动重启）：

```bash
# Windows
.venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Linux/Mac
.venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 生产部署

使用多进程模式（仅限 Linux/Mac）：

```bash
.venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

**注意：** Windows 不支持多进程模式，会自动降级为单进程。

---

## 总结

**推荐启动方式：**

1. **开发环境：** 使用 `start.bat` 或 `start.sh`
2. **生产环境：** 使用 systemd/supervisor 管理服务
3. **临时测试：** 使用 `uv run python main.py`

**关键点：**
- 始终使用虚拟环境中的 Python
- 确保使用 `--host 0.0.0.0` 以支持局域网访问
- 手机访问需要在同一局域网内
