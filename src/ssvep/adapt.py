"""M3: adaptation of a trained network to a new user WITHOUT labels (test-time adaptation).

None of these functions takes a label. They change the batch-normalisation layers only:
  A1  adapt_statistics: the stored mean and variance become those of the user's unlabelled trials
  A2  adapt_entropy:    A1, then the scale and shift are moved to lower the entropy of the predictions
"""
from __future__ import annotations

import copy

import torch
from torch import nn


def _bn_layers(model):
    return [m for m in model.modules() if isinstance(m, nn.BatchNorm2d)]


def entropy(logits):
    """Mean over trials of - sum over classes of p * log(p)."""
    logp = torch.log_softmax(logits, dim=1)
    return -(logp.exp() * logp).sum(dim=1).mean()


def batches(n_trials: int, size: int, seed=None):
    """Trial indices in batches. seed=None keeps the given order (trials sorted by block: one batch = one block);
    with a seed the trials are shuffled first."""
    perm = torch.arange(n_trials) if seed is None else torch.randperm(n_trials, generator=torch.Generator().manual_seed(seed))
    return [perm[i:i + size] for i in range(0, n_trials, size)]


def adapt_statistics(model, x, batch: int = 12, seed=None):
    """A1. Returns a copy of the model whose batch-normalisation statistics are those of the trials x
    (plain average over the batches). Weights, scale and shift are untouched."""
    model = copy.deepcopy(model)
    x = torch.as_tensor(x, dtype=torch.float32)
    model.eval()
    for bn in _bn_layers(model):
        bn.reset_running_stats()
        bn.momentum = None                                   # cumulative average over the batches
        bn.train()
    with torch.no_grad():
        for idx in batches(len(x), batch, seed):
            model(x[idx])
    model.eval()
    return model


def adapt_entropy(model, x, batch: int = 12, seed=None, lr: float = 1e-3):
    """A2. A1, then one gradient step per batch on the batch-normalisation scale and shift to lower the entropy
    of the predictions on the unlabelled trials x (one pass). Everything else stays fixed."""
    model = adapt_statistics(model, x, batch, seed)
    x = torch.as_tensor(x, dtype=torch.float32)
    for p in model.parameters():
        p.requires_grad_(False)
    params = [p for bn in _bn_layers(model) for p in (bn.weight, bn.bias)]
    for p in params:
        p.requires_grad_(True)
    opt = torch.optim.Adam(params, lr=lr)
    model.eval()                                             # statistics of A1 are used as they will be at test
    for idx in batches(len(x), batch, seed):
        opt.zero_grad()
        entropy(model(x[idx])).backward()
        opt.step()
    for p in params:
        p.requires_grad_(False)
    return model


def online(model, blocks, lr: float = 1e-3):
    """Online variant: the blocks arrive one after the other; each block is predicted first, then used (its
    trials join the statistics, and one entropy step is taken). Returns the predictions, block by block.
    blocks: list of arrays (trials, bands, channels, samples), without labels."""
    model = copy.deepcopy(model)
    for p in model.parameters():
        p.requires_grad_(False)
    params = [p for bn in _bn_layers(model) for p in (bn.weight, bn.bias)]
    for p in params:
        p.requires_grad_(True)
    opt = torch.optim.Adam(params, lr=lr)
    seen, predictions = [], []
    for x in blocks:
        x = torch.as_tensor(x, dtype=torch.float32)
        model.eval()
        with torch.no_grad():
            predictions.append(model(x).argmax(dim=1).numpy())          # decided before the block is used
        seen.append(x)
        for bn in _bn_layers(model):
            bn.reset_running_stats()
            bn.momentum = None
            bn.train()
        with torch.no_grad():
            for past in seen:                                            # statistics of all the user's trials so far
                model(past)
        model.eval()
        opt.zero_grad()
        entropy(model(x)).backward()
        opt.step()
    return predictions
