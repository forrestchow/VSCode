# 电商数据获取

从电商平台卖家中心（商家后台）自动获取自有店铺的商品、订单、店铺数据，清洗后存入 PostgreSQL，通过 Metabase 进行 BI 分析。

## 架构

纯 Python + CDP（Chrome DevTools Protocol），不需要 ChromeDriver，不需要浏览器插件。

详见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

## 快速开始

```bash
# 安装依赖
pip install -r python_engine/requirements.txt

# 初始化数据库
python scripts/init_db.py

# 定位察尔汗 Chrome profile
python scripts/find_chayan.py

# 启动
python python_engine/main.py
```
