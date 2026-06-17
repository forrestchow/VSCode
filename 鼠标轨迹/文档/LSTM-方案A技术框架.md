# LSTM 方案 A：技术框架详解

## 一、逻辑总览

```
训练时:
  录制人类操作 → 同时获得[物理轨迹, 画面轨迹, 场景标签]
                      ↓
               对齐后作为一条训练样本
                      ↓
                LSTM 共享编码器 + 两个输出头
                      ↓
                物理Loss + 画面Loss → 联合训练

推理时:
  CV检测 + 决策引擎 → 画面坐标 + action_type
                      ↓
                LSTM 共享编码器 + 物理头(只有这一个)
                      ↓
                物理轨迹 → KMBox → PC A
```

---

## 二、训练数据样本结构

每一条样本代表一次"从 A 点移动到 B 点并完成点击"的完整动作。

### 输入字段

| 字段 | 类型 | 来源 | 说明 |
|------|------|------|------|
| `screen_start` | (x, y) | 录制帧光标位置 | 轨迹开始时鼠标在画面上的坐标 |
| `screen_target` | (x, y) | 录制帧检测目标位置 | 终点在画面上的坐标 |
| `action_type` | int (categorical) | 离线 CV 扫帧判断 | 如 0=walk, 1=approach_npc, 2=menu_select... |
| `speed_category` | int | 人工标注或默认 normal | 0=slow, 1=normal, 2=fast |

### 输出字段

| 字段 | 类型 | 说明 | 哪个 Loss 用 |
|------|------|------|-------------|
| `physical_trajectory` | [(t, x, y), ...] | pynput 录的物理鼠标轨迹 | **Loss_p** |
| `screen_cursor_trajectory` | [(t, x, y), ...] | 采集卡帧跟踪的光标轨迹 | **Loss_s** |

### 一条完整样本

```python
{
    "screen_start": (820, 210),
    "screen_target": (500, 300),
    "action_type": 1,           # approach_npc
    "speed_category": 1,        # normal

    "physical_trajectory": [
        (0.000, 820, 210),      # t=0ms, 起点
        (0.008, 812, 208),      # t=8ms
        (0.016, 800, 205),      # t=16ms
        ...                     # 中间数十到数百个点
        (1.234, 500, 300),      # t=1234ms, 终点（点击发生）
    ],

    "screen_cursor_trajectory": [
        (0.000, 820, 210),      # t=0ms, 与物理轨迹对齐
        (0.008, 818, 208),      # t=8ms, 比物理位移小 = 游戏处理后的结果
        (0.016, 812, 205),
        ...
        (1.234, 500, 300),
    ],
}
```

### 关键约束

`physical_trajectory` 和 `screen_cursor_trajectory` 必须 **严格逐点对齐**——时间戳完全一致，序列长度相同。

对齐方式：采集卡帧和 pynput 事件都用同一个 `time.perf_counter()` 时钟打时间戳。录制完成后按最近邻时间戳配对插值，使两个序列长度一致。

---

## 三、模型架构

### 输入嵌入层

```
screen_start:        (x, y) → Linear(2, 32) → ReLU
screen_target:       (x, y) → Linear(2, 32) → ReLU
action_type:         int → Embedding(num_classes, 16) → 类别嵌入向量
speed_category:      int → Embedding(3, 8) → 类别嵌入向量

输入拼接 → 总向量: [start_32d, target_32d, action_16d, speed_8d] = 88维
```

### LSTM 编码器

```
输入: 每个时间步喂入 88 维条件向量（在每一步重复广播）
架构: LSTM(hidden_size=256, num_layers=2, dropout=0.2)
输出: 每个时间步的 hidden state → 256维
```

也可以采用另一种方式：条件向量只在初始状态喂入，然后 LSTM 自回归生成后续状态。这取决于实现。两种在 ML 领域都常见。

#### 方式 1：条件向量逐时间步广播（推荐）

```
每个时间步 t:
  input_t = concat(hidden_t, condition_vec)   # condition_vec 每步都一样
  → LSTM_step → 下一个 hidden
```

更稳定，解码器不会漂移。

#### 方式 2：条件向量只初始化

```
h0 = MLP(condition_vec)   → 初始 hidden
c0 = zeros
第一时间步: input_1 = (start_x, start_y)
后续步:    input_t = (prev_x, prev_y)
```

更常见于 Seq2Seq 的 Teacher Forcing，但对你的场景没有优势。

**推荐方式 1。**

### 两个输出头

```
LSTM hidden state (256维)
        │
    ┌───┴───┐
    │       │
 物理头   画面头
 (MDN)    (MDN)
    │       │
    ▼       ▼
物理轨迹  画面轨迹
```

每个输出头都是一个 MDN（Mixture Density Network），结构相同：

```
Linear(256, 128) → ReLU → Linear(128, n_mixtures * 5)
      ↑               ↑             ↑
                              每个混合分量输出 (μx, μy, σx, σy, π)
```

MDN 输出的是概率分布，不是确定值。每个时间步预测 5 个混合分量：
- `πᵢ`：分量权重（归一化后和为 1）
- `μxᵢ, μyᵢ`：该分量的均值（即最可能的坐标位置）
- `σxᵢ, σyᵢ`：该分量的方差（不确定性）

训练时通过 **负对数似然（NLL）** 计算 Loss，推理时从混合分布中采样。

---

## 四、两个 Loss 详解

### Loss_p：物理轨迹损失（主任务）

```python
# 对物理轨迹的每一个时间步 t
# 模型输出: mixture_weights, means, variances

Loss_p_t = -log( Σ_i π_i * N(y_true_t | μ_i, σ_i) )
      ↑              ↑             ↑
   负对数似然     加权混合    真实位置在该分量下的概率

Loss_p = mean(Loss_p_t for t in 1..T)
```

**物理意义**：模型认为"手应该这么动"的概率有多大。

### Loss_s：画面轨迹损失（辅助任务结构完全一样）

```python
Loss_s_t = -log( Σ_i π_i · N(screen_gt_t | μ_i, σ_i) )

Loss_s = mean(Loss_s_t for t in 1..T)
```

**物理意义**：模型认为"这个动作在画面上应该呈现为这样"的概率有多大。

### 联合 Loss

```python
total_loss = Loss_p + λ * Loss_s
```

λ 是一个超参数，控制画面轨迹对训练的约束强度。

### 梯度回传路径

```
total_loss.backward()

梯度流向:
     total_loss
      /      \
Loss_p_grad   λ * Loss_s_grad
    │              │
    ▼              ▼
物理头 ← 共享编码器 → 画面头
      ↑           ↑
   物理头梯度 + λ * 画面头梯度 = 编码器最终梯度
```

编码器的参数更新同时被两个任务影响。这就是"额外约束"的本质——共享编码器不仅要让物理轨迹准，还不能让画面轨迹预测偏离。

---

## 五、训练管线

### 预处理

```
pynput 事件 + 采集卡帧 → 时间戳对齐 → 按点击事件切段
                                       ↓
                               模板匹配跟踪每帧光标 → screen_cursor_trajectory
                                       ↓
                               离线 CV 判断每段 action_type
                                       ↓
                               标准化: 坐标归一化到 [0, 1]（除以分辨率）
                                       ↓
                               长度统一: 所有轨迹填充/截断到固定长度 N（如 256 步）
```

### 数据增广

```
- 终点加微小随机偏移 (±3px)
- 时间轴整体缩放 (±10%)
- 随机遮挡部分中间点（模拟 KMBox 丢帧）
```

### 训练超参数

| 参数 | 建议值 |
|------|--------|
| LSTM hidden | 256 |
| LSTM layers | 2 |
| MDN mixtures | 5 |
| λ | 0.1 ~ 0.5（先 0.1，验证集上调） |
| batch size | 32 ~ 64 |
| learning rate | 1e-3（Adam） |
| 输入序列长度 N | 256（>95% 轨迹长度） |
| 输出维度 | (N, 2) 坐标序列 |

### 训练/验证/测试划分

70% 训练 / 15% 验证 / 15% 测试。按 session 切分（同一次录制的所有段不能跨分集），防止数据泄露。

### 评估指标

| 指标 | 意义 | 观测对象 |
|------|------|---------|
| NLL loss_p | 物理轨迹拟合质量 | 验证集 |
| NLL loss_s | 画面轨迹拟合质量 | 验证集 |
| DTW 距离 | 生成轨迹与真实轨迹的形状相似度 | 测试集 |
| 终点误差 (px) | 点击精度 | 测试集 |
| 速度分布 KL 散度 | 生成轨迹的速度曲线像不像人类 | 测试集 |

---

## 六、推理管线

```
采集卡帧 → CV模块(YOLO+OCR+模板匹配) → GameState
                                             ↓
决策引擎(if-else状态机)
  - 检测到NPC → category=approach_npc, target=该NPC坐标
  - 检测到对话框 → category=menu_select, target=选项坐标
  - 默认 → category=walk
      ↓
Action = { category, target_x, target_y, speed }
      ↓
LSTM 推理:
  1. screen_start = CV检测到的当前光标位置
  2. screen_target = action.target
  3. action_type = action.category（转为 int index）
  4. 拼接 88 维条件向量
  5. LSTM 自回归生成（只用物理头）
  6. 输出物理轨迹序列
      ↓
KMBox 发送:
  1. delta 检查：单帧超过阈值则拉伸时间
  2. 时序抖动：HID 发送间隔加 ±10% 随机
  3. 逐点发送物理坐标
      ↓
CV 兜底校正:
  模板匹配跟踪光标 → 终点偏差 > 阈值 → 补发修正段
```

推理时画面轨迹头不存在。模型内存里只有物理头的权重，ONNX 导出时可以剪掉画面头。

---

## 七、ONNX 导出

```python
# 导出推理用模型（只保留物理头）
class LSTMModelInference(nn.Module):
    def __init__(self, encoder, physical_head):
        super().__init__()
        self.encoder = encoder
        self.physical_head = physical_head

    def forward(self, condition):
        # condition = 88维向量
        hidden = self.encoder.init_hidden()
        trajectory = []
        for t in range(max_steps):
            _, hidden = self.encoder(condition, hidden)
            delta = self.physical_head(hidden)
            # delta 是 (dx, dy) 或 (x, y)
            trajectory.append(delta)
        return torch.stack(trajectory)
```

ONNX 导出后推理 < 5ms（CPU），可以作为 `ort.InferenceSession` 调用。

---

## 八、方案 A 与传统 LSTM 的对比总结

```
               传统 LSTM                         方案 A
              ──────────                       ──────────
数据要求        物理轨迹 + action_type           物理轨迹 + 画面轨迹 + action_type

对齐工作        不需要                            需要逐帧对齐两个轨迹

模型输出        1 个头（物理）                    2 个头（物理 + 画面）

Loss           Loss_p                            Loss_p + λ * Loss_s

模型学的        直接从端点到物理轨迹                除了端点到物理轨迹，还学到了端点到画面轨迹，
映射            的隐式映射                        而画面轨迹与物理轨迹之间的变换关系也编码了进去

推理延迟        1×前向                           1×前向（相同，画面头被丢弃）

数据成本        低                               高（需逐帧跟踪光标对齐）

收益            —                                多了一个正则化约束，模型理解"游戏变换"
```

方案 A 用额外的数据准备成本（画面轨迹对齐），换取了模型对游戏变换的隐式理解。这个理解不是显式建模的，而是通过**共享编码器 + 辅助 Loss 约束**让模型在训练过程中自己学出来的。
