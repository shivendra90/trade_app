import argparse
import csv
import datetime as dt
import os
import time
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


class BreezeLiveClient:
    def __init__(self, api_key: str, api_secret: str, session_token: str) -> None:
        if BreezeConnect is None:
            raise RuntimeError("breeze-connect is required. Install with: pip install breeze-connect")
        self.client = BreezeConnect(api_key=api_key)
        self.client.generate_session(api_secret=api_secret, session_token=session_token)

    def fetch_recent_candles(
        self,
        symbol: str,
        interval: str,
        exchange_code: str,
        lookback_minutes: int,
    ) -> List[Candle]:
        end = dt.datetime.now()
        start = end - dt.timedelta(minutes=lookback_minutes)
        response = self.client.get_historical_data_v2(
            interval=interval,
            from_date=start.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            to_date=end.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            stock_code=symbol,
            exchange_code=exchange_code,
        )
        rows = self._extract_rows(response)
        candles: List[Candle] = []
        for row in rows:
            ts_raw = row.get("datetime") or row.get("date") or row.get("timestamp")
            if ts_raw is None:
                raise ValueError(f"No datetime field found in candle row: {row}")
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
        return candles

    def place_order(
        self,
        side: str,
        symbol: str,
        qty: int,
        exchange_code: str,
        product: str,
        order_type: str = "market",
    ) -> Dict[str, Any]:
        action = "buy" if side.upper() == "BUY" else "sell"
        response = self.client.place_order(
            stock_code=symbol,
            exchange_code=exchange_code,
            product=product,
            action=action,
            order_type=order_type,
            quantity=str(qty),
            price="0",
            validity="day",
        )
        return response if isinstance(response, dict) else {"response": response}

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


class TradeCSVLogger:
    headers = [
        "event_time",
        "candle_time",
        "strategy",
        "symbol",
        "action",
        "reason",
        "price",
        "qty",
        "position_after",
        "entry_price",
        "stop_loss_price",
        "target_price",
        "trailing_stop_price",
        "realized_pnl",
        "unrealized_pnl",
        "total_pnl",
    ]

    def __init__(self, csv_path: Path) -> None:
        self.csv_path = csv_path
        self.csv_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.csv_path.exists():
            with self.csv_path.open("w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow(self.headers)

    def log(
        self,
        *,
        event_time: dt.datetime,
        candle_time: dt.datetime,
        strategy: str,
        symbol: str,
        action: str,
        reason: str,
        price: float,
        qty: int,
        state: TradeState,
        unrealized_pnl: float,
    ) -> None:
        total_pnl = state.realized_pnl + unrealized_pnl
        row = [
            event_time.isoformat(),
            candle_time.isoformat(),
            strategy,
            symbol,
            action,
            reason,
            f"{price:.4f}",
            qty,
            int(state.has_position),
            f"{state.entry_price:.4f}",
            f"{state.stop_loss_price:.4f}",
            f"{state.target_price:.4f}",
            f"{state.trailing_stop_price:.4f}",
            f"{state.realized_pnl:.4f}",
            f"{unrealized_pnl:.4f}",
            f"{total_pnl:.4f}",
        ]
        with self.csv_path.open("a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(row)


class LiveChart:
    def __init__(self, enabled: bool, output_file: Path, max_points: int = 150) -> None:
        self.enabled = enabled
        self.output_file = output_file
        self.max_points = max_points
        self.output_file.parent.mkdir(parents=True, exist_ok=True)

    def update(
        self,
        candles: List[Candle],
        events: List[TradeEvent],
        state: TradeState,
        symbol: str,
        strategy_name: str,
    ) -> None:
        if not self.enabled:
            return

        chart_candles = candles[-self.max_points :]
        if not chart_candles:
            return

        fig = make_subplots(
            rows=2,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.12,
            row_heights=[0.75, 0.25],
            subplot_titles=("Candlestick Chart", "Realized P&L"),
        )

        times = [c.timestamp for c in chart_candles]
        opens = [c.open for c in chart_candles]
        highs = [c.high for c in chart_candles]
        lows = [c.low for c in chart_candles]
        closes = [c.close for c in chart_candles]

        fig.add_trace(
            go.Candlestick(
                x=times,
                open=opens,
                high=highs,
                low=lows,
                close=closes,
                name="OHLC",
                hovertemplate="<b>%{x|%H:%M}</b><br>O: %{open:.2f}<br>H: %{high:.2f}<br>L: %{low:.2f}<br>C: %{close:.2f}<extra></extra>",
            ),
            row=1,
            col=1,
        )

        timestamps_dict = {c.timestamp: i for i, c in enumerate(chart_candles)}
        buy_events = [ev for ev in events if ev.timestamp in timestamps_dict and ev.side == "BUY"]
        sell_events = [ev for ev in events if ev.timestamp in timestamps_dict and ev.side == "SELL"]

        if buy_events:
            buy_times = [ev.timestamp for ev in buy_events]
            buy_prices = [ev.price for ev in buy_events]
            buy_reasons = [ev.reason for ev in buy_events]
            fig.add_trace(
                go.Scatter(
                    x=buy_times,
                    y=buy_prices,
                    mode="markers",
                    marker=dict(size=10, color="blue", symbol="triangle-up"),
                    name="BUY",
                    hovertemplate="<b>BUY</b><br>%{x|%H:%M}<br>Price: %{y:.2f}<br>Reason: "
                    + "<br>".join(
                        [
                            f"{reason}"
                            for reason in buy_reasons
                        ]
                    ),
                    text=buy_reasons,
                    customdata=buy_reasons,
                ),
                row=1,
                col=1,
            )

        if sell_events:
            sell_times = [ev.timestamp for ev in sell_events]
            sell_prices = [ev.price for ev in sell_events]
            sell_reasons = [ev.reason for ev in sell_events]
            fig.add_trace(
                go.Scatter(
                    x=sell_times,
                    y=sell_prices,
                    mode="markers",
                    marker=dict(size=10, color="red", symbol="triangle-down"),
                    name="SELL",
                    hovertemplate="<b>SELL</b><br>%{x|%H:%M}<br>Price: %{y:.2f}<br>Reason: %{customdata}",
                    customdata=sell_reasons,
                ),
                row=1,
                col=1,
            )

        if state.stop_loss_price > 0:
            fig.add_hline(
                y=state.stop_loss_price,
                line_dash="dash",
                line_color="red",
                annotation_text="SL",
                row=1,
                col=1,
            )

        if state.target_price > 0:
            fig.add_hline(
                y=state.target_price,
                line_dash="dash",
                line_color="green",
                annotation_text="Target",
                row=1,
                col=1,
            )

        if state.trailing_stop_price > 0 and state.has_position:
            fig.add_hline(
                y=state.trailing_stop_price,
                line_dash="dot",
                line_color="orange",
                annotation_text="TSL",
                row=1,
                col=1,
            )

        pnl_series = [ev.cumulative_pnl for ev in events]
        if pnl_series:
            fig.add_trace(
                go.Scatter(
                    x=[events[i].timestamp for i in range(len(events))],
                    y=pnl_series,
                    mode="lines+markers",
                    name="Realized P&L",
                    line=dict(color="purple", width=2),
                    hovertemplate="<b>%{x|%H:%M}</b><br>P&L: ₹%{y:.2f}<extra></extra>",
                ),
                row=2,
                col=1,
            )
            fig.add_hline(y=0, line_color="gray", line_width=1, row=2, col=1)

        fig.update_xaxes(title_text="Time", row=2, col=1)
        fig.update_yaxes(title_text="Price", row=1, col=1)
        fig.update_yaxes(title_text="P&L (₹)", row=2, col=1)

        title_text = (
            f"{symbol} | {strategy_name} | Position: {state.has_position} | "
            f"Entry: ₹{state.entry_price:.2f} | SL: ₹{state.stop_loss_price:.2f} | "
            f"Target: ₹{state.target_price:.2f} | TSL: ₹{state.trailing_stop_price:.2f} | "
            f"Realized PnL: ₹{state.realized_pnl:.2f}"
        )
        fig.update_layout(
            title=title_text,
            template="plotly_dark",
            height=800,
            hovermode="x unified",
            xaxis_rangeslider_visible=False,
        )

        fig.write_html(str(self.output_file))



class LiveTradingBot:
    def __init__(
        self,
        client: BreezeLiveClient,
        strategy: Strategy,
        symbol: str,
        exchange_code: str,
        interval: str,
        qty: int,
        poll_seconds: int,
        live_orders: bool,
        stop_loss_pct: float,
        target_pct: float,
        trailing_stop_pct: float,
        stop_loss_amount: float,
        target_amount: float,
        trailing_stop_amount: float,
        logger: TradeCSVLogger,
        chart: LiveChart,
        product: str = "cash",
        max_iterations: int = 0,
    ) -> None:
        self.client = client
        self.strategy = strategy
        self.symbol = symbol
        self.exchange_code = exchange_code
        self.interval = interval
        self.qty = qty
        self.poll_seconds = poll_seconds
        self.live_orders = live_orders
        self.product = product
        self.stop_loss_pct = stop_loss_pct
        self.target_pct = target_pct
        self.trailing_stop_pct = trailing_stop_pct
        self.stop_loss_amount = stop_loss_amount
        self.target_amount = target_amount
        self.trailing_stop_amount = trailing_stop_amount
        self.logger = logger
        self.chart = chart
        self.state = TradeState()
        self.events: List[TradeEvent] = []
        self.max_iterations = max_iterations

    def run_session(self, end_time: dt.time, lookback_minutes: int) -> None:
        print(f"Starting strategy: {self.strategy.name} for {self.symbol}")
        iterations = 0
        while dt.datetime.now().time() <= end_time:
            candles = self.client.fetch_recent_candles(
                symbol=self.symbol,
                interval=self.interval,
                exchange_code=self.exchange_code,
                lookback_minutes=lookback_minutes,
            )
            if not candles:
                print(f"{dt.datetime.now().isoformat()} | No data. Retrying in {self.poll_seconds}s")
                time.sleep(self.poll_seconds)
                continue

            latest = candles[-1]
            risk_reason = self._risk_exit_reason(latest.close)
            if risk_reason:
                self._execute_signal("SELL", latest, reason=risk_reason)
            else:
                signal = self.strategy.signal(candles, self.state.has_position)
                if signal in ("BUY", "SELL"):
                    reason = f"STRATEGY_{self.strategy.name.upper()}"
                    self._execute_signal(signal, latest, reason=reason)
                else:
                    self._status_log(latest, action="HOLD", reason="NO_SIGNAL")

            self.chart.update(
                candles=candles,
                events=self.events,
                state=self.state,
                symbol=self.symbol,
                strategy_name=self.strategy.name,
            )

            iterations += 1
            if self.max_iterations > 0 and iterations >= self.max_iterations:
                print("Reached max iterations for this run. Exiting.")
                break
            time.sleep(self.poll_seconds)
        print("Session complete.")

    def run_daily(
        self,
        start_time: dt.time,
        end_time: dt.time,
        lookback_minutes: int,
    ) -> None:
        while True:
            now = dt.datetime.now()
            if now.weekday() >= 5:
                print("Weekend detected, waiting for next trading day.")
                time.sleep(3600)
                continue
            if now.time() < start_time:
                wait_seconds = int((dt.datetime.combine(now.date(), start_time) - now).total_seconds())
                print(f"Waiting {wait_seconds}s for market start at {start_time}.")
                time.sleep(max(wait_seconds, 1))
                continue
            if now.time() > end_time:
                print("Market session closed for today. Waiting for next day.")
                time.sleep(3600)
                continue
            self.run_session(end_time=end_time, lookback_minutes=lookback_minutes)
            if self.state.has_position:
                print("Session ended with open position. Manual square-off advised.")
            time.sleep(3600)

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

    def _execute_signal(self, side: str, candle: Candle, reason: str) -> None:
        event_time = dt.datetime.now()
        price = candle.close
        if side == "BUY" and self.state.has_position:
            self._status_log(candle, action="BUY_IGNORED", reason="ALREADY_IN_POSITION")
            return
        if side == "SELL" and not self.state.has_position:
            self._status_log(candle, action="SELL_IGNORED", reason="NO_OPEN_POSITION")
            return

        if self.live_orders:
            response = self.client.place_order(
                side=side,
                symbol=self.symbol,
                qty=self.qty,
                exchange_code=self.exchange_code,
                product=self.product,
            )
            print(f"{event_time.isoformat()} | LIVE {side} response: {response}")

        if side == "BUY":
            stop_loss_distance = self._stop_loss_distance(price)
            target_distance = self._target_distance(price)
            trailing_stop_distance = self._trailing_stop_distance(price)
            self.state.has_position = True
            self.state.qty = self.qty
            self.state.entry_price = price
            self.state.entry_time = candle.timestamp
            self.state.highest_price = price
            self.state.stop_loss_price = (price - stop_loss_distance) if stop_loss_distance > 0 else 0.0
            self.state.target_price = (price + target_distance) if target_distance > 0 else 0.0
            self.state.trailing_stop_price = (price - trailing_stop_distance) if trailing_stop_distance > 0 else 0.0

            print(
                f"{event_time.isoformat()} | BUY {self.qty} {self.symbol} @ {price:.2f} | Reason: {reason} "
                f"| SL: {self.state.stop_loss_price:.2f} | TG: {self.state.target_price:.2f} "
                f"| TSL: {self.state.trailing_stop_price:.2f} | Realized P&L: {self.state.realized_pnl:.2f}"
            )
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
            self.logger.log(
                event_time=event_time,
                candle_time=candle.timestamp,
                strategy=self.strategy.name,
                symbol=self.symbol,
                action="BUY",
                reason=reason,
                price=price,
                qty=self.qty,
                state=self.state,
                unrealized_pnl=self._unrealized_pnl(price),
            )
            return

        trade_pnl = (price - self.state.entry_price) * self.state.qty
        self.state.realized_pnl += trade_pnl
        print(
            f"{event_time.isoformat()} | SELL {self.state.qty} {self.symbol} @ {price:.2f} | Reason: {reason} "
            f"| Trade P&L: {trade_pnl:.2f} | Cumulative Realized P&L: {self.state.realized_pnl:.2f}"
        )
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

        self.logger.log(
            event_time=event_time,
            candle_time=candle.timestamp,
            strategy=self.strategy.name,
            symbol=self.symbol,
            action="SELL",
            reason=reason,
            price=price,
            qty=0,
            state=self.state,
            unrealized_pnl=0.0,
        )

    def _status_log(self, candle: Candle, action: str, reason: str) -> None:
        unrealized = self._unrealized_pnl(candle.close)
        event_time = dt.datetime.now()
        print(
            f"{event_time.isoformat()} | {action} @ {candle.close:.2f} | Reason: {reason} "
            f"| Unrealized P&L: {unrealized:.2f} | Realized P&L: {self.state.realized_pnl:.2f}"
        )
        self.logger.log(
            event_time=event_time,
            candle_time=candle.timestamp,
            strategy=self.strategy.name,
            symbol=self.symbol,
            action=action,
            reason=reason,
            price=candle.close,
            qty=self.state.qty,
            state=self.state,
            unrealized_pnl=unrealized,
        )

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


def build_cli() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Breeze live trading bot with pluggable strategies, risk controls, CSV logs and live chart"
    )
    parser.add_argument("--symbol", default="NIFTY-I")
    parser.add_argument("--exchange", default="NSE")
    parser.add_argument("--interval", default="1minute")
    parser.add_argument("--qty", type=int, default=1)
    parser.add_argument("--strategy", default="sma_crossover")
    parser.add_argument("--start-time", default="09:15")
    parser.add_argument("--end-time", default="15:30")
    parser.add_argument("--lookback-minutes", type=int, default=120)
    parser.add_argument("--poll-seconds", type=int, default=60)
    parser.add_argument("--stop-loss-pct", type=float, default=0.7)
    parser.add_argument("--target-pct", type=float, default=1.2)
    parser.add_argument("--trailing-stop-pct", type=float, default=0.5)
    parser.add_argument("--stop-loss-amount", type=float, default=0.0)
    parser.add_argument("--target-amount", type=float, default=0.0)
    parser.add_argument("--trailing-stop-amount", type=float, default=0.0)
    parser.add_argument("--daily", action="store_true", help="Run every trading day within market window")
    parser.add_argument("--live-chart", action="store_true", help="Show live chart window and update chart image")
    parser.add_argument("--chart-file", default="")
    parser.add_argument("--csv-log", default="")
    parser.add_argument("--max-iterations", type=int, default=0, help="0 means unlimited")
    parser.add_argument(
        "--live-orders",
        action="store_true",
        help="Actually place broker orders. Default is paper execution only.",
    )
    return parser


def main() -> None:
    parser = build_cli()
    args = parser.parse_args()

    api_key = os.getenv("API_KEY")
    api_secret = os.getenv("SECRET")
    session_token = os.getenv("TOKEN")

    if not api_key or not api_secret or not session_token:
        raise RuntimeError(
            "Set API_KEY, SECRET and TOKEN environment variables"
        )

    if args.stop_loss_pct < 0 or args.target_pct < 0 or args.trailing_stop_pct < 0:
        raise ValueError("stop-loss, target and trailing-stop percentages must be non-negative")
    if args.stop_loss_amount < 0 or args.target_amount < 0 or args.trailing_stop_amount < 0:
        raise ValueError("stop-loss, target and trailing-stop amounts must be non-negative")

    strategy = StrategyFactory.create(args.strategy)
    client = BreezeLiveClient(api_key=api_key, api_secret=api_secret, session_token=session_token)

    today_compact = dt.date.today().strftime("%Y%m%d")
    today_iso = dt.date.today().isoformat()
    live_log_dir = Path("logs") / "live_trading" / today_iso
    csv_path = Path(args.csv_log) if args.csv_log else (live_log_dir / f"trade_tracker_{today_compact}.csv")
    chart_output = Path(args.chart_file) if args.chart_file else (live_log_dir / "live_chart.html")
    chart = LiveChart(enabled=args.live_chart, output_file=chart_output)
    logger = TradeCSVLogger(csv_path=csv_path)

    bot = LiveTradingBot(
        client=client,
        strategy=strategy,
        symbol=args.symbol,
        exchange_code=args.exchange,
        interval=args.interval,
        qty=args.qty,
        poll_seconds=args.poll_seconds,
        live_orders=args.live_orders,
        stop_loss_pct=args.stop_loss_pct,
        target_pct=args.target_pct,
        trailing_stop_pct=args.trailing_stop_pct,
        stop_loss_amount=args.stop_loss_amount,
        target_amount=args.target_amount,
        trailing_stop_amount=args.trailing_stop_amount,
        logger=logger,
        chart=chart,
        max_iterations=args.max_iterations,
    )

    print(f"CSV trade tracker: {csv_path.resolve()}")
    print(
        "Risk config "
        f"(amount takes precedence over pct): "
        f"SL amount={args.stop_loss_amount}, SL pct={args.stop_loss_pct}, "
        f"Target amount={args.target_amount}, Target pct={args.target_pct}, "
        f"TSL amount={args.trailing_stop_amount}, TSL pct={args.trailing_stop_pct}"
    )
    if args.live_chart:
        print(f"Live chart file: {chart_output.resolve()}")

    start_time = parse_time(args.start_time)
    end_time = parse_time(args.end_time)
    if args.daily:
        bot.run_daily(start_time=start_time, end_time=end_time, lookback_minutes=args.lookback_minutes)
    else:
        now = dt.datetime.now().time()
        if now < start_time:
            wait_seconds = int((dt.datetime.combine(dt.date.today(), start_time) - dt.datetime.now()).total_seconds())
            print(f"Waiting {wait_seconds}s for market start at {start_time}.")
            time.sleep(max(wait_seconds, 1))
        bot.run_session(end_time=end_time, lookback_minutes=args.lookback_minutes)


if __name__ == "__main__":
    main()
