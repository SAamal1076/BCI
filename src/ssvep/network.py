"""M3: a compact EEGNet-type network for one window of sub-band signals, its training, and the folds of people.

Input of the network: (trials, sub-bands, channels, samples), each sub-band of each trial scaled to zero mean
and unit variance. Fixed in the M3 plan; there is no architecture search.
"""
from __future__ import annotations

import numpy as np
import torch
from torch import nn


def folds(people, n_folds: int = 4):
    """Deal the sorted people into n_folds test groups. Returns a list of (train, validation, test) tuples.
    Every 6th training person (starting with the 4th) is a validation person: 8 of 51 for 68 people."""
    people = sorted(people)
    out = []
    for i in range(n_folds):
        test = people[i::n_folds]
        rest = [p for p in people if p not in test]
        val = rest[3::6]
        train = [p for p in rest if p not in val]
        out.append((tuple(train), tuple(val), tuple(test)))
    return out


def standardise(x):
    """Each sub-band of each trial to zero mean and unit variance. x: (trials, bands, channels, samples)."""
    x = np.asarray(x, dtype=np.float32)
    m = x.mean(axis=(-2, -1), keepdims=True)
    s = x.std(axis=(-2, -1), keepdims=True)
    return (x - m) / np.maximum(s, 1e-12)


class Net(nn.Module):
    """Temporal convolution -> spatial (depthwise) convolution -> separable convolution -> linear layer."""

    def __init__(self, n_bands=3, n_channels=8, n_samples=250, n_classes=12, f1=8, depth=2, f2=16, k1=63, k2=15, dropout=0.5):
        super().__init__()
        self.temporal = nn.Conv2d(n_bands, f1, (1, k1), padding=(0, k1 // 2), bias=False)
        self.bn1 = nn.BatchNorm2d(f1)
        self.spatial = nn.Conv2d(f1, f1 * depth, (n_channels, 1), groups=f1, bias=False)
        self.bn2 = nn.BatchNorm2d(f1 * depth)
        self.pool1 = nn.AvgPool2d((1, 4))
        self.separable_depth = nn.Conv2d(f1 * depth, f1 * depth, (1, k2), padding=(0, k2 // 2), groups=f1 * depth, bias=False)
        self.separable_point = nn.Conv2d(f1 * depth, f2, 1, bias=False)
        self.bn3 = nn.BatchNorm2d(f2)
        self.pool2 = nn.AvgPool2d((1, 8))
        self.drop = nn.Dropout(dropout)
        self.act = nn.ELU()
        self.fc = nn.Linear(f2 * (n_samples // 4 // 8), n_classes)

    def forward(self, x):
        x = self.bn1(self.temporal(x))
        x = self.drop(self.pool1(self.act(self.bn2(self.spatial(x)))))
        x = self.drop(self.pool2(self.act(self.bn3(self.separable_point(self.separable_depth(x))))))
        return self.fc(x.flatten(1))


def n_parameters(model) -> int:
    return sum(p.numel() for p in model.parameters())


@torch.no_grad()
def predict(model, x, batch: int = 256):
    """Scores (trials, classes) in evaluation mode. x: standardised array or tensor."""
    model.eval()
    x = torch.as_tensor(x, dtype=torch.float32)
    return torch.cat([model(x[i:i + batch]) for i in range(0, len(x), batch)]).numpy()


def train(x, y, x_val, y_val, seed: int, max_epochs: int = 60, patience: int = 8, lr: float = 1e-3, batch: int = 64):
    """Train one network. Stops when the validation loss has not improved for `patience` epochs and returns the
    weights of the best epoch. Returns (model, history) with history = list of (epoch, train loss, val loss, val accuracy)."""
    torch.manual_seed(seed)
    model = Net(n_bands=x.shape[1], n_channels=x.shape[2], n_samples=x.shape[3])
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    loss_fn = nn.CrossEntropyLoss()
    x, y = torch.as_tensor(x, dtype=torch.float32), torch.as_tensor(y, dtype=torch.long)
    x_val, y_val = torch.as_tensor(x_val, dtype=torch.float32), torch.as_tensor(y_val, dtype=torch.long)
    order = torch.Generator().manual_seed(seed)
    best, best_state, since, history = np.inf, None, 0, []
    for epoch in range(1, max_epochs + 1):
        model.train()
        total = 0.0
        perm = torch.randperm(len(x), generator=order)
        for i in range(0, len(x), batch):
            idx = perm[i:i + batch]
            opt.zero_grad()
            loss = loss_fn(model(x[idx]), y[idx])
            loss.backward()
            opt.step()
            total += loss.item() * len(idx)
        model.eval()
        with torch.no_grad():
            out = torch.cat([model(x_val[i:i + 256]) for i in range(0, len(x_val), 256)])
            val_loss = float(loss_fn(out, y_val))
            val_acc = float((out.argmax(1) == y_val).float().mean())
        history.append((epoch, total / len(x), val_loss, val_acc))
        if val_loss < best - 1e-6:
            best, since = val_loss, 0
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
        else:
            since += 1
            if since >= patience:
                break
    model.load_state_dict(best_state)
    return model, history
