"""平台同步器实现 — 各云平台的数据拉取逻辑。

每个平台同步器仅负责 API 数据拉取和格式转换，
返回 Pydantic 数据模型。**严禁包含任何数据库写入操作**。

新增平台步骤：
1. 继承 BaseCloudSyncer
2. 使用 @register_syncer 装饰器注册
3. 实现 _fetch_*() 方法返回 Pydantic 数据
4. 在此文件的 __all__ 中添加导出
"""
