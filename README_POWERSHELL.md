# PowerShell 启动指南

本文档说明如何使用 PowerShell 启动 Grok2API。

## 🚀 快速启动

### 使用 PowerShell 启动脚本

**PowerShell 7.x（推荐）：**
```powershell
.\start.ps1
```

**如果遇到执行策略限制：**
```powershell
# 临时允许执行脚本
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process
.\start.ps1
```

**或者直接运行：**
```powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1
```

---

## 🔧 PowerShell 执行策略

### 什么是执行策略？

PowerShell 的执行策略是一种安全功能，用于控制脚本的执行权限。

### 常见执行策略

| 策略 | 说明 |
|------|------|
| `Restricted` | 默认策略，不允许运行任何脚本 |
| `RemoteSigned` | 允许运行本地脚本，远程脚本需要签名 |
| `Unrestricted` | 允许运行所有脚本 |
| `Bypass` | 临时绕过所有限制 |

### 查看当前执行策略

```powershell
Get-ExecutionPolicy
```

### 修改执行策略

**方式 1：临时修改（推荐）**
```powershell
# 仅对当前进程有效
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process
```

**方式 2：永久修改（需要管理员权限）**
```powershell
# 以管理员身份运行 PowerShell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

---

## 📱 启动方式对比

### 方式 1：start.ps1（PowerShell 脚本）

**优点：**
- ✅ UTF-8 编码支持完美
- ✅ 彩色输出，更美观
- ✅ 自动获取 IP 地址
- ✅ 无乱码问题

**使用方法：**
```powershell
.\start.ps1
```

---

### 方式 2：start.bat（批处理脚本）

**优点：**
- ✅ 无需执行策略设置
- ✅ 双击即可运行
- ✅ 兼容性好

**使用方法：**
```cmd
start.bat
```

或者双击 `start.bat` 文件

---

### 方式 3：start.sh（Bash 脚本）

**优点：**
- ✅ 跨平台（Linux/Mac/Git Bash）
- ✅ UTF-8 编码支持

**使用方法：**
```bash
./start.sh
```

---

## 🎯 推荐使用方式

### Windows 用户

**如果你使用 PowerShell 7.x：**
```powershell
.\start.ps1
```

**如果你使用 CMD 或不想设置执行策略：**
```cmd
start.bat
```

### Linux/Mac 用户

```bash
./start.sh
```

---

## 🔍 PowerShell 7.x 特性

### UTF-8 编码支持

PowerShell 7.x 默认使用 UTF-8 编码，对中文支持更好。

**start.ps1 中的编码设置：**
```powershell
# 设置控制台编码为 UTF-8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

# 设置 Python 输出编码为 UTF-8
$env:PYTHONIOENCODING = "utf-8"
```

### 彩色输出

PowerShell 支持彩色输出，让日志更易读：

```powershell
Write-Host "成功" -ForegroundColor Green
Write-Host "警告" -ForegroundColor Yellow
Write-Host "错误" -ForegroundColor Red
```

---

## 🐛 常见问题

### Q1: 提示"无法加载文件，因为在此系统上禁止运行脚本"

**A:** 这是执行策略限制，使用以下命令临时允许：

```powershell
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process
.\start.ps1
```

### Q2: PowerShell 7.x 和 Windows PowerShell 有什么区别？

**A:**
- **Windows PowerShell 5.1**：Windows 自带，基于 .NET Framework
- **PowerShell 7.x**：跨平台，基于 .NET Core，UTF-8 支持更好

### Q3: 如何安装 PowerShell 7.x？

**A:** 访问 [PowerShell GitHub](https://github.com/PowerShell/PowerShell/releases) 下载安装。

### Q4: start.ps1 和 start.bat 有什么区别？

**A:**
- **start.ps1**：PowerShell 脚本，UTF-8 支持更好，彩色输出
- **start.bat**：批处理脚本，兼容性好，无需执行策略设置

### Q5: 为什么推荐使用 PowerShell 7.x？

**A:**
- ✅ UTF-8 编码支持完美，无乱码
- ✅ 跨平台，Windows/Linux/Mac 都能用
- ✅ 功能更强大，性能更好
- ✅ 微软官方推荐

---

## 📊 三种启动方式对比

| 特性 | start.ps1 | start.bat | start.sh |
|------|-----------|-----------|----------|
| **平台** | Windows | Windows | Linux/Mac/Git Bash |
| **UTF-8 支持** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **彩色输出** | ✅ | ❌ | ✅ |
| **无需配置** | ⚠️ 需要执行策略 | ✅ | ✅ |
| **推荐指数** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |

---

## 🎉 总结

### 推荐使用方式

**Windows + PowerShell 7.x 用户：**
```powershell
.\start.ps1
```

**Windows + CMD 用户：**
```cmd
start.bat
```

**Linux/Mac 用户：**
```bash
./start.sh
```

### 优势

- ✅ 所有启动脚本都支持 UTF-8 编码
- ✅ 无中文乱码问题
- ✅ 自动获取 IP 地址
- ✅ 友好的启动提示

---

## 📚 相关文档

- **快速启动指南**：[README_START.md](./README_START.md)
- **部署指南**：[DEPLOY_GUIDE.md](./DEPLOY_GUIDE.md)
- **项目文档**：[readme.md](./readme.md)

---

**祝你使用愉快！** 🚀
