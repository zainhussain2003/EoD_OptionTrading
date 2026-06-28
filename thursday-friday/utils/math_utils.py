import math


def norm_cdf(x: float) -> float:
    return (1.0 + math.erf(x / math.sqrt(2.0))) / 2.0


def norm_pdf(x: float) -> float:
    return math.exp(-x * x / 2.0) / math.sqrt(2.0 * math.pi)


def black_scholes_call(S: float, K: float, T: float, r: float, sigma: float
                       ) -> tuple[float, float, float, float]:
    """Returns (call_price, delta, d1, d2). delta = N(d1)."""
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        intrinsic = max(S - K, 0.0)
        delta = 1.0 if S > K else (0.5 if abs(S - K) < 0.001 else 0.0)
        return intrinsic, delta, 0.0, 0.0
    try:
        sqrt_T = math.sqrt(T)
        d1 = (math.log(S / K) + (r + sigma ** 2 / 2.0) * T) / (sigma * sqrt_T)
        d2 = d1 - sigma * sqrt_T
        d1 = max(-10.0, min(10.0, d1))
        d2 = max(-10.0, min(10.0, d2))
        price = S * norm_cdf(d1) - K * math.exp(-r * T) * norm_cdf(d2)
        delta = norm_cdf(d1)
        return max(price, 0.0), delta, d1, d2
    except (ValueError, ZeroDivisionError, OverflowError):
        return max(S - K, 0.0), 0.5, 0.0, 0.0


def calc_pop(S: float, K: float, premium: float, T: float, r: float, sigma: float) -> float:
    """Probability that call expires above breakeven (K + premium)."""
    if T <= 0:
        return 1.0 if S > K + premium else 0.0
    breakeven = K + premium
    if breakeven <= 0:
        return 1.0
    try:
        sqrt_T = math.sqrt(T)
        d2_be = (math.log(S / breakeven) + (r - sigma ** 2 / 2.0) * T) / (sigma * sqrt_T)
        return norm_cdf(d2_be)
    except (ValueError, ZeroDivisionError):
        return 0.0


def calc_theta_hourly(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Theta per trading hour (negative = option loses value)."""
    if T <= 0 or sigma <= 0 or S <= 0:
        return 0.0
    try:
        sqrt_T = math.sqrt(T)
        d1 = (math.log(S / K) + (r + sigma ** 2 / 2.0) * T) / (sigma * sqrt_T)
        d2 = d1 - sigma * sqrt_T
        theta_annual = (
            -(S * norm_pdf(d1) * sigma / (2.0 * sqrt_T))
            - r * K * math.exp(-r * T) * norm_cdf(d2)
        )
        return theta_annual / 252.0 / 6.5
    except (ValueError, ZeroDivisionError, OverflowError):
        return 0.0


def realized_vol(daily_closes: list[float], window: int = 20) -> float:
    """Annualized realized volatility from daily closing prices."""
    if len(daily_closes) < window + 1:
        return 0.30
    log_returns = [
        math.log(daily_closes[i] / daily_closes[i - 1])
        for i in range(max(1, len(daily_closes) - window), len(daily_closes))
    ]
    if len(log_returns) < 2:
        return 0.30
    mean = sum(log_returns) / len(log_returns)
    variance = sum((r - mean) ** 2 for r in log_returns) / (len(log_returns) - 1)
    return math.sqrt(variance * 252.0)
