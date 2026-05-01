"""Layer 1 Research — HMM Regime Engine v1.

Research-only Hidden Markov Model style regime classifier for Itera Dynamics.

This module is intentionally dependency-light. It does not require hmmlearn or
scikit-learn. It implements a small Gaussian HMM with diagonal covariance using
NumPy/Pandas only so the research branch can run in the existing environment.

Purpose:
    Shadow-test probabilistic regime inference against the deterministic Layer 1
    regime engine. This should not replace production regime logic.

Outputs per bar:
    - hmm_state_id
    - hmm_state_label
    - state probabilities
    - expected_return
    - expected_volatility

Design:
    - closed-bar only
    - deterministic initialization
    - no persistence / no side effects
    - fitted only on historical data supplied by the runner
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class HMMConfig:
    n_states: int = 4
    max_iter: int = 75
    tol: float = 1e-5
    random_seed: int = 7
    min_std: float = 1e-6


@dataclass(frozen=True)
class HMMFitResult:
    means: np.ndarray
    variances: np.ndarray
    transition: np.ndarray
    initial: np.ndarray
    feature_columns: list[str]
    state_labels: dict[int, str]
    converged: bool
    iterations: int
    log_likelihood: float


def build_hmm_features(df: pd.DataFrame) -> pd.DataFrame:
    """Create stable, closed-bar features for regime inference."""
    data = df.copy().sort_index()
    close = data["close"].astype(float)

    log_ret = np.log(close / close.shift(1))
    vol_20 = log_ret.rolling(20).std()
    vol_60 = log_ret.rolling(60).std()
    mom_20 = close.pct_change(20)
    mom_60 = close.pct_change(60)
    ema_50 = close.ewm(span=50, adjust=False).mean()
    ema_200 = close.ewm(span=200, adjust=False).mean()
    trend_dist = close / ema_200 - 1.0
    fast_slow = ema_50 / ema_200 - 1.0

    feats = pd.DataFrame(
        {
            "log_return": log_ret,
            "vol_20": vol_20,
            "vol_ratio_20_60": vol_20 / vol_60,
            "mom_20": mom_20,
            "mom_60": mom_60,
            "trend_dist_200": trend_dist,
            "ema_50_200_dist": fast_slow,
        },
        index=data.index,
    )
    feats = feats.replace([np.inf, -np.inf], np.nan).dropna()
    return feats


def _standardize(x: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    mu = x.mean(axis=0)
    sigma = x.std(axis=0)
    sigma = np.where(sigma <= 1e-12, 1.0, sigma)
    return (x - mu) / sigma, mu, sigma


def _logsumexp(a: np.ndarray, axis: int | None = None) -> np.ndarray:
    amax = np.max(a, axis=axis, keepdims=True)
    out = amax + np.log(np.sum(np.exp(a - amax), axis=axis, keepdims=True))
    if axis is not None:
        out = np.squeeze(out, axis=axis)
    return out


def _log_gaussian_diag(x: np.ndarray, means: np.ndarray, variances: np.ndarray) -> np.ndarray:
    n_features = x.shape[1]
    log_probs = []
    for k in range(means.shape[0]):
        var = np.maximum(variances[k], 1e-8)
        lp = -0.5 * (
            n_features * np.log(2.0 * np.pi)
            + np.sum(np.log(var))
            + np.sum(((x - means[k]) ** 2) / var, axis=1)
        )
        log_probs.append(lp)
    return np.vstack(log_probs).T


def _forward_backward(log_emit: np.ndarray, transition: np.ndarray, initial: np.ndarray):
    n, k = log_emit.shape
    log_a = np.log(np.maximum(transition, 1e-12))
    log_pi = np.log(np.maximum(initial, 1e-12))

    alpha = np.zeros((n, k))
    beta = np.zeros((n, k))
    alpha[0] = log_pi + log_emit[0]
    for t in range(1, n):
        alpha[t] = log_emit[t] + _logsumexp(alpha[t - 1][:, None] + log_a, axis=0)

    beta[-1] = 0.0
    for t in range(n - 2, -1, -1):
        beta[t] = _logsumexp(log_a + log_emit[t + 1][None, :] + beta[t + 1][None, :], axis=1)

    ll = float(_logsumexp(alpha[-1], axis=0))
    log_gamma = alpha + beta - ll
    gamma = np.exp(log_gamma)
    gamma = gamma / gamma.sum(axis=1, keepdims=True)

    xi_sum = np.zeros((k, k))
    for t in range(n - 1):
        log_xi = alpha[t][:, None] + log_a + log_emit[t + 1][None, :] + beta[t + 1][None, :] - ll
        xi = np.exp(log_xi)
        xi_sum += xi / max(xi.sum(), 1e-12)

    return gamma, xi_sum, ll


def _init_params(x: np.ndarray, n_states: int, seed: int):
    rng = np.random.default_rng(seed)
    order = np.argsort(x[:, 0])
    buckets = np.array_split(order, n_states)
    means = np.vstack([x[b].mean(axis=0) if len(b) else x[rng.integers(0, len(x))] for b in buckets])
    variances = np.vstack([x[b].var(axis=0) + 1e-3 if len(b) else x.var(axis=0) + 1e-3 for b in buckets])

    transition = np.full((n_states, n_states), 0.05 / max(n_states - 1, 1))
    np.fill_diagonal(transition, 0.95)
    transition = transition / transition.sum(axis=1, keepdims=True)
    initial = np.full(n_states, 1.0 / n_states)
    return means, variances, transition, initial


def fit_hmm_regime(features: pd.DataFrame, config: HMMConfig | None = None) -> tuple[HMMFitResult, pd.DataFrame]:
    """Fit a diagonal Gaussian HMM and return state probabilities."""
    cfg = config or HMMConfig()
    feature_columns = list(features.columns)
    x_raw = features.to_numpy(dtype=float)
    x, mu, sigma = _standardize(x_raw)

    means, variances, transition, initial = _init_params(x, cfg.n_states, cfg.random_seed)
    prev_ll = -np.inf
    converged = False
    ll = -np.inf

    for it in range(1, cfg.max_iter + 1):
        log_emit = _log_gaussian_diag(x, means, variances)
        gamma, xi_sum, ll = _forward_backward(log_emit, transition, initial)

        weights = gamma.sum(axis=0) + 1e-12
        means = (gamma.T @ x) / weights[:, None]
        for k in range(cfg.n_states):
            diff = x - means[k]
            variances[k] = (gamma[:, k][:, None] * diff * diff).sum(axis=0) / weights[k]
        variances = np.maximum(variances, cfg.min_std**2)

        initial = gamma[0]
        transition = xi_sum / np.maximum(xi_sum.sum(axis=1, keepdims=True), 1e-12)
        transition = np.maximum(transition, 1e-8)
        transition = transition / transition.sum(axis=1, keepdims=True)

        if abs(ll - prev_ll) < cfg.tol:
            converged = True
            break
        prev_ll = ll

    # Convert means back to raw-feature units for interpretation.
    raw_means = means * sigma + mu
    raw_vars = variances * (sigma**2)
    labels = label_states(raw_means, feature_columns)

    result = HMMFitResult(
        means=raw_means,
        variances=raw_vars,
        transition=transition,
        initial=initial,
        feature_columns=feature_columns,
        state_labels=labels,
        converged=converged,
        iterations=it,
        log_likelihood=ll,
    )

    probs = pd.DataFrame(gamma, index=features.index, columns=[f"state_{i}_prob" for i in range(cfg.n_states)])
    probs["hmm_state_id"] = gamma.argmax(axis=1)
    probs["hmm_state_label"] = probs["hmm_state_id"].map(labels)
    return result, probs


def label_states(raw_means: np.ndarray, feature_columns: list[str]) -> dict[int, str]:
    """Assign interpretable research labels to fitted HMM states.

    The HMM can discover multiple positive-trend states. This mapper therefore
    ranks states by volatility and trend strength before assigning labels, rather
    than allowing every positive-momentum state to collapse into TREND_UP.
    Weak positive states are labeled conservatively as RANGE until downstream
    shadow-mode testing proves they deserve a more constructive interpretation.
    """
    idx = {name: i for i, name in enumerate(feature_columns)}
    n_states = raw_means.shape[0]

    vols = raw_means[:, idx["vol_20"]]
    rets = raw_means[:, idx["log_return"]]
    mom_20 = raw_means[:, idx["mom_20"]]
    mom_60 = raw_means[:, idx["mom_60"]]
    trends = raw_means[:, idx["trend_dist_200"]]
    fast_slow = raw_means[:, idx["ema_50_200_dist"]]

    labels: dict[int, str] = {}
    high_vol_state = int(np.argmax(vols))
    labels[high_vol_state] = "HIGH_VOL"

    remaining = [s for s in range(n_states) if s not in labels]
    if not remaining:
        return labels

    for s in remaining:
        if trends[s] < 0.0 and mom_60[s] < 0.0:
            labels[s] = "TREND_DOWN"

    remaining = [s for s in range(n_states) if s not in labels]
    if not remaining:
        return labels

    def trend_score(state: int) -> float:
        return float(rets[state] + mom_20[state] + mom_60[state] + trends[state] + fast_slow[state])

    # Among non-crisis/non-down states, the strongest broad positive state is the
    # clean TREND_UP regime. This avoids treating weak/choppy positive states as
    # high-confidence uptrends.
    trend_up_state = max(remaining, key=trend_score)
    if trend_score(trend_up_state) > 0.0:
        labels[trend_up_state] = "TREND_UP"

    remaining = [s for s in range(n_states) if s not in labels]
    if not remaining:
        return labels

    low_vol_state = min(remaining, key=lambda s: vols[s])
    labels[low_vol_state] = "VOL_COMPRESSION"

    remaining = [s for s in range(n_states) if s not in labels]
    for s in remaining:
        labels[s] = "RANGE"

    return labels
