# 图生图 HTTP/2 错误修复说明

## 问题描述

图生图功能失败，错误信息：
```
curl: (92) HTTP/2 stream 1 was not closed cleanly: PROTOCOL_ERROR (err 1)
```

## 根本原因

1. **Session 复用问题**：`UploadService` 默认复用同一个 `AsyncSession` 对象，在 HTTP/2 连接中，当连接变得陈旧或被服务器关闭时，会导致 PROTOCOL_ERROR
2. **缺少重试机制**：HTTP/2 协议错误是瞬态错误，应该支持自动重试
3. **错误处理不完善**：没有针对 HTTP/2 特定错误的处理逻辑

## 解决方案

### 1. 禁用 Session 复用（核心修复）

**文件**：`app/services/grok/services/assets.py`

**修改内容**：
- 为 `_get_session()` 方法添加 `reuse` 参数，允许禁用 session 复用
- 为 `upload()` 方法添加 `reuse_session` 参数（默认 `False`）
- 在不复用 session 时，确保每次上传后正确关闭 session

**原理**：每次上传使用独立的 HTTP 连接，避免 HTTP/2 连接状态问题

### 2. 添加 HTTP/2 错误重试机制

**文件**：`app/services/grok/services/assets.py`

**修改内容**：
- 导入 `retry_on_status` 重试工具
- 在 `upload()` 方法中捕获 HTTP/2 错误（curl: (92)、PROTOCOL_ERROR）
- 将 HTTP/2 错误包装为 `UpstreamException`，状态码设为 502
- 使用 `retry_on_status` 自动重试上传操作

**原理**：HTTP/2 协议错误通常是瞬态的，重试可以成功

### 3. 更新重试配置

**文件**：
- `config.defaults.toml`
- `app/services/grok/defaults.py`

**修改内容**：
- 将 502 状态码添加到 `retry_status_codes` 列表
- 原值：`[401, 429, 403]`
- 新值：`[401, 429, 403, 502]`

**原理**：允许系统对 502 错误（包括 HTTP/2 错误）进行自动重试

### 4. 更新 img2img 端点

**文件**：`app/api/v1/admin.py`

**修改内容**：
- 在调用 `upload_service.upload()` 时显式传递 `reuse_session=False`
- 添加注释说明原因

**代码示例**：
```python
# 上传图片（不复用 session 避免 HTTP/2 连接问题）
for image_data in images:
    file_id, file_uri = await upload_service.upload(
        image_data, token, reuse_session=False
    )
```

## 技术细节

### HTTP/2 PROTOCOL_ERROR 的常见原因

1. **连接复用问题**：HTTP/2 支持多路复用，但连接状态管理复杂
2. **服务器主动关闭**：服务器可能在客户端发送请求前关闭连接
3. **超时问题**：长时间空闲的连接可能被中间代理关闭
4. **流控制错误**：HTTP/2 流量控制窗口管理不当

### 为什么禁用 Session 复用有效

- **独立连接**：每次请求使用新连接，避免连接状态问题
- **避免竞态条件**：多个并发上传不会共享同一个连接
- **自动清理**：每次上传后立即关闭连接，释放资源

### 重试策略

- **最大重试次数**：3 次（配置：`retry.max_retry`）
- **退避策略**：指数退避 + jitter
- **基础延迟**：0.5 秒（配置：`retry.retry_backoff_base`）
- **最大延迟**：30 秒（配置：`retry.retry_backoff_max`）
- **总预算**：90 秒（配置：`retry.retry_budget`）

## 性能影响

### 优点
- **提高成功率**：避免 HTTP/2 连接问题
- **自动恢复**：瞬态错误自动重试
- **更好的隔离**：每个上传独立，互不影响

### 缺点
- **连接开销**：每次上传建立新连接，增加延迟（约 100-300ms）
- **资源消耗**：更多的 TCP 连接和 TLS 握手

### 权衡
对于图生图场景，通常只上传 1-2 张图片，连接开销可接受。相比失败重试的代价，禁用复用是更好的选择。

## 测试建议

### 1. 基本功能测试
```bash
# 测试单张图片上传
curl -X POST http://localhost:8000/api/v1/admin/img2img \
  -F "prompt=a beautiful landscape" \
  -F "image=@test.jpg"
```

### 2. 并发测试
```bash
# 测试多张图片同时上传
for i in {1..5}; do
  curl -X POST http://localhost:8000/api/v1/admin/img2img \
    -F "prompt=test $i" \
    -F "image=@test.jpg" &
done
wait
```

### 3. 压力测试
```bash
# 测试连续上传
for i in {1..20}; do
  curl -X POST http://localhost:8000/api/v1/admin/img2img \
    -F "prompt=test $i" \
    -F "image=@test.jpg"
  sleep 1
done
```

## 监控建议

### 日志关键字
- `HTTP/2 error during upload`：检测到 HTTP/2 错误
- `Upload failed after retries`：重试失败
- `Retry succeeded after N attempts`：重试成功

### 指标监控
- 上传成功率
- 平均重试次数
- HTTP/2 错误频率
- 上传延迟分布

## 回滚方案

如果修复导致其他问题，可以回滚：

```bash
# 回滚代码
git checkout HEAD~1 app/services/grok/services/assets.py
git checkout HEAD~1 app/api/v1/admin.py
git checkout HEAD~1 config.defaults.toml
git checkout HEAD~1 app/services/grok/defaults.py

# 重启服务
systemctl restart grok2api
```

## 后续优化建议

1. **连接池管理**：实现智能连接池，自动检测和清理陈旧连接
2. **HTTP/1.1 降级**：为特定场景提供 HTTP/1.1 选项
3. **监控告警**：添加 HTTP/2 错误率监控和告警
4. **配置化**：允许用户通过配置选择是否复用 session

## 相关文件清单

- `app/services/grok/services/assets.py` - 核心修复
- `app/api/v1/admin.py` - img2img 端点更新
- `config.defaults.toml` - 配置更新
- `app/services/grok/defaults.py` - 默认配置更新
- `app/services/grok/utils/retry.py` - 重试工具（已存在）
- `app/services/grok/processors/base.py` - HTTP/2 错误检测（已存在）

## 版本信息

- **curl_cffi 版本**：0.14.0
- **修复日期**：2026-02-08
- **影响范围**：图生图功能、文件上传功能
