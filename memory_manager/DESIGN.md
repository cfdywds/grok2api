# Context Monitor

## 职责
监控上下文使用情况，判断是否需要触发记忆压缩

### 监控指标
- **Token 使用量**：实时追踪对话 token 消耗
- **时间间隔**：检查距离上次压缩的时间
- **消息数量**：统计新增消息数

### 触发条件（混合模式）

```python
TRIGGER_CONDITIONS = {
    "token_threshold": 30_000,      # Token 接近上限
    "time_interval": 2 * 60 * 60,   # 超过 2 小时未压缩
    "message_count": 500,           # 消息数过多
}
```

### 实现逻辑

```python
class ContextMonitor:
    def __init__(self, config: Config):
        self.config = config
        self.usage_tracker = UsageTracker()
        self.last_compression_time = datetime.now()

    async def check_trigger(self) -> TriggerDecision:
        """
        检查是否触发压缩

        Returns:
            TriggerDecision: 包含决策和原因的枚举
        """
        current_token_usage = await self.usage_tracker.get_current_usage()
        time_elapsed = datetime.now() - self.last_compression_time
        message_count = await self.usage_tracker.get_message_count()

        # 检查各个条件
        token_exceeded = current_token_usage > TRIGGER_CONDITIONS["token_threshold"]
        time_expired = time_elapsed.total_seconds() > TRIGGER_CONDITIONS["time_interval"]
        messages_exceeded = message_count > TRIGGER_CONDITIONS["message_count"]

        # 只要满足任一条件就触发
        if token_exceeded or time_expired or messages_exceeded:
            return TriggerDecision(
                should_compress=True,
                reason=self._get_reason(token_exceeded, time_expired, messages_exceeded)
            )

        return TriggerDecision(should_compress=False)

    def _get_reason(self, token_exp, time_exp, msg_exp) -> str:
        reasons = []
        if token_exp: reasons.append("Token usage near limit")
        if time_exp: reasons.append(f"No compression for {time_elapsed} hours")
        if msg_exp: reasons.append("Message count exceeded")
        return "; ".join(reasons)
```

---

## 下一步

请告诉我是否需要我继续实现：
1. Memory Analyzer（记忆分析器）- 识别重复/冗余内容
2. Compression Engine（压缩引擎）- 去重和摘要算法
3. Archive Manager（归档管理器）- 存储旧对话
4. MCP Server 完整实现
