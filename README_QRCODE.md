# 手机扫码访问功能

## 功能说明

新增了手机扫码访问功能，让局域网内的手机可以通过扫描二维码快速访问网站。

## 使用方法

### 1. 启动服务

```bash
python main.py
```

或使用 uvicorn：

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

**重要**：必须使用 `--host 0.0.0.0` 才能让局域网内的其他设备访问。

### 2. 打开网页

在电脑浏览器中访问任意页面，例如：
- http://localhost:8000/admin/gallery
- http://localhost:8000/admin/imagine

### 3. 点击扫码按钮

在导航栏右上角找到 📱 按钮，点击后会弹出二维码。

### 4. 手机扫码

使用手机微信、浏览器等扫描二维码，即可在手机上访问相同的页面。

## 技术实现

### 后端 API

- `GET /api/v1/qrcode/generate` - 生成二维码图片
  - 参数：
    - `url`: 完整URL（可选）
    - `port`: 端口号（默认8000）
    - `path`: 路径（默认为空）

- `GET /api/v1/qrcode/info` - 获取二维码信息
  - 参数：
    - `port`: 端口号（默认8000）
  - 返回：本机IP、URL等信息

### 前端组件

- `app/static/common/qrcode-modal.html` - 二维码弹窗组件
- 导航栏添加了扫码按钮
- 自动获取当前页面路径生成对应的二维码

### 依赖库

- `qrcode[pil]` - 二维码生成库

## 注意事项

1. **网络要求**：手机和电脑必须在同一局域网内
2. **防火墙**：确保防火墙允许 8000 端口的访问
3. **IP地址**：系统会自动获取本机局域网IP地址
4. **端口配置**：如果修改了端口，二维码会自动适配

## 故障排查

### 手机无法访问

1. 检查手机和电脑是否在同一WiFi网络
2. 检查防火墙设置：
   ```bash
   # Windows
   netsh advfirewall firewall add rule name="Grok2API" dir=in action=allow protocol=TCP localport=8000
   ```
3. 确认服务启动时使用了 `--host 0.0.0.0`

### 二维码无法显示

1. 检查浏览器控制台是否有错误
2. 确认 `/api/v1/qrcode/generate` 接口可以访问
3. 清除浏览器缓存后重试

## API 测试

```bash
# 获取二维码信息
curl http://localhost:8000/api/v1/qrcode/info?port=8000

# 生成二维码（在浏览器中打开）
http://localhost:8000/api/v1/qrcode/generate?port=8000&path=/admin/gallery
```

## 示例

假设你的电脑IP是 `192.168.1.100`，端口是 `8000`：

1. 在电脑上访问：`http://localhost:8000/admin/gallery`
2. 点击导航栏的 📱 按钮
3. 二维码会显示：`http://192.168.1.100:8000/admin/gallery`
4. 手机扫码后会直接打开图片管理页面
