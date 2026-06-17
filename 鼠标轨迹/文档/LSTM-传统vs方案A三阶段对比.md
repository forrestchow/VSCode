# 传统 LSTM vs 方案 A：三阶段逐项对比

## 一、数据准备阶段

### 传统 LSTM

录制时需要采集：

```
采集卡帧  ──CV判断──▶  screen_start, screen_target, action_type
pynput    ─────────────▶  physical_trajectory

一条样本 = {screen_start, screen_target, action_type, physical_trajectory}
```

**数据准备工作量：**
- 录一次操作
- 用点击事件自动切段
- 离线 CV 标每段的 action_type
- 坐标归一化到 [0, 1]
- 长度统一填充/截断到固定步数

**不需要做的事情：**
- 不需要从采集卡帧里跟踪光标
- 不需要对齐画面轨迹和物理轨迹
- 不需要处理两套坐标系的偏差

**数据量需求：** 几百到几千条样本即可训练一个可用的 LSTM。

### 方案 A

录制时需要采集：

```
采集卡帧  ──CV判断──▶  screen_start, screen_target, action_type
                        └─▶ 模板匹配跟踪光标 ▶  screen_cursor_trajectory
pynput    ─────────────▶  physical_trajectory

一条样本 = {screen_start, screen_target, action_type, 
            physical_trajectory, screen_cursor_trajectory}    ← 多了一个字段
```

**数据准备工作量（多了以下步骤）：**

步骤 1：录制时时间戳必须在同一时钟

```
pynput 事件时间戳:  time.perf_counter()
采集卡帧时间戳:     time.perf_counter()（同时刻记录，不能两个各自独立计时）
```

步骤 2：逐帧模板匹配跟踪光标

```
for each frame in 该段的帧序列:
    cursor_pos = template_match(frame, cursor_template)  
    # 光标图标通常固定，匹配准确度很高
    screen_cursor_trajectory.append((ts, cursor_pos))
```

步骤 3：两条轨迹的逐点对齐

```
physical_trajectory 来自 pynput event stream:   约 125~250 个点/秒
screen_cursor_trajectory 来自采集卡帧:          60 个点/秒（60fps）

两个序列长度不同 → 需要插值对齐

对齐方法:
  1. 以物理轨迹的时间戳为基准（密度高）
  2. 对每个物理点的时间戳，在 screen_cursor 序列中找到最近邻的两帧做线性插值
  3. 使两个序列长度相同，时间戳一一对应
```

**对齐的代码示例：**

```python
import numpy as np
from scipy.interpolate import interp1d

# physical_ts: [0, 8, 16, 24, ...] ms，密集
# screen_ts: [0, 16.6, 33.3, 50, ...] ms，稀疏（60fps）
# screen_x: [820, 818, 812, 805, ...]

# 插值对齐到物理轨迹的时间轴
f_x = interp1d(screen_ts, screen_x, kind='linear', bounds_error=False)
aligned_screen_x = f_x(physical_ts)

f_y = interp1d(screen_ts, screen_y, kind='linear', bounds_error=False)
aligned_screen_y = f_y(physical_ts)

# 现在 screen_cursor_trajectory 和 physical_trajectory 长度一致
```

### 对比表：数据准备

| 环节 | 传统 LSTM | 方案 A | 方案 A 额外成本 |
|------|----------|--------|---------------|
| 原始录制 | 采集卡帧 + pynput | 采集卡帧 + pynput | 无 |
| 端点提取 | CV 检测 | CV 检测 | 无 |
| action_type 标注 | 离线 CV | 离线 CV | 无 |
| 光标跟踪 | 不需要 | **需要做** | 开发模板匹配 + 人工验证质量 |
| 轨迹对齐 | 不需要 | **需要做** | 插值对齐代码 + 对齐质量检查 |
| 标注后检查 | 看终点是否对准即可 | 还要检查光标跟踪有没有偏移 | 多一道 QC |
| 总工作量基准 | 1× | ~1.5× ~ 2× | 主要是光标跟踪和对齐 |

---

## 二、模型训练阶段

### 传统 LSTM

```
输入向量 (88维):
  [start_x, start_y, target_x, target_y, action_embedding(16d), speed_embedding(8d)]

模型:
  输入层(88) → LSTM(256, 2层) → MDN物理头 → 物理轨迹点序列

Loss:
  Loss_p = 负对数似然(预测的物理轨迹分布, 真实的物理轨迹坐标)

梯度回传路径:
  Loss_p → 物理头 → LSTM编码器 → 输入层

只更新一个输出头的参数。
参数空间: 编码器参数 + 物理头参数
```

**训练过程关注点：**
- 只关注"物理轨迹是否像人类"
- 不关心物理轨迹到了画面上会变成什么样
- 模型学到的是：`screen_coords → physical_movement` 的纯黑盒映射

**验证时观察的指标：**
```
验证 Loss_p ↓
生成轨迹的 DTW 距离 ↓
终点误差 ↓
速度分布是否像人类
```

### 方案 A

```
输入向量 (88维):
  [start_x, start_y, target_x, target_y, action_embedding(16d), speed_embedding(8d)]

模型:
  输入层(88) → LSTM(256, 2层) → 物理MDN头 → 物理轨迹点序列
                                  画面MDN头 → 画面轨迹点序列

Loss:
  Loss_p = 负对数似然(预测物理轨迹分布, 真实物理轨迹坐标)
  Loss_s = 负对数似然(预测画面轨迹分布, 真实画面轨迹坐标)
  
  total_loss = Loss_p + λ * Loss_s

梯度回传路径:
  total_loss → 物理MDN头 → LSTM编码器 (梯度来自 Loss_p)
            → 画面MDN头 → LSTM编码器 (梯度来自 Loss_s)
                            ↑
                    编码器同时接收两路梯度，更新参数时两者相互约束
```

**训练过程关注点：**
- 主关注：物理轨迹是否像人类（Loss_p）
- 辅助关注：物理轨迹发出的信号，经游戏变换后在画面上是否匹配（Loss_s）
- 模型学到的是：`screen_coords → physical_movement`，**同时通过副任务被迫理解了"物理→画面"的变换**

**验证时观察的指标：**
```
验证 Loss_p ↓（主指标）
验证 Loss_s ↓（副指标，正常情况下应该同步下降）
Loss_s 下降慢于 Loss_p → λ 偏小，可以调大
Loss_s 下降但 Loss_p 不再下降 → λ 偏大，画面轨迹过度约束了物理任务
DTW 距离 ↓
终点误差 ↓
速度分布
```

### 两种 Loss 的相互影响

```
情况 1: Loss_p 下降，Loss_s 也下降（理想状态）
  → 编码器学到了一个好的表示，同时有利于两个任务
  → 画面轨迹的正则化生效

情况 2: Loss_p 下降，Loss_s 不降反升
  → 编码器虽然在拟合物理轨迹，但丢失了画面变换的理解
  → 可能是 λ 太小（画面接近不起作用），也可能是两个任务之间存在冲突
  
情况 3: Loss_s 下降，Loss_p 不降反升（灾难）
  → 编码器被画面任务带偏了
  → λ 太大，赶紧调小
```

### 是否需要做数据增强

| 增强方法 | 传统 LSTM | 方案 A | 原因 |
|---------|----------|--------|------|
| 终点微偏移 ±3px | 推荐 | 推荐 | 两者都受益 |
| 时间轴缩放 ±10% | 推荐 | 推荐 | 速度多样性 |
| 随机丢弃中间点 | 推荐 | **不推荐** | 方案 A 需要画面轨迹与物理轨迹对齐，丢弃会破坏配对 |
| 起点偏移 | 推荐 | **需小心** | 起点变了，画面轨迹也必须同步偏移，两条轨迹要一起变化 |

方案 A 的数据增强要**同步变换两个序列**——不能单独增强其中一个。

### 对比表：模型训练

| 环节 | 传统 LSTM | 方案 A |
|------|----------|--------|
| 模型参数 | 编码器 + 物理头 | 编码器 + 物理头 + **画面头** |
| 参数量 | M | ~M + 画面头参数（增加约 20%~30%） |
| Loss 数 | 1 个 | 2 个 |
| 需要调的超参数 | lr, batch, hidden size | lr, batch, hidden size + **λ** |
| 训练收敛参考 | Loss_p 降到 ~0.1 左右 | Loss_p 和 Loss_s 同步下降 |
| 梯度冲突风险 | 无 | 存在（两个 Loss 可能相互撕扯） |
| 训练前先做实验 | 不需要 | **推荐先做一个单样本过拟合实验**（λ=0.5），看两个 Loss 是否都能降到接近 0 |
| 数据增强灵活性 | 高 | 低（两个序列必须同步做） |

---

## 三、推理阶段

### 传统 LSTM

```
输入: screen_start, screen_target, action_type, speed_category
      ↓
ONNX 推理（单次前向，< 5ms）
      ↓
输出: [(dx1,dy1), (dx2,dy2), ..., (dxn,dyn)]  物理相对位移序列
      ↓
KMBox 发送 → PC A
```

模型加载：一个 ONNX 文件，约 2~5MB。

### 方案 A

```
输入: screen_start, screen_target, action_type, speed_category
      ↓
ONNX 推理（与左侧完全相同）
      ↓
物理头输出: [(dx1,dy1), (dx2,dy2), ..., (dxn,dyn)]  物理相对位移序列
      ↓
KMBox 发送 → PC A
```

模型加载：也可以只保留物理头的 ONNX 文件（约 2~5MB）。画面头在导出时被剪掉。

**推理时方案 A 和传统 LSTM 没有任何区别**——画面头不存在，计算路径完全一致。

### 对比表：推理

| 环节 | 传统 LSTM | 方案 A |
|------|----------|--------|
| ONNX 大小 | 2~5 MB | 相同（导出去掉画面头） |
| 推理延迟 | < 5ms CPU | 相同 |
| 内存占用 | 相同推理图 | 相同 |
| 是否有画面头 | 无 | 训练时有，推理时无 |
| 推理代码 | 相同 | 相同 |

**方案 A 推理时就是传统 LSTM。两个方案在推理时无法区分。**

---

## 四、总对比表：三阶段

| 阶段 | 维度 | 传统 LSTM | 方案 A | 差异影响 |
|------|------|----------|--------|---------|
| **数据准备** | 画面轨迹 | 不需要 | **需要** | 方案 A 多 0.5~1 倍工作 |
| | 轨迹对齐 | 不需要 | **需要** | 涉及模板匹配和插值代码 |
| | 检查成本 | 低 | 中 | 多一道 QC |
| **训练** | 模型参数 | 1 个输出头 | 2 个输出头 | 方案 A 多 20~30% 参数 |
| | Loss | 1 个 | 2 个 | 多一个 λ 要调 |
| | 收敛难度 | 低 | 中 | 存在梯度冲突风险 |
| | 训练时间 | 1× | 1.2~1.5× | 多一个头要多迭代 |
| **推理** | ONNX | 同 | **完全一致** | **无差异** |

**结论：方案 A 的成本全在数据准备和训练调参，推理时零成本差异。画面轨迹信息全部被吸收进编码器权重里，推理时不额外消耗任何资源。**
