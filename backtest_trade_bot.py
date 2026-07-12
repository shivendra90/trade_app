"""
This is the backtester module for the trading bot.

Takes in environment variables for initiating Breeze session (API key, secret and session token)
Takes in these flags:
--symbol (the stock for which trading needs to happen, ex. NIFTY)
--exchange (market where trade will happen. NSE or BSE)
--interval (1 minute, 5 minutes allowed)
--strategy (algorithm on which the bot will function)
--qty (quantity of specified symbol)
--stop-loss-amount (amount on which trade will stop when incurred loss)
--target-amount (profit amount targeted in INR)
--trailing-stop-amount"""


import argparse
import csv
import datetime as dt
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol

try:
    import pandas as pd
except ImportError as exc:
    raise RuntimeError("pandas is required. Install with: pip install pandas") from exc

try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
except ImportError as exc:
    raise RuntimeError("plotly is required. Install with: pip install plotly") from exc

try:
    from breeze_connect import BreezeConnect
except ImportError:
    BreezeConnect = None


@dataclass
class Candle:
    timestamp: dt.datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


@dataclass
class TradeState:
    has_position: bool = False
    qty: int = 0
    entry_price: float = 0.0
    entry_time: Optional[dt.datetime] = None
    realized_pnl: float = 0.0
    highest_price: float = 0.0
    stop_loss_price: float = 0.0
    target_price: float = 0.0
    trailing_stop_price: float = 0.0


@dataclass
class TradeEvent:
    timestamp: dt.datetime
    side: str
    price: float
    qty: int
    reason: str
    trade_pnl: float
    cumulative_pnl: float


class Strategy(Protocol):
    name: str

    def signal(self, candles: List[Candle], has_position: bool) -> str:
        ...


class SmaCrossStrategy:
    name = "sma_crossover"

    def __init__(self, short_window: int = 9, long_window: int = 21) -> None:
        if short_window >= long_window:
            raise ValueError("short_window must be smaller than long_window")
        self.short_window = short_window
        self.long_window = long_window

    def signal(self, candles: List[Candle], has_position: bool) -> str:
        if len(candles) < self.long_window:
            return "HOLD"
        closes = pd.Series([c.close for c in candles], dtype="float64")
        short_sma = closes.tail(self.short_window).mean()
        long_sma = closes.tail(self.long_window).mean()
        if short_sma > long_sma and not has_position:
            return "BUY"
        if short_sma < long_sma and has_position:
            return "SELL"
        return "HOLD"


class RsiMeanReversionStrategy:
    name = "rsi_mean_reversion"

    def __init__(self, period: int = 14, oversold: float = 30, overbought: float = 70) -> None:
        self.period = period
        self.oversold = oversold
        self.overbought = overbought

    def signal(self, candles: List[Candle], has_position: bool) -> str:
        if len(candles) < self.period + 1:
            return "HOLD"
        closes = pd.Series([c.close for c in candles], dtype="float64")
        delta = closes.diff()
        gains = delta.clip(lower=0).rolling(self.period).mean().iloc[-1]
        losses = (-delta.clip(upper=0)).rolling(self.period).mean().iloc[-1]
        if losses == 0:
            return "HOLD"
        rs = gains / losses
        rsi = 100 - (100 / (1 + rs))
        if rsi <= self.oversold and not has_position:
            return "BUY"
        if rsi >= self.overbought and has_position:
            return "SELL"
        return "HOLD"


class BreakoutStrategy:
    name = "breakout"

    def __init__(self, lookback: int = 20) -> None:
        self.lookback = lookback

    def signal(self, candles: List[Candle], has_position: bool) -> str:
        if len(candles) < self.lookback + 1:
            return "HOLD"
        window = candles[-(self.lookback + 1) : -1]
        latest = candles[-1]
        high_band = max(c.high for c in window)
        low_band = min(c.low for c in window)
        if latest.close > high_band and not has_position:
            return "BUY"
        if latest.close < low_band and has_position:
            return "SELL"
        return "HOLD"


class StrategyFactory:
    @staticmethod
    def create(name: str) -> Strategy:
        key = name.strip().lower()
        if key == "sma_crossover":
            return SmaCrossStrategy()
        if key == "rsi_mean_reversion":
            return RsiMeanReversionStrategy()
        if key == "breakout":
            return BreakoutStrategy()
        raise ValueError(
            f"Unknown strategy '{name}'. Supported: sma_crossover, rsi_mean_reversion, breakout"
        )


class BreezeClient:
    def __init__(self, api_key: str, api_secret: str, session_token: str) -> None:
        if BreezeConnect is None:
            raise RuntimeError("breeze-connect is required. Install with: pip install breeze-connect")
        self.client = BreezeConnect(api_key=api_key)
        self.client.generate_session(api_secret=api_secret, session_token=session_token)

    def fetch_day_candles(
        self,
        symbol: str,
        exchange_code: str,
        interval: str,
        target_date: dt.date,
        start_time: dt.time,
        end_time: dt.time,
    ) -> List[Candle]:
        from_dt = dt.datetime.combine(target_date, start_time)
        to_dt = dt.datetime.combine(target_date, end_time)
        response = self.client.get_historical_data_v2(
            interval=interval,
            from_date=from_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            to_date=to_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            stock_code=symbol,
            exchange_code=exchange_code,
        )
        rows = self._extract_rows(response)
        candles: List[Candle] = []
        for row in rows:
            ts_raw = row.get("datetime") or row.get("date") or row.get("timestamp")
            if ts_raw is None:
                continue
            timestamp = pd.to_datetime(ts_raw).to_pydatetime()
            candles.append(
                Candle(
                    timestamp=timestamp,
                    open=float(row.get("open", row.get("Open"))),
                    high=float(row.get("high", row.get("High"))),
                    low=float(row.get("low", row.get("Low"))),
                    close=float(row.get("close", row.get("Close"))),
                    volume=float(row.get("volume", 0) or 0),
                )
            )
        candles.sort(key=lambda c: c.timestamp)
        return candles

    @staticmethod
    def _extract_rows(response: Any) -> List[Dict[str, Any]]:
        if isinstance(response, list):
            return response
        if isinstance(response, dict):
            if "Success" in response and isinstance(response["Success"], list):
                return response["Success"]
            if "data" in response and isinstance(response["data"], list):
                return response["data"]
        raise ValueError(f"Unexpected historical response format: {response}")


class BacktestReportWriter:
    def __init__(self, csv_path: Path) -> None:
        self.csv_path = csv_path
        self.csv_path.parent.mkdir(parents=True, exist_ok=True)

    def write_events(self, events: List[TradeEvent]) -> None:
        with self.csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "timestamp",
                "side",
                "price",
                "qty",
                "reason",
                "trade_pnl",
                "cumulative_pnl",
            ])
            for e in events:
                writer.writerow(
                    [
                        e.timestamp.isoformat(),
                        e.side,
                        f"{e.price:.4f}",
                        e.qty,
                        e.reason,
                        f"{e.trade_pnl:.4f}",
                        f"{e.cumulative_pnl:.4f}",
                    ]
                )

    @staticmethod
    def write_summary(csv_path: Path, records: List[Dict[str, Any]]) -> None:
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        columns = [
            "date",
            "strategy",
            "symbol",
            "candles",
            "completed_trades",
            "winning_trades",
            "losing_trades",
            "realized_pnl",
        ]
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()
            for row in records:
                writer.writerow(row)


class BacktestChart:
    def __init__(self, output_file: Path) -> None:
        self.output_file = output_file
        self.output_file.parent.mkdir(parents=True, exist_ok=True)

    def write(
        self,
        candles: List[Candle],
        events: List[TradeEvent],
        equity_curve: List[float],
        state: TradeState,
        symbol: str,
        strategy_name: str,
        target_date: dt.date,
    ) -> None:
        fig = make_subplots(
            rows=2,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.12,
            row_heights=[0.75, 0.25],
            subplot_titles=("Candlestick Backtest", "P&L Curve"),
        )

        times = [c.timestamp for c in candles]
        fig.add_trace(
            go.Candlestick(
                x=times,
                open=[c.open for c in candles],
                high=[c.high for c in candles],
                low=[c.low for c in candles],
                close=[c.close for c in candles],
                name="OHLC",
                hovertemplate="<b>%{x|%H:%M}</b><br>O: %{open:.2f}<br>H: %{high:.2f}<br>L: %{low:.2f}<br>C: %{close:.2f}<extra></extra>",
            ),
            row=1,
            col=1,
        )

        buy_events = [e for e in events if e.side == "BUY"]
        sell_events = [e for e in events if e.side == "SELL"]

        if buy_events:
            fig.add_trace(
                go.Scatter(
                    x=[e.timestamp for e in buy_events],
                    y=[e.price for e in buy_events],
                    mode="markers",
                    marker=dict(size=10, color="deepskyblue", symbol="triangle-up"),
                    name="BUY",
                    customdata=[e.reason for e in buy_events],
                    hovertemplate="<b>BUY</b><br>%{x|%H:%M}<br>Price: %{y:.2f}<br>Reason: %{customdata}<extra></extra>",
                ),
                row=1,
                col=1,
            )

        if sell_events:
            fig.add_trace(
                go.Scatter(
                    x=[e.timestamp for e in sell_events],
                    y=[e.price for e in sell_events],
                    mode="markers",
                    marker=dict(size=10, color="red", symbol="triangle-down"),
                    name="SELL",
                    customdata=[f"{e.reason} | Trade PnL: {e.trade_pnl:.2f}" for e in sell_events],
                    hovertemplate="<b>SELL</b><br>%{x|%H:%M}<br>Price: %{y:.2f}<br>%{customdata}<extra></extra>",
                ),
                row=1,
                col=1,
            )

        fig.add_trace(
            go.Scatter(
                x=times,
                y=equity_curve,
                mode="lines",
                name="Total P&L",
                line=dict(color="purple", width=2),
                hovertemplate="<b>%{x|%H:%M}</b><br>Total P&L: %{y:.2f}<extra></extra>",
            ),
            row=2,
            col=1,
        )
        fig.add_hline(y=0, line_color="gray", line_width=1, row=2, col=1)

        fig.update_layout(
            title=(
                f"{symbol} | {strategy_name} | Backtest Date: {target_date.isoformat()} | "
                f"Realized P&L: {state.realized_pnl:.2f}"
            ),
            template="plotly_dark",
            hovermode="x unified",
            xaxis_rangeslider_visible=False,
            height=850,
        )
        fig.update_xaxes(title_text="Time", row=2, col=1)
        fig.update_yaxes(title_text="Price", row=1, col=1)
        fig.update_yaxes(title_text="P&L", row=2, col=1)

        fig.write_html(str(self.output_file))


class BatchComparisonChart:
    def __init__(self, output_file: Path) -> None:
        self.output_file = output_file
        self.output_file.parent.mkdir(parents=True, exist_ok=True)

    def write(self, summary_rows: List[Dict[str, Any]], symbol: str) -> None:
        df = pd.DataFrame(summary_rows)
        if df.empty:
            return

        df["date"] = pd.to_datetime(df["date"])
        pnl_by_strategy = df.groupby("strategy", as_index=False)["realized_pnl"].sum()
        daily = df.groupby(["date", "strategy"], as_index=False)["realized_pnl"].sum()

        fig = make_subplots(
            rows=2,
            cols=1,
            subplot_titles=("Net P&L by Strategy", "Daily P&L by Strategy"),
            vertical_spacing=0.15,
        )

        fig.add_trace(
            go.Bar(
                x=pnl_by_strategy["strategy"],
                y=pnl_by_strategy["realized_pnl"],
                name="Net P&L",
                hovertemplate="Strategy: %{x}<br>Net P&L: %{y:.2f}<extra></extra>",
            ),
            row=1,
            col=1,
        )

        for strategy in sorted(daily["strategy"].unique()):
            s_df = daily[daily["strategy"] == strategy].sort_values("date")
            fig.add_trace(
                go.Scatter(
                    x=s_df["date"],
                    y=s_df["realized_pnl"],
                    mode="lines+markers",
                    name=strategy,
                    hovertemplate="Date: %{x|%Y-%m-%d}<br>P&L: %{y:.2f}<extra></extra>",
                ),
                row=2,
                col=1,
            )

        fig.update_layout(
            title=f"{symbol} | Multi-day Strategy Comparison",
            template="plotly_dark",
            barmode="group",
            hovermode="x unified",
            height=900,
        )
        fig.update_xaxes(title_text="Strategy", row=1, col=1)
        fig.update_xaxes(title_text="Date", row=2, col=1)
        fig.update_yaxes(title_text="Net P&L", row=1, col=1)
        fig.update_yaxes(title_text="Daily P&L", row=2, col=1)
        fig.write_html(str(self.output_file))


class Backtester:
    def __init__(
        self,
        strategy: Strategy,
        qty: int,
        stop_loss_pct: float,
        target_pct: float,
        trailing_stop_pct: float,
        stop_loss_amount: float,
        target_amount: float,
        trailing_stop_amount: float,
        square_off_eod: bool,
    ) -> None:
        self.strategy = strategy
        self.qty = qty
        self.stop_loss_pct = stop_loss_pct
        self.target_pct = target_pct
        self.trailing_stop_pct = trailing_stop_pct
        self.stop_loss_amount = stop_loss_amount
        self.target_amount = target_amount
        self.trailing_stop_amount = trailing_stop_amount
        self.square_off_eod = square_off_eod
        self.state = TradeState()
        self.events: List[TradeEvent] = []

    def run(self, candles: List[Candle]) -> Dict[str, Any]:
        equity_curve: List[float] = []
        if not candles:
            return {"events": [], "equity_curve": [], "state": self.state}

        history: List[Candle] = []
        for candle in candles:
            history.append(candle)
            risk_reason = self._risk_exit_reason(candle.close)
            if risk_reason:
                self._execute("SELL", candle, risk_reason)
            else:
                signal = self.strategy.signal(history, self.state.has_position)
                if signal in ("BUY", "SELL"):
                    self._execute(signal, candle, f"STRATEGY_{self.strategy.name.upper()}")

            equity_curve.append(self.state.realized_pnl + self._unrealized_pnl(candle.close))

        if self.square_off_eod and self.state.has_position:
            self._execute("SELL", candles[-1], "EOD_SQUARE_OFF")
            equity_curve[-1] = self.state.realized_pnl

        return {"events": self.events, "equity_curve": equity_curve, "state": self.state}

    def _execute(self, side: str, candle: Candle, reason: str) -> None:
        price = candle.close
        if side == "BUY" and self.state.has_position:
            return
        if side == "SELL" and not self.state.has_position:
            return

        if side == "BUY":
            sl_distance = self._stop_loss_distance(price)
            target_distance = self._target_distance(price)
            tsl_distance = self._trailing_stop_distance(price)

            self.state.has_position = True
            self.state.qty = self.qty
            self.state.entry_price = price
            self.state.entry_time = candle.timestamp
            self.state.highest_price = price
            self.state.stop_loss_price = price - sl_distance if sl_distance > 0 else 0.0
            self.state.target_price = price + target_distance if target_distance > 0 else 0.0
            self.state.trailing_stop_price = price - tsl_distance if tsl_distance > 0 else 0.0

            self.events.append(
                TradeEvent(
                    timestamp=candle.timestamp,
                    side="BUY",
                    price=price,
                    qty=self.qty,
                    reason=reason,
                    trade_pnl=0.0,
                    cumulative_pnl=self.state.realized_pnl,
                )
            )
            return

        trade_pnl = (price - self.state.entry_price) * self.state.qty
        self.state.realized_pnl += trade_pnl
        self.events.append(
            TradeEvent(
                timestamp=candle.timestamp,
                side="SELL",
                price=price,
                qty=self.state.qty,
                reason=reason,
                trade_pnl=trade_pnl,
                cumulative_pnl=self.state.realized_pnl,
            )
        )

        self.state.has_position = False
        self.state.qty = 0
        self.state.entry_price = 0.0
        self.state.entry_time = None
        self.state.highest_price = 0.0
        self.state.stop_loss_price = 0.0
        self.state.target_price = 0.0
        self.state.trailing_stop_price = 0.0

    def _risk_exit_reason(self, last_price: float) -> Optional[str]:
        if not self.state.has_position:
            return None
        if last_price > self.state.highest_price:
            self.state.highest_price = last_price
            trailing_distance = self._trailing_stop_distance(self.state.entry_price)
            if trailing_distance > 0:
                self.state.trailing_stop_price = self.state.highest_price - trailing_distance

        if self._stop_loss_distance(self.state.entry_price) > 0 and last_price <= self.state.stop_loss_price:
            return "STOP_LOSS_HIT"
        if self._target_distance(self.state.entry_price) > 0 and last_price >= self.state.target_price:
            return "TARGET_HIT"
        if (
            self._trailing_stop_distance(self.state.entry_price) > 0
            and self.state.trailing_stop_price > 0
            and last_price <= self.state.trailing_stop_price
        ):
            return "TRAILING_STOP_HIT"
        return None

    def _unrealized_pnl(self, last_price: float) -> float:
        if not self.state.has_position:
            return 0.0
        return (last_price - self.state.entry_price) * self.state.qty

    def _stop_loss_distance(self, entry_price: float) -> float:
        if self.stop_loss_amount > 0:
            return self.stop_loss_amount
        if self.stop_loss_pct > 0:
            return entry_price * (self.stop_loss_pct / 100.0)
        return 0.0

    def _target_distance(self, entry_price: float) -> float:
        if self.target_amount > 0:
            return self.target_amount
        if self.target_pct > 0:
            return entry_price * (self.target_pct / 100.0)
        return 0.0

    def _trailing_stop_distance(self, entry_price: float) -> float:
        if self.trailing_stop_amount > 0:
            return self.trailing_stop_amount
        if self.trailing_stop_pct > 0:
            return entry_price * (self.trailing_stop_pct / 100.0)
        return 0.0


def parse_time(value: str) -> dt.time:
    return dt.datetime.strptime(value, "%H:%M").time()


def parse_date(value: str) -> dt.date:
    return dt.datetime.strptime(value, "%Y-%m-%d").date()


def previous_trading_day(day: dt.date) -> dt.date:
    d = day - dt.timedelta(days=1)
    while d.weekday() >= 5:
        d -= dt.timedelta(days=1)
    return d


def resolve_backtest_date(user_input: str, cutoff_time: dt.time) -> dt.date:
    if user_input:
        chosen = parse_date(user_input)
        while chosen.weekday() >= 5:
            chosen -= dt.timedelta(days=1)
        return chosen

    now = dt.datetime.now()
    candidate = now.date() if now.time() >= cutoff_time else previous_trading_day(now.date())
    while candidate.weekday() >= 5:
        candidate -= dt.timedelta(days=1)
    return candidate


def trading_days_between(start_date: dt.date, end_date: dt.date) -> List[dt.date]:
    if end_date < start_date:
        raise ValueError("to-date must be >= from-date")
    days: List[dt.date] = []
    current = start_date
    while current <= end_date:
        if current.weekday() < 5:
            days.append(current)
        current += dt.timedelta(days=1)
    return days


def backtest_day_dir(backtest_date: dt.date) -> Path:
    return Path("logs") / "backtesting" / backtest_date.isoformat()


def backtest_batch_dir(start_date: dt.date, end_date: dt.date) -> Path:
    return Path("logs") / "backtesting" / f"{start_date.isoformat()}_to_{end_date.isoformat()}"


def resolve_chart_path(input_path: str, backtest_date: dt.date) -> Path:
    if input_path:
        return Path(input_path)
    day_dir = backtest_day_dir(backtest_date)
    return day_dir / f"backtest_chart_{backtest_date.isoformat()}.html"


def resolve_csv_path(input_path: str, backtest_date: dt.date) -> Path:
    if input_path:
        return Path(input_path)
    day_dir = backtest_day_dir(backtest_date)
    return day_dir / f"backtest_trades_{backtest_date.isoformat()}.csv"


def resolve_summary_csv_path(input_path: str, start_date: dt.date, end_date: dt.date) -> Path:
    if input_path:
        return Path(input_path)
    batch_dir = backtest_batch_dir(start_date, end_date)
    return batch_dir / f"backtest_summary_{start_date.isoformat()}_{end_date.isoformat()}.csv"


def resolve_comparison_chart_path(input_path: str, start_date: dt.date, end_date: dt.date) -> Path:
    if input_path:
        return Path(input_path)
    batch_dir = backtest_batch_dir(start_date, end_date)
    return batch_dir / f"backtest_comparison_{start_date.isoformat()}_{end_date.isoformat()}.html"


def parse_strategy_list(primary_strategy: str, compare_strategies: str) -> List[str]:
    if compare_strategies.strip():
        items = [x.strip() for x in compare_strategies.split(",") if x.strip()]
        unique = []
        for i in items:
            if i not in unique:
                unique.append(i)
        if not unique:
            raise ValueError("--compare-strategies was provided but no valid strategy names were found")
        return unique
    return [primary_strategy]


def build_cli() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Standalone backtesting framework for Breeze OHLC data with Plotly chart"
    )
    parser.add_argument("--symbol", default="NIFTY-I")
    parser.add_argument("--exchange", default="NSE")
    parser.add_argument("--interval", default="1minute")
    parser.add_argument("--strategy", default="sma_crossover")
    parser.add_argument("--compare-strategies", default="", help="Comma-separated strategies for comparison")
    parser.add_argument("--qty", type=int, default=1)

    parser.add_argument("--backtest-date", default="", help="YYYY-MM-DD. If empty, auto-select by cutoff time.")
    parser.add_argument("--from-date", default="", help="YYYY-MM-DD. Enables batch mode.")
    parser.add_argument("--to-date", default="", help="YYYY-MM-DD. Enables batch mode.")
    parser.add_argument("--market-cutoff", default="15:20", help="If current time >= cutoff, use today; else previous trading day.")
    parser.add_argument("--start-time", default="09:15")
    parser.add_argument("--end-time", default="15:30")

    parser.add_argument("--stop-loss-pct", type=float, default=0.7)
    parser.add_argument("--target-pct", type=float, default=1.2)
    parser.add_argument("--trailing-stop-pct", type=float, default=0.5)
    parser.add_argument("--stop-loss-amount", type=float, default=0.0)
    parser.add_argument("--target-amount", type=float, default=0.0)
    parser.add_argument("--trailing-stop-amount", type=float, default=0.0)

    parser.add_argument("--chart-file", default="")
    parser.add_argument("--trades-csv", default="")
    parser.add_argument("--summary-csv", default="")
    parser.add_argument("--comparison-chart", default="")
    parser.add_argument("--no-square-off-eod", action="store_true")
    return parser


def load_credentials() -> Dict[str, str]:
    api_key = os.getenv("API_KEY")
    api_secret = os.getenv("SECRET")
    session_token = os.getenv("TOKEN")
    if not api_key or not api_secret or not session_token:
        raise RuntimeError(
            "Set API_KEY, SECRET and OKEN environment variables"
        )
    return {"api_key": api_key, "api_secret": api_secret, "session_token": session_token}


def validate_inputs(args: argparse.Namespace) -> None:
    if args.qty <= 0:
        raise ValueError("qty must be > 0")

    values = [
        args.stop_loss_pct,
        args.target_pct,
        args.trailing_stop_pct,
        args.stop_loss_amount,
        args.target_amount,
        args.trailing_stop_amount,
    ]
    if any(v < 0 for v in values):
        raise ValueError("Risk values must be non-negative")

    from_set = bool(args.from_date.strip())
    to_set = bool(args.to_date.strip())
    if from_set != to_set:
        raise ValueError("Provide both --from-date and --to-date for batch mode")


def summarize(events: List[TradeEvent], realized_pnl: float) -> None:
    sell_events = [e for e in events if e.side == "SELL"]
    wins = [e for e in sell_events if e.trade_pnl > 0]
    losses = [e for e in sell_events if e.trade_pnl < 0]

    print("\nBacktest Summary")
    print("---------------")
    print(f"Total events: {len(events)}")
    print(f"Completed trades: {len(sell_events)}")
    print(f"Winning trades: {len(wins)}")
    print(f"Losing trades: {len(losses)}")
    print(f"Net realized P&L: {realized_pnl:.2f}")


def run_single_day(
    args: argparse.Namespace,
    client: BreezeClient,
    strategy_name: str,
    date_value: dt.date,
    start_time: dt.time,
    end_time: dt.time,
) -> None:
    candles = client.fetch_day_candles(
        symbol=args.symbol,
        exchange_code=args.exchange,
        interval=args.interval,
        target_date=date_value,
        start_time=start_time,
        end_time=end_time,
    )
    if not candles:
        raise RuntimeError(f"No candles fetched for {args.symbol} on {date_value.isoformat()}")

    strategy = StrategyFactory.create(strategy_name)
    backtester = Backtester(
        strategy=strategy,
        qty=args.qty,
        stop_loss_pct=args.stop_loss_pct,
        target_pct=args.target_pct,
        trailing_stop_pct=args.trailing_stop_pct,
        stop_loss_amount=args.stop_loss_amount,
        target_amount=args.target_amount,
        trailing_stop_amount=args.trailing_stop_amount,
        square_off_eod=not args.no_square_off_eod,
    )
    result = backtester.run(candles)

    chart_path = resolve_chart_path(args.chart_file, date_value)
    csv_path = resolve_csv_path(args.trades_csv, date_value)

    chart = BacktestChart(chart_path)
    chart.write(
        candles=candles,
        events=result["events"],
        equity_curve=result["equity_curve"],
        state=result["state"],
        symbol=args.symbol,
        strategy_name=strategy.name,
        target_date=date_value,
    )

    report = BacktestReportWriter(csv_path)
    report.write_events(result["events"])

    print(f"Backtest date: {date_value.isoformat()}")
    print(f"Candles: {len(candles)}")
    print(f"Chart: {chart_path.resolve()}")
    print(f"Trades CSV: {csv_path.resolve()}")
    print(
        "Risk config (amount takes precedence over pct): "
        f"SL amount={args.stop_loss_amount}, SL pct={args.stop_loss_pct}, "
        f"Target amount={args.target_amount}, Target pct={args.target_pct}, "
        f"TSL amount={args.trailing_stop_amount}, TSL pct={args.trailing_stop_pct}"
    )
    summarize(result["events"], result["state"].realized_pnl)


def run_batch_mode(
    args: argparse.Namespace,
    client: BreezeClient,
    strategies: List[str],
    dates: List[dt.date],
    start_time: dt.time,
    end_time: dt.time,
) -> None:
    summary_rows: List[Dict[str, Any]] = []
    detailed_trade_rows: List[Dict[str, Any]] = []
    candles_cache: Dict[dt.date, List[Candle]] = {}

    for d in dates:
        candles = client.fetch_day_candles(
            symbol=args.symbol,
            exchange_code=args.exchange,
            interval=args.interval,
            target_date=d,
            start_time=start_time,
            end_time=end_time,
        )
        candles_cache[d] = candles

    for d in dates:
        candles = candles_cache[d]
        if not candles:
            print(f"Skipping {d.isoformat()} (no candles)")
            continue

        for strategy_name in strategies:
            strategy = StrategyFactory.create(strategy_name)
            backtester = Backtester(
                strategy=strategy,
                qty=args.qty,
                stop_loss_pct=args.stop_loss_pct,
                target_pct=args.target_pct,
                trailing_stop_pct=args.trailing_stop_pct,
                stop_loss_amount=args.stop_loss_amount,
                target_amount=args.target_amount,
                trailing_stop_amount=args.trailing_stop_amount,
                square_off_eod=not args.no_square_off_eod,
            )
            result = backtester.run(candles)
            events = result["events"]
            state = result["state"]
            sells = [e for e in events if e.side == "SELL"]
            wins = [e for e in sells if e.trade_pnl > 0]
            losses = [e for e in sells if e.trade_pnl < 0]

            summary_rows.append(
                {
                    "date": d.isoformat(),
                    "strategy": strategy.name,
                    "symbol": args.symbol,
                    "candles": len(candles),
                    "completed_trades": len(sells),
                    "winning_trades": len(wins),
                    "losing_trades": len(losses),
                    "realized_pnl": round(state.realized_pnl, 4),
                }
            )

            for e in events:
                detailed_trade_rows.append(
                    {
                        "date": d.isoformat(),
                        "strategy": strategy.name,
                        "timestamp": e.timestamp.isoformat(),
                        "side": e.side,
                        "price": round(e.price, 4),
                        "qty": e.qty,
                        "reason": e.reason,
                        "trade_pnl": round(e.trade_pnl, 4),
                        "cumulative_pnl": round(e.cumulative_pnl, 4),
                    }
                )

    if not summary_rows:
        raise RuntimeError("No backtest results produced in batch mode")

    start_date = dates[0]
    end_date = dates[-1]
    summary_csv = resolve_summary_csv_path(args.summary_csv, start_date, end_date)
    comparison_chart = resolve_comparison_chart_path(args.comparison_chart, start_date, end_date)
    trades_csv = Path(args.trades_csv) if args.trades_csv else (
        backtest_batch_dir(start_date, end_date)
        / f"backtest_trades_{start_date.isoformat()}_{end_date.isoformat()}.csv"
    )

    BacktestReportWriter.write_summary(summary_csv, summary_rows)

    trades_csv.parent.mkdir(parents=True, exist_ok=True)
    with trades_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["date", "strategy", "timestamp", "side", "price", "qty", "reason", "trade_pnl", "cumulative_pnl"],
        )
        writer.writeheader()
        for row in detailed_trade_rows:
            writer.writerow(row)

    chart = BatchComparisonChart(comparison_chart)
    chart.write(summary_rows, symbol=args.symbol)

    summary_df = pd.DataFrame(summary_rows)
    agg = summary_df.groupby("strategy", as_index=False).agg(
        total_pnl=("realized_pnl", "sum"),
        total_trades=("completed_trades", "sum"),
        total_wins=("winning_trades", "sum"),
        total_losses=("losing_trades", "sum"),
    )

    print(f"Batch range: {start_date.isoformat()} -> {end_date.isoformat()} ({len(dates)} trading days)")
    print(f"Strategies: {', '.join(strategies)}")
    print(f"Summary CSV: {summary_csv.resolve()}")
    print(f"Detailed trades CSV: {trades_csv.resolve()}")
    print(f"Comparison chart: {comparison_chart.resolve()}")
    print("\nAggregate Strategy Summary")
    print("--------------------------")
    for _, row in agg.sort_values("total_pnl", ascending=False).iterrows():
        print(
            f"{row['strategy']}: P&L={row['total_pnl']:.2f}, "
            f"Trades={int(row['total_trades'])}, Wins={int(row['total_wins'])}, Losses={int(row['total_losses'])}"
        )


def main() -> None:
    parser = build_cli()
    args = parser.parse_args()
    validate_inputs(args)

    cutoff = parse_time(args.market_cutoff)
    start_time = parse_time(args.start_time)
    end_time = parse_time(args.end_time)

    creds = load_credentials()
    client = BreezeClient(
        api_key=creds["api_key"],
        api_secret=creds["api_secret"],
        session_token=creds["session_token"],
    )

    strategies = parse_strategy_list(args.strategy, args.compare_strategies)

    if args.from_date.strip() and args.to_date.strip():
        from_date = parse_date(args.from_date)
        to_date = parse_date(args.to_date)
        dates = trading_days_between(from_date, to_date)
        run_batch_mode(
            args=args,
            client=client,
            strategies=strategies,
            dates=dates,
            start_time=start_time,
            end_time=end_time,
        )
        return

    backtest_date = resolve_backtest_date(args.backtest_date, cutoff)
    run_single_day(
        args=args,
        client=client,
        strategy_name=strategies[0],
        date_value=backtest_date,
        start_time=start_time,
        end_time=end_time,
    )


if __name__ == "__main__":
    main()
