# Collection adapters / 数据采集适配器

**English:** This boundary contains code that communicates with external data providers. `apify_client.py` implements the cost-capped Stocktwits Actor interaction and converts external output into the shared validation contract. Collection is a paid side effect and must remain explicit, bounded, and non-retrying by default.

**中文：** 本目录保存与外部数据提供商通信的代码。`apify_client.py` 实现带成本上限的 Stocktwits Actor 调用，并把外部输出交给共享校验契约。采集属于可能产生费用的副作用，必须保持显式触发、有明确上限，并且默认不自动重试。
