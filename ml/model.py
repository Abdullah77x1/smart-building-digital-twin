"""A SINGLE multi-task network: shared layers, three prediction heads."""
import numpy as np
import torch
from torch import nn


class MultiTaskModel(nn.Module):
    def __init__(self, feature_count: int, hidden_size: int = 64):
        super().__init__()
        self.shared = nn.Sequential(
            nn.Linear(feature_count, hidden_size),
            nn.ReLU(),
            nn.Linear(hidden_size, hidden_size),
            nn.ReLU(),
        )
        self.hvac_head = nn.Linear(hidden_size, 4)
        self.temperature_head = nn.Linear(hidden_size, 4)
        self.occupancy_head = nn.Linear(hidden_size, 4)

    def forward(self, x):
        shared = self.shared(x)
        return torch.cat((self.hvac_head(shared), self.temperature_head(shared), self.occupancy_head(shared)), dim=1)


def save_checkpoint(path, model, features, targets, x_mean, x_std, y_mean, y_std, hidden_size):
    torch.save({
        "model_state": model.state_dict(),
        "features": features,
        "targets": targets,
        "hidden_size": hidden_size,
        "x_mean": torch.tensor(x_mean, dtype=torch.float32),
        "x_std": torch.tensor(x_std, dtype=torch.float32),
        "y_mean": torch.tensor(y_mean, dtype=torch.float32),
        "y_std": torch.tensor(y_std, dtype=torch.float32),
    }, path)


def load_checkpoint(path):
    ckpt = torch.load(path, map_location="cpu", weights_only=True)
    model = MultiTaskModel(len(ckpt["features"]), ckpt["hidden_size"])
    model.load_state_dict(ckpt["model_state"])
    model.eval()
    return model, ckpt


@torch.no_grad()
def predict(model, ckpt, raw_inputs, batch_size=8192):
    x = np.asarray(raw_inputs, dtype=np.float32)
    xmean = ckpt["x_mean"].numpy()
    xstd = ckpt["x_std"].numpy()
    ym = ckpt["y_mean"].numpy()
    ys = ckpt["y_std"].numpy()
    x_scaled = (x - xmean) / xstd
    pieces = []
    for i in range(0, len(x_scaled), batch_size):
        pieces.append(model(torch.from_numpy(x_scaled[i:i + batch_size])).numpy())
    out = np.concatenate(pieces, axis=0) * ys + ym
    out[:, 0:4] = np.maximum(out[:, 0:4], 0)
    out[:, 8:12] = np.clip(out[:, 8:12], 0, 15)
    return out
