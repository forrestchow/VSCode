# 梦幻西游 LSTM 鼠标轨迹 — 偏移与实时性讨论

## 问题

如果游戏对于鼠标最终结果没有影响，只是过程中有类似延迟的效果，那就没问题。
另一种可能就是存在偏移，那么应该如何解决偏移呢？是不是要实时计算？
LSTM 模型的轨迹，是不是实时计算的？

## 回答

### 一、偏移问题：要看偏移的性质

先做一个小实验确认偏移类型：

让 KMBox 发一个固定坐标，例如 `(500, 300)` → 在 B 电脑上观察光标实际落点 → 重复 10 次。

| 现象 | 原因 | 处理方式 |
|------|------|---------|
| 每次都落在 `(500, 300)`，无偏移 | 游戏只平滑路径，不碰终点 | 不用管，直接用 |
| 每次都落在同一个偏的位置，如 `(495, 298)` | **固定系统偏移**（分辨率/DPI 映射问题） | 做一次**标定映射**，不需要实时计算 |
| 每次落点不一样，如有时 `(497, 301)` 有时 `(503, 299)` | **游戏随机扰动**（反脚本抖动） | 需要闭环反馈处理 |

#### 固定偏移的处理（静态校准）

校准一次就够了，不需要实时算：

```
校准过程：
  KMBox 发 (100, 100) → 实测光标落在 (95, 98)
  KMBox 发 (500, 100) → 实测光标落在 (498, 98)
  KMBox 发 (100, 500) → 实测光标落在 (95, 503)
  → 算出映射矩阵 M

部署时：
  LSTM 输出 (x, y)
  → 通过 M 映射成 (x', y')
  → KMBox 发送 (x', y')
  → 预期光标精确到达目标
```

这种映射用仿射变换（3 个点就能算）或者线性回归就够了，不需要深度学习。

#### 随机扰动的处理

比较棘手，需要：
1. 先确认扰动幅度和规律（每步随机抖动还是到达终点后抖动？）
2. LSTM 生成目标点后，加 PID 反馈环——但这需要实时光标位置回传（KMBox 双向通信）

不过梦幻西游作为老游戏，基本不太可能做随机扰动。

---

### 二、LSTM 轨迹是实时计算的吗？

**是的，典型实现是自回归逐步生成（Autoregressive），每一步都是实时推理。**

```
输入当前坐标 + 目标坐标 → LSTM 推理 → 下一步坐标 → 发送 KMBox
                                                ↓
                                      把新坐标作为输入继续算下一步
                                                ↓
                                          ... 重复直到到达目标
```

每步的时间开销：

| 环节 | 时间 |
|------|------|
| LSTM 推理一次（GPU/CPU） | ~1-5ms |
| 通过网络发给 KMBox | ~1-5ms |
| KMBox 模拟 USB 信号 | ~1ms |
| 游戏更新光标位置 | ~16ms（一帧） |

**总延迟约 20-30ms，人眼几乎无感。**

---

### 三、结合偏移的完整推荐流程

```
位置反馈（可选）------
            ↓              ↓
LSTM →  (x, y) → 校准映射 → (x', y') → KMBox → B电脑 (梦幻西游)
```

**推荐策略**：
1. **先不加偏移补偿**，直接用 LSTM + KMBox 绝对模式跑起来
2. 观察光标是否准确到达目标位置
3. 如果有固定偏移，做一次**静态校准**（不是实时算的）
4. 如果还有随机扰动，再加**基于回读的闭环控制**

---

### 四、PID 反馈环与 LSTM 如何结合

#### 角色分工

```
LSTM = 轨迹规划器（Trajectory Planner）→ 生成"看起来像人"的路径
PID  = 轨迹跟踪器（Trajectory Tracker） → 纠偏，确保实际到达目标
```

- **训练阶段**：只用 LSTM，没有 PID。LSTM 学到的是人类移动的模式（微抖动、加速减速、overshoot 修正等）
- **部署阶段**：LSTM + PID 串联

#### 结合方式一：LSTM 生成完整轨迹，PID 独立跟踪（最简单，推荐入门）

```
部署时：
  LSTM 先算出整条轨迹：P₀ → P₁ → P₂ → ... → Pₙ
                              ↓
  PID 负责逐点跟踪：
    for k = 0 to n:
      KMBox 发 P(k) + PID修正量
      ↓
      读实际位置 feedback
      ↓
      error = P(k) - feedback
      PID修正量 += Kp*error + Ki*∫error + Kd*d(error)/dt
```

LSTM 和 PID 完全解耦，LSTM 生成一次即可。

#### 结合方式二：PID 输出作为 LSTM 的额外输入（更鲁棒）

把 PID 的误差信号**反馈到 LSTM 的输入中**，让 LSTM 知道"上一步有偏差，请调整下一步"。

```
LSTM 每一步的输入变成 6 维向量：
  (current_x, current_y, target_x, target_y, pid_error_x, pid_error_y)
                                              ↑
                                    PID 实时计算的当前偏差

  例子：
  LSTM 上一步输出 P(k) = (500, 300)
  → KMBox 执行后，实际光标落在 P'(k) = (497, 302)
  → PID 算出误差 error = (3, -2)
  → 把这个 error 作为 LSTM 下一步输入的一部分
  → LSTM 生成 P(k+1) 时会自动补偿
```

**优点**：LSTM 能学会"在有偏差的情况下如何调整轨迹"，生成的轨迹更自然
**缺点**：需要 KMBox 支持位置回读（双向通信）

#### 结合方式三：LSTM 输出轨迹增量，PID 做安全限幅（推荐实践）

```
LSTM 输出 delta_x, delta_y（相对移动，不是绝对坐标）
  ↓
PID 检查这个 delta:
  - 如果 delta 在合理范围内 → 直接执行
  - 如果 delta 异常大（模型抽风） → 限幅
  - 如果上一步有 residual error → 叠加修正
  ↓
KMBox 执行
```

PID 作为 LSTM 输出的"护栏"，防止模型生成离谱轨迹。

#### 完整部署循环（以方式一为例）

```
while (还没到达目标) {
  // 1. LSTM 规划下一步去哪
  next_pos = lstm_inference(current_pos, target_pos, history)

  // 2. 读取实际光标位置（需 KMBox 回传或 B 机上报）
  actual_pos = read_actual_position()

  // 3. PID 计算偏差
  error_x = next_pos.x - actual_pos.x
  error_y = next_pos.y - actual_pos.y
  integral_x += error_x * dt
  integral_y += error_y * dt
  derivative_x = (error_x - prev_error_x) / dt
  derivative_y = (error_y - prev_error_y) / dt

  correction_x = Kp*error_x + Ki*integral_x + Kd*derivative_x
  correction_y = Kp*error_y + Ki*integral_y + Kd*derivative_y

  // 4. 发送修正后的目标
  final_pos = (next_pos.x + correction_x, next_pos.y + correction_y)
  kmbox_send_absolute(final_pos)

  // 5. 记录历史
  prev_error = error
  history.push(next_pos)
}
```

#### 总结对比

| | LSTM | PID |
|---|---|---|
| **角色** | 生成人类风格的轨迹 | 纠偏，确保精确到达 |
| **运行阶段** | 训练 + 部署 | 仅部署 |
| **依赖** | 需要大量人类轨迹数据 | 需要实时光标位置反馈 |
| **复杂度** | 高（训练、调参） | 低（调三个参数） |

**最简可行组合**：先用方式一（LSTM 生成完整轨迹 → PID 逐点跟踪），确定偏差规律后再决定是否升级到方式二。
