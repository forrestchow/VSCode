"""
LSTM 鼠标轨迹生成模型

训练时：Teacher Forcing + batch 处理
推理时：Autoregressive 逐步生成
"""

import torch
import torch.nn as nn


class TrajectoryLSTM(nn.Module):
    """
    输入条件向量 [start_x, start_y, end_x, end_y] → 生成 (dx, dy) 序列
    """

    def __init__(self, hidden_size=128, num_layers=2, dropout=0.2):
        super().__init__()
        self.hidden_size = hidden_size
        self.num_layers = num_layers

        # 条件嵌入
        self.condition_embed = nn.Sequential(
            nn.Linear(4, 32),
            nn.ReLU(),
            nn.Linear(32, 32),
            nn.ReLU(),
        )

        # LSTM
        self.lstm = nn.LSTM(
            input_size=2 + 32,       # prev_delta(2) + condition_emb(32)
            hidden_size=hidden_size,
            num_layers=num_layers,
            dropout=dropout if num_layers > 1 else 0.0,
            batch_first=True,
        )

        # 输出头
        self.output_head = nn.Sequential(
            nn.Linear(hidden_size, 64),
            nn.ReLU(),
            nn.Linear(64, 2),        # (dx, dy)
        )

    def forward(self, condition, deltas=None, max_steps=200):
        """
        Args:
            condition: (batch, 4)  归一化起点终点
            deltas:    (batch, T, 2)  真实 delta 序列（训练时）
            max_steps: int  推理时最大步数

        Returns:
            (batch, T, 2)  预测的 delta 序列
        """
        if deltas is not None:
            return self._train_forward(condition, deltas)
        else:
            return self._inference_forward(condition, max_steps)

    def _train_forward(self, condition, deltas):
        """
        Teacher Forcing: 整序列一次前向
        condition: (B, 4)
        deltas:    (B, T, 2)
        """
        B, T, _ = deltas.shape

        # 条件嵌入 → 扩展到每个时间步
        cond_emb = self.condition_embed(condition)          # (B, 32)
        cond_emb = cond_emb.unsqueeze(1).expand(-1, T, -1) # (B, T, 32)

        # Teacher Forcing: 前一步的真实 delta 作为输入
        # t=0 时前一步 delta = (0, 0)
        prev_delta = torch.cat([
            torch.zeros(B, 1, 2, device=deltas.device),
            deltas[:, :-1, :],
        ], dim=1)  # (B, T, 2)

        # LSTM 输入
        lstm_input = torch.cat([prev_delta, cond_emb], dim=-1)  # (B, T, 34)

        lstm_out, _ = self.lstm(lstm_input)     # (B, T, hidden)
        pred = self.output_head(lstm_out)       # (B, T, 2)

        return pred

    def _inference_forward(self, condition, max_steps=200):
        """
        Autoregressive 推理: 逐步生成
        condition: (B, 4)
        """
        B = condition.shape[0]
        device = condition.device

        cond_emb = self.condition_embed(condition)  # (B, 32)

        # 初始化 LSTM 状态
        h = torch.zeros(self.num_layers, B, self.hidden_size, device=device)
        c = torch.zeros(self.num_layers, B, self.hidden_size, device=device)

        outputs = []
        prev = torch.zeros(B, 2, device=device)  # (0, 0)

        for t in range(max_steps):
            lstm_input = torch.cat([prev, cond_emb], dim=-1).unsqueeze(1)  # (B, 1, 34)
            lstm_out, (h, c) = self.lstm(lstm_input, (h, c))
            pred = self.output_head(lstm_out.squeeze(1))  # (B, 2)
            outputs.append(pred)
            prev = pred  # 自回归

        return torch.stack(outputs, dim=1)  # (B, max_steps, 2)


# ── 工具函数 ──

def create_model(hidden_size=128, num_layers=2, dropout=0.2):
    """工厂函数"""
    return TrajectoryLSTM(
        hidden_size=hidden_size,
        num_layers=num_layers,
        dropout=dropout,
    )


def count_parameters(model):
    """统计参数量"""
    return sum(p.numel() for p in model.parameters() if p.requires_grad)
