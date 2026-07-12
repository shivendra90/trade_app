import argparse
import datetime as dt
import os
import webbrowser
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import plotly.graph_objects as go
from breeze_connect import BreezeConnect
from plotly.subplots import make_subplots


def parse_date(value: str) -> dt.date:
    return dt.datetime.strptime(value, "%Y-%m-%d").date()


def parse_time(value: str) -> dt.time:
    return dt.datetime.strptime(value, "%H:%M").time()


def load_credentials() -> Dict[str, str]:
    api_key = os.getenv("BREEZE_API_KEY")
    api_secret = os.getenv("BREEZE_API_SECRET")
    session_token = os.getenv("BREEZE_SESSION_TOKEN")
    if not api_key or not api_secret or not session_token:
        raise RuntimeError(
            "Set BREEZE_API_KEY, BREEZE_API_SECRET and BREEZE_SESSION_TOKEN environment variables"
        )
    return {"api_key": api_key, "api_secret": api_secret, "session_token": session_token}


def extract_rows(response: Any) -> List[Dict[str, Any]]:
    if isinstance(response, list):
        return response
    if isinstance(response, dict):
        if "Success" in response and isinstance(response["Success"], list):
            return response["Success"]
        if "data" in response and isinstance(response["data"], list):
            return response["data"]
    raise ValueError(f"Unexpected response format: {response}")


def fetch_ohlc(
    breeze: BreezeConnect,
    symbol: str,
    exchange: str,
    interval: str,
    target_date: dt.date,
    start_time: dt.time,
    end_time: dt.time,
) -> pd.DataFrame:
    from_dt = dt.datetime.combine(target_date, start_time)
    to_dt = dt.datetime.combine(target_date, end_time)

    response = breeze.get_historical_data_v2(
        interval=interval,
        from_date=from_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        to_date=to_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        stock_code=symbol,
        exchange_code=exchange,
    )
    rows = extract_rows(response)
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    datetime_col = "datetime" if "datetime" in df.columns else ("date" if "date" in df.columns else "timestamp")
    if datetime_col not in df.columns:
        raise ValueError("Could not find datetime/date/timestamp column in Breeze response")

    df["datetime"] = pd.to_datetime(df[datetime_col])
    for col in ("open", "high", "low", "close", "volume"):
        if col not in df.columns:
            title_col = col.capitalize()
            if title_col in df.columns:
                df[col] = df[title_col]
    if "volume" not in df.columns:
        df["volume"] = 0

    df = df[["datetime", "open", "high", "low", "close", "volume"]].copy()
    df[["open", "high", "low", "close", "volume"]] = df[["open", "high", "low", "close", "volume"]].apply(
        pd.to_numeric, errors="coerce"
    )
    df = df.dropna(subset=["datetime", "open", "high", "low", "close"]).sort_values("datetime")
    return df


def build_chart(df: pd.DataFrame, symbol: str, exchange: str, interval: str, target_date: dt.date) -> go.Figure:
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        row_heights=[0.75, 0.25],
        subplot_titles=(f"{symbol} Candlestick", "Volume"),
    )

    fig.add_trace(
        go.Candlestick(
            x=df["datetime"],
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            name="OHLC",
            hovertemplate="<b>%{x|%Y-%m-%d %H:%M}</b><br>O: %{open:.2f}<br>H: %{high:.2f}<br>L: %{low:.2f}<br>C: %{close:.2f}<extra></extra>",
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Bar(
            x=df["datetime"],
            y=df["volume"],
            name="Volume",
            marker_color="#5DADE2",
            hovertemplate="<b>%{x|%Y-%m-%d %H:%M}</b><br>Volume: %{y:.0f}<extra></extra>",
        ),
        row=2,
        col=1,
    )

    fig.update_layout(
        template="plotly_white",
        title=f"{symbol} ({exchange}) | {interval} | {target_date.isoformat()}",
        xaxis_rangeslider_visible=False,
        hovermode="x unified",
        height=850,
    )
    fig.update_xaxes(title_text="Time", row=2, col=1)
    fig.update_yaxes(title_text="Price", row=1, col=1)
    fig.update_yaxes(title_text="Volume", row=2, col=1)
    return fig


def build_cli() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Visualize a specified day OHLC chart from Breeze API using Plotly")
    parser.add_argument("--symbol", default="NIFTY-I")
    parser.add_argument("--exchange", default="NSE")
    parser.add_argument("--interval", default="1minute")
    parser.add_argument("--date", default=dt.date.today().isoformat(), help="YYYY-MM-DD")
    parser.add_argument("--start-time", default="09:15")
    parser.add_argument("--end-time", default="15:30")
    parser.add_argument("--output", default="", help="Output HTML path")
    return parser


def main() -> None:
    parser = build_cli()
    args = parser.parse_args()

    target_date = parse_date(args.date)
    start_time = parse_time(args.start_time)
    end_time = parse_time(args.end_time)

    creds = load_credentials()
    breeze = BreezeConnect(api_key=creds["api_key"])
    breeze.generate_session(api_secret=creds["api_secret"], session_token=creds["session_token"])

    df = fetch_ohlc(
        breeze=breeze,
        symbol=args.symbol,
        exchange=args.exchange,
        interval=args.interval,
        target_date=target_date,
        start_time=start_time,
        end_time=end_time,
    )
    if df.empty:
        raise RuntimeError(f"No OHLC data found for {args.symbol} on {target_date.isoformat()}")

    if args.output:
        output_path = Path(args.output)
    else:
        output_path = Path("logs") / "charts" / target_date.isoformat() / f"{args.symbol}_{args.interval}.html"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fig = build_chart(df, args.symbol, args.exchange, args.interval, target_date)
    fig.write_html(str(output_path))
    webbrowser.open(output_path.resolve().as_uri())

    print(f"Candles fetched: {len(df)}")
    print(f"Chart written to: {output_path.resolve()}")


if __name__ == "__main__":
    main()
