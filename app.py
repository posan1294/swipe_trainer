import os
import random
from functools import lru_cache

import pandas as pd
import yfinance as yf
from flask import Flask, jsonify, render_template

app = Flask(__name__)

STOCK_NAMES = {
    "7203.T": "トヨタ自動車",       "6758.T": "ソニーグループ",
    "9984.T": "ソフトバンクグループ","6861.T": "キーエンス",
    "8306.T": "三菱UFJ",            "9432.T": "NTT",
    "7267.T": "ホンダ",             "6501.T": "日立製作所",
    "4502.T": "武田薬品工業",        "8035.T": "東京エレクトロン",
    "9433.T": "KDDI",               "6752.T": "パナソニック",
    "7974.T": "任天堂",             "4063.T": "信越化学工業",
    "8316.T": "三井住友FG",         "3382.T": "セブン&アイ",
    "9983.T": "ファーストリテイリング","6098.T": "リクルートHD",
    "4503.T": "アステラス製薬",      "8267.T": "イオン",
    "2802.T": "味の素",             "6723.T": "ルネサス",
    "9020.T": "JR東日本",           "5401.T": "日本製鉄",
    "6857.T": "アドバンテスト",      "4385.T": "メルカリ",
    "2503.T": "キリンHD",           "8411.T": "みずほFG",
    "7269.T": "スズキ",             "4755.T": "楽天グループ",
    "7201.T": "日産自動車",         "4519.T": "中外製薬",
    "4568.T": "第一三共",           "2801.T": "キッコーマン",
    "6902.T": "デンソー",           "7270.T": "SUBARU",
    "8604.T": "野村HD",             "8591.T": "オリックス",
    "2413.T": "エムスリー",         "9697.T": "カプコン",
}

STOCKS_JP    = list(STOCK_NAMES.keys())
DISPLAY_DAYS = 400
PREDICT_DAYS = 120
THRESHOLD    = 0.10


@lru_cache(maxsize=50)
def _fetch(ticker_code: str):
    try:
        df = yf.download(ticker_code, period="5y", progress=False, auto_adjust=True)
        if df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df[["Open", "High", "Low", "Close"]].dropna()
        if len(df) < DISPLAY_DAYS + PREDICT_DAYS + 50:
            return None
        df["MA5"]   = df["Close"].rolling(5).mean()
        df["MA25"]  = df["Close"].rolling(25).mean()
        df["MA75"]  = df["Close"].rolling(75).mean()
        df["MA200"] = df["Close"].rolling(200).mean()
        return df
    except Exception:
        return None


def generate_question():
    stocks = STOCKS_JP.copy()
    random.shuffle(stocks)

    for ticker in stocks:
        df = _fetch(ticker)
        if df is None:
            continue

        min_cut = DISPLAY_DAYS
        max_cut = len(df) - PREDICT_DAYS - 1
        if min_cut >= max_cut:
            continue

        cut_idx = random.randint(min_cut, max_cut)
        display = df.iloc[cut_idx - DISPLAY_DAYS : cut_idx]
        future  = df.iloc[cut_idx : cut_idx + PREDICT_DAYS]

        if len(display) < 200 or len(future) < PREDICT_DAYS:
            continue

        def to_candles(df_slice, offset=0):
            out = []
            for i, (_, row) in enumerate(df_slice.iterrows()):
                out.append({
                    "x": offset + i + 1,
                    "y": [round(float(row["Open"]),  2),
                          round(float(row["High"]),  2),
                          round(float(row["Low"]),   2),
                          round(float(row["Close"]), 2)],
                })
            return out

        def to_line(col):
            out = []
            for i, (_, row) in enumerate(display.iterrows()):
                if pd.notna(row[col]):
                    out.append({"x": i + 1, "y": round(float(row[col]), 2)})
            return out

        price_start = float(display["Close"].iloc[-1])
        price_end   = float(future["Close"].iloc[-1])
        actual_pct  = (price_end - price_start) / price_start
        answer      = "up" if actual_pct >= THRESHOLD else "down"

        # 時期：チャート末尾の年月（予想開始時点）
        cut_date = display.index[-1]
        period   = f"{cut_date.year}年{cut_date.month}月"

        code = ticker.replace(".T", "")

        return {
            "candles":        to_candles(display),
            "reveal_candles": to_candles(future, offset=DISPLAY_DAYS),
            "ma5":            to_line("MA5"),
            "ma25":           to_line("MA25"),
            "ma75":           to_line("MA75"),
            "ma200":          to_line("MA200"),
            "answer":         answer,
            "actual_pct":     round(actual_pct * 100, 1),
            "cut_x":          DISPLAY_DAYS,
            "stock_code":     code,
            "stock_name":     STOCK_NAMES.get(ticker, ticker),
            "period":         period,
        }

    return None


@app.route("/")
def index():
    resp = app.make_response(render_template("index.html"))
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    return resp


@app.route("/api/question")
def question():
    data = generate_question()
    if data is None:
        return jsonify({"error": "Failed to generate question"}), 500
    return jsonify(data)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
