# ERP（待写）

状态：⬜ 待写

ERP 按**平台**管理：具体 ERP 系统作为该平台下的数据源，目录为 `platforms/erp/<system>/`。

落地时按 `SPEC.md` 的「新增一个平台 / 数据源的落地清单」执行：

1. 确认具体 ERP 系统、账号与鉴权方式；
2. 确认数据分类（订单 / 库存 / 采购 / 财务等）；
3. 定位接口或导出方式；
4. 为每个 ERP 系统建立自己的 `collect.py`、`api.py`、`endpoints.json`、`config.json`；
5. 输出到 `data/erp/<system>/`；
6. 更新 `PLAN.md`、`STRUCTURE.md`。

当前无代码、无接口模板。
