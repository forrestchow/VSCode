# 电商数据获取 — 架构文档

> **本文档是项目的唯一真相源（single source of truth）。**
> 所有代码实现必须对齐本文档。如果代码偏离文档，需要更新文档以反映实际实现。

---

## 1. Context

### 目标

从电商平台**卖家中心（商家后台）**自动获取自有店铺数据，清洗后存入 PostgreSQL，最终通过 Metabase 进行 BI 分析。

### 数据来源（自有店铺后台）

| 数据类型 | 来源页面 | 说明 |
|---------|---------|------|
| **商品数据** | 出售中的商品 / 商品管理 | 已发布商品的列表、价格、SKU、库存 |
| **订单数据** | 已卖出宝贝 / 订单管理 | 历史订单、销售额、退款 |
| **店铺数据** | 数据中心 / 日报 | 访客数、支付金额、转化率、客单价 |

### 用户工作流

用户使用 **"察尔汗"** Chrome 访客浏览器（保存了各平台卖家中心的账号密码），打开卖家中心 → 点击登录框选账号 → 进入后台 → 浏览数据页面。Python 脚本通过 CDP 连接浏览器，注入 JS 提取页面数据。

---

## 2. 核心架构：纯 Python + CDP

### 2.1 为什么不需要 ChromeDriver（反爬关键）

| | Selenium + ChromeDriver | 我们的 CDP 方案 |
|---|---|---|
| `navigator.webdriver` | `true` ❌ 网站秒检测 | `undefined` ✅ 完全隐藏 |
| 浏览器横幅 | "受自动测试软件控制" | 无 |
| 登录态 | 独立新 profile | 察尔汗 profile（真实登录态） |
| 风控风险 | 高 | 低（看起来就是真人操作） |

CDP（Chrome DevTools Protocol）是 Chrome F12 开发者工具的底层协议。Python 通过 WebSocket 连接 Chrome，不需要 ChromeDriver，不启动自动化模式。

### 2.2 架构图

```
┌─────────────────────────────────────────────┐
│               Python 引擎                     │
│                                              │
│  ┌──────────────────────┐                   │
│  │  browser/manager.py  │  Chrome 生命周期    │
│  │  → 发现/启动察尔汗     │                   │
│  │  → CDP 连接(9222端口) │                   │
│  └──────────┬───────────┘                   │
│             │                                │
│  ┌──────────▼───────────┐                   │
│  │  browser/cdp_client  │  CDP 操作          │
│  │  → Runtime.evaluate  │  执行JS提取数据     │
│  │  → DOM.getOuterHTML  │  获取HTML（开发用）  │
│  │  → Page.navigate     │  页面导航           │
│  └──────────┬───────────┘                   │
│             │                                │
│  ┌──────────▼───────────┐                   │
│  │  pipeline/*          │  数据处理           │
│  │  → cleaner.py        │  pandas 清洗        │
│  │  → normalizer.py     │  多平台归一化        │
│  │  → loader.py         │  PostgreSQL 写入     │
│  └──────────┬───────────┘                   │
│             │                                │
│  ┌──────────▼───────────┐                   │
│  │  db/*                │  数据存储           │
│  │  → PostgreSQL        │  星型模型           │
│  │  → Metabase 展示     │  BI 可视化          │
│  └──────────────────────┘                   │
└─────────────────────────────────────────────┘
```

### 2.3 不需要的东西

| 不需要 | 原因 |
|--------|------|
| Chrome 插件 | CDP 的 `Runtime.evaluate` 可以直接注入 JS 提取数据 |
| HTTP Server | Python 通过 CDP 直接拿到返回值，无需插件 POST |
| ChromeDriver | CDP 原生支持，无自动化标记 |

---

## 3. Chrome 浏览器管理

### 3.1 察尔汗 Chrome 自动发现/连接

```
Python 启动时检测：

情况1：察尔汗 Chrome 没有运行
    → Python 启动察尔汗（带 --remote-debugging-port=9222）
    → 用户看到察尔汗浏览器打开（所有密码和登录态都在）
    ✅ 全自动

情况2：察尔汗 Chrome 已在运行，且 debug port 可访问
    → Python 直接 CDP 连接
    ✅ 直接连接

情况3：察尔汗 Chrome 已在运行，但没有 debug port
    → 提示用户配置快捷方式
    ⚠️ 一次性配置
```

**一劳永逸**：给察尔汗快捷方式添加参数 `--remote-debugging-port=9222`

### 3.2 HTML 结构获取（开发用）

通过 CDP 直接获取，无需任何扩展：

```python
# 获取整个页面 HTML
html = await cdp.send("Runtime.evaluate", {
    "expression": "document.documentElement.outerHTML",
    "returnByValue": True
})

# 获取特定区域
html = await cdp.send("Runtime.evaluate", {
    "expression": "document.querySelector('.product-list').outerHTML",
    "returnByValue": True
})
```

---

## 4. 项目目录结构

```
E:/VS Code/电商数据获取/
│
├── docs/
│   └── ARCHITECTURE.md           # ← 本文档（唯一真相源）
│
├── python_engine/                # Python 引擎
│   ├── main.py                   # 入口
│   ├── config.py                 # 配置（察尔汗路径、DB连接、debug port）
│   ├── browser/
│   │   ├── manager.py            # Chrome 生命周期管理
│   │   ├── navigator.py          # CDP 页面导航控制
│   │   └── cdp_client.py         # CDP 协议封装
│   ├── extractors/               # 各平台数据提取器
│   │   ├── base.py               # 提取器基类
│   │   ├── taobao/
│   │   │   ├── products.py       # 出售中的商品
│   │   │   └── orders.py         # 订单管理
│   │   ├── pdd/                  # 拼多多（后续）
│   │   ├── jd/                   # 京东（后续）
│   │   └── douyin/               # 抖音（后续）
│   ├── pipeline/
│   │   ├── cleaner.py            # pandas 数据清洗
│   │   ├── normalizer.py         # 多平台字段归一化
│   │   └── loader.py             # PostgreSQL 写入
│   ├── db/
│   │   ├── connection.py         # SQLAlchemy engine
│   │   └── schema.sql            # DDL（复用电商BI分析的星型模型）
│   └── requirements.txt
│
├── html_snapshots/               # HTML 快照（开发分析用，不进 git）
├── scripts/
│   ├── init_db.py                # 初始化数据库 + 填充 dim_date
│   └── find_chayan.py            # 定位察尔汗 profile 路径
│
├── .gitignore
└── README.md
```

---

## 5. 数据采集目标（按平台）

### 5.1 淘宝/天猫 卖家中心（千牛）— 优先实现

| 页面 | URL 匹配 | 要提取的数据 |
|------|---------|------------|
| 出售中的商品 | `myseller.taobao.com/sale/item*` | 商品ID、标题、价格、SKU、库存、月销量 |
| 已卖出的宝贝 | `myseller.taobao.com/sale/order*` | 订单号、商品、金额、时间、状态 |
| 数据中心-日报 | `sycm.taobao.com/*` | 访客数、支付金额、转化率、客单价 |

### 5.2 拼多多 商家后台（后续扩展）

| 页面 | URL 匹配 | 要提取的数据 |
|------|---------|------------|
| 商品管理 | `mms.pinduoduo.com/goods/list*` | 商品ID、标题、价格、销量、库存 |
| 订单管理 | `mms.pinduoduo.com/order/list*` | 订单号、商品、金额、时间 |
| 数据中心 | `mms.pinduoduo.com/data/*` | 流量、销售额、转化率 |

### 5.3 京东 商家后台（后续扩展）

| 页面 | URL 匹配 | 要提取的数据 |
|------|---------|------------|
| 商品管理 | `shop.jd.com/goods*` | 商品ID、标题、价格、销量 |
| 订单管理 | `shop.jd.com/order*` | 订单号、金额、时间 |

### 5.4 抖音 电商后台（后续扩展）

| 页面 | URL 匹配 | 要提取的数据 |
|------|---------|------------|
| 商品管理 | `fxg.jinritemai.com/product*` | 商品ID、标题、价格、销量 |
| 订单管理 | `fxg.jinritemai.com/order*` | 订单号、金额、时间 |

---

## 6. 开发工作流

### 6.1 新增一个页面的解析器

```
1. Python 脚本打开目标页面（通过 CDP 导航）
2. 执行 Runtime.evaluate → 保存 HTML 到 html_snapshots/
3. 分析 HTML 结构，找到目标数据所在的 DOM 节点
4. 编写 data_extractor 函数（CDP 注入的 JS）
5. 运行 → 验证提取结果
6. 结果正确 → 提交代码 + 更新本文档（如需要）
7. 删除过程快照
```

### 6.2 文档同步规则

**每完成一个功能，必须核对 `docs/ARCHITECTURE.md`：**

- 代码实现 = 文档描述 → ✅ 继续
- 代码实现 ≠ 文档描述 → ⚠️
  - 代码是对的 → **更新文档**，让文档追上代码
  - 文档是对的 → **修改代码**，让代码对齐文档
- 每次更新文档/代码后 → git commit 一起提交

---

## 7. 数据库设计

直接复用 `电商BI分析/03-数据表设计方案.md` 的星型模型：

- `dim_date` — 日期维度（预生成 2023-2027）
- `dim_product` — 产品维度（product_id, name, brand, category, platform）
- `dim_shop` — 店铺维度（shop_id, name, platform, shop_type）
- `fact_sales` — 销售事实表（date_id, product_id, shop_id, sales_amount, sales_volume, order_count）

---

## 8. 实现计划

### Phase 1: 项目骨架搭建 ✅
- [x] 创建目录结构
- [x] 写入 ARCHITECTURE.md
- [x] Python 引擎基础（config, browser/manager, cdp_client, navigator）
- [x] 数据库初始化（init_db, schema.sql, connection.py）

### Phase 2: 淘宝卖家中心 — 出售中的商品（首个功能，跑通全流程）
- [x] 浏览器连接 + 导航到卖家中心
- [x] 商品列表数据提取 JS（多策略：data-id / table / container fallback）
- [x] 数据清洗 pipeline（cleaner / normalizer）
- [x] PostgreSQL 写入（dim_product / dim_shop / fact_sales upsert）
- [ ] 端到端验证（需要连到实际淘宝卖家中心页面测试提取效果）

### Phase 3: 淘宝卖家中心 — 订单管理
- [ ] 订单列表数据提取
- [ ] 端到端验证

### Phase 4: 扩展更多平台
- [ ] 拼多多商家后台
- [ ] 京东商家后台
- [ ] 抖音电商后台

### Phase 5: BI 集成
- [ ] Metabase 仪表盘对接
