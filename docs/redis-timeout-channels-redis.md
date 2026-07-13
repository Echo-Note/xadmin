# WebSocket Redis TimeoutError 排查与修复

> 日期：2026-07-13
> 影响：Django Channels WebSocket 连接空闲时每 5 秒抛出异常，导致 WS consumer 崩溃

## 现象

Django 后端 ASGI 服务运行期间，WebSocket consumer 在空闲等待消息时反复抛出如下异常：

```
Exception inside application: Timeout reading from 172.16.30.120:6379
...
File ".../channels/utils.py", line 57, in await_many_dispatch
    await task
redis.exceptions.TimeoutError: Timeout reading from 172.16.30.120:6379
```

异常每隔约 5 秒出现一次，对应 `channels_redis` 的 `BRPOP` 阻塞读循环。

## 排查过程

### 第一步：排除 Redis 服务本身的问题

远程 Redis 运行在 Docker 主机 `172.16.30.120:6379`（容器 `xadmin-redis`）。

| 检查项 | 命令 | 结果 |
|---|---|---|
| 网络连通性 | `ping 172.16.30.120` | 0% 丢包，延迟 <1ms |
| TCP 端口 | `nc -zv 172.16.30.120 6379` | 连接成功 |
| Redis PING | `redis.ping()` | `True` |
| redis_version | `info('server')` | 7.4.3 |
| uptime | `info('server')` | 53 分钟（稳定运行） |
| connected_clients | `info('clients')` | 10 |
| rejected_connections | `info('stats')` | 0 |
| 容器状态 | `docker ps` | `Up (healthy)` |
| 容器日志 | `docker logs xadmin-redis` | 无任何异常，仅正常 RDB 持久化 |

**结论：Redis 服务本身完全正常，问题出在客户端侧。**

### 第二步：复现并定位

用项目实际的 channel layer 编写探测脚本：

```python
layer = channels.layers.get_channel_layer()
# 1) 有消息时 send/receive 闭环
await layer.send('test.ch', {'type': 'ping'})
msg = await layer.receive('test.ch')   # 0.01s 正常返回

# 2) 空 channel receive（模拟 WS consumer 空闲等待）
await layer.receive('test.empty')      # 精确 5.00s 后抛 TimeoutError
```

关键发现：
- **有消息时** `send/receive` 闭环 0.01s 正常（BRPOP 立即返回，不会触发 socket 超时）。
- **空 channel** `receive` **精确在 5.00s 抛 `TimeoutError: Timeout reading from 172.16.30.120:6379`**，与报错完全一致。

5 秒这个数字同时等于 `channels_redis.RedisChannelLayer.brpop_timeout`（=5）和 `redis-py 8.x` 的 `DEFAULT_SOCKET_TIMEOUT`（=5），这是关键线索。

### 第三步：确认根因

对比测试 `redis-py` 不同版本：

| redis-py 版本 | 空 channel receive 行为 |
|---|---|
| 8.0.1 | 精确 5.00s 抛 `TimeoutError` ❌ |
| 5.2.1 | 阻塞 12s+ 正常不报错 ✅ |

**根因机制：**

1. `channels-redis 4.3.0`（当前最新版）的 `receive_single` 用 `BRPOP` 阻塞读 Redis 列表，超时设为 `brpop_timeout = 5` 秒：
   ```python
   # channels_redis/core.py
   content = await self._brpop_with_clean(index, channel_key, timeout=self.brpop_timeout)
   ```

2. `redis-py 8.x` 改了 `read_response` 的超时语义（`redis/_defaults.py`）：
   ```python
   DEFAULT_SOCKET_TIMEOUT = 5  # 5s  （5.x 为 None，即不超时）
   ```
   在 `redis/asyncio/connection.py` 中：
   ```python
   read_timeout = timeout if timeout is not None else self.socket_timeout
   async with async_timeout(read_timeout):
       ...
   ```
   当 `BRPOP` 的阻塞时间（5s）≥ `socket_timeout`（5s）时，**socket 读超时会先于 BRPOP 自然返回触发 `TimeoutError`**，而不是让 BRPOP 阻塞到超时后返回 `None`。

3. `channels-redis 4.3.0` 声明依赖 `redis>=4.6`（无上限），发布时 `redis-py` 还在 5.x，代码未适配 8.x 的 BRPOP 超时语义。

4. 项目 `pyproject.toml` 原本未显式锁定 `redis` 版本，`redis==8.0.1` 作为 `channels-redis` / `django-redis` 的传递依赖被解析进来，引入了该不兼容。

### 依赖版本确认

```
channels-redis==4.3.0   # 已是最新版，无更高版本可升级
redis==8.0.1            # 问题版本
django-redis==6.0.0     # 要求 redis>=4.0.2，兼容 5.x
channels-redis          # 要求 redis>=4.6，兼容 5.x
```

## 修复方案

在 `server/pyproject.toml` 显式锁定 `redis` 到 5.x，避免解析到不兼容的 8.x：

```python
"django-redis==6.0.0",
# 锁定 redis-py 5.x：channels-redis 4.3.0 的 BRPOP 阻塞读与 redis-py 8.x 的
# socket_timeout 语义不兼容，空 channel receive 会每 5s 抛 TimeoutError。
# channels-redis 4.3.0 声明 redis>=4.6 无上限，但代码未适配 8.x，故显式锁 5.x。
"redis>=5.0,<6.0",
```

执行 `uv sync` 后解析到 `redis==5.3.1`。

## 验证

降级后重新运行探测脚本：
- `redis-py: 5.3.1`
- 有消息 `send/receive`：0.01s 正常
- 空 channel `receive`：阻塞 12s+ **不再抛 `TimeoutError`** ✅

项目代码（`apps/common/utils/connection.py`）仅使用 `redis.Redis`（isinstance 检查）和 `redis.client.PubSub` 等稳定 API，5.x / 8.x 均兼容，降级安全。

## 启示

1. **传递依赖需关注上游兼容性**：`channels-redis 4.3.0` 对 `redis` 只设下限不设上限，`redis-py 8.x` 的破坏性默认值变更会无声引入 bug。对于关键传递依赖，应在 `pyproject.toml` 显式锁定版本范围。

2. **排查顺序**：遇到「Timeout reading from host:port」类错误，应先排除服务端（连通性 / 服务健康 / 日志），再定位客户端（版本 / 配置 / 超时语义）。本次 Redis 服务完全正常，根因在 `redis-py` 版本。

3. **超时值巧合是重要线索**：报错的 5 秒同时等于 `brpop_timeout` 和 `redis-py 8.x` 的 `DEFAULT_SOCKET_TIMEOUT`，直接指向了客户端超时语义变更。
