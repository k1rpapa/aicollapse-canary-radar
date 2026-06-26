import os
import json
import requests
import statistics
import yfinance as yf
from datetime import datetime, timezone, timedelta

# =========================================================================
# CanaryInTheGrid v9.5 - Three-Tier Physical Infrastructure Monitor
# =========================================================================

# インフラ三層構造の定義
MONITOR_CONFIG = {
    "TIER_1": ["CEG", "VRT", "ETN", "EQIX"],  # Foundation: 物理的基盤
    "TIER_1_5": ["SMCI", "ANET"],             # Fabric: 演算・接続
    "TIER_2": ["CRWV", "NBIS"]               # Velocity: 演算・サービス
}

def fetch_market_data():
    all_tickers = []
    for layer in MONITOR_CONFIG.values():
        all_tickers.extend(layer)
    
    print(f"[*] Fetching Infrastructure Snapshot: {all_tickers}")
    results = {}
    
    # 複数銘柄を一括取得
    tickers_str = " ".join(all_tickers)
    data = yf.download(tickers_str, period="5d", group_by='ticker')
    
    for ticker in all_tickers:
        try:
            ticker_data = data[ticker] if len(all_tickers) > 1 else data
            curr = float(ticker_data['Close'].iloc[-1])
            prev = float(ticker_data['Close'].iloc[-2])
            pct_change = ((curr - prev) / prev) * 100
            results[ticker] = {"price": round(curr, 2), "change": round(pct_change, 2)}
        except Exception as e:
            print(f"[-] Data Error for {ticker}: {e}")
            results[ticker] = {"price": 0.0, "change": 0.0}
            
    return results

def aggregate_layer_metrics(data):
    metrics = {}
    for layer_name, tickers in MONITOR_CONFIG.items():
        changes = [data[t]["change"] for t in tickers if data[t]["price"] > 0]
        avg_change = sum(changes) / len(changes) if changes else 0
        metrics[layer_name] = round(avg_change, 2)
    return metrics

def run_diagnostic(metrics):
    t1 = metrics["TIER_1"]
    t15 = metrics["TIER_1_5"]
    t2 = metrics["TIER_2"]
    
    # 修正済みロジック: 物理基盤(t1)の健常性を最優先する
    if t1 < -2.0:
        return "🔴 【物理崩壊】基盤層の全面安。AIバブルは終焉した"
    elif t1 > 0 and t2 < -2.0:
        return "🟡 【質の逃避】TIER1は堅調。TIER2への投機マネーのみが枯渇"
    elif t15 < -1.0 and t2 < -1.0:
        return "🟠 【減速】演算能力の供給過剰懸念。マネタイズへの疑念"
    else:
        return "🟢 【正常】物理基盤に資本が流入しており健全"

    if t2 < t1 and t15 < t1:
        return "🔴 【崩壊確定】物理基盤からの資金逃避。AIインフラバブル崩壊"
    elif t2 < t15:
        return "🟠 【警戒】演算・接続層への疑念。マネタイズへの疑問符"
    elif t15 < t1:
        return "🟡 【ボトルネック】物理基盤は堅調だが、ハードウェア供給が遅延"
    else:
        return "🟢 【正常】物理基盤からクラウド層まで健全な資本流入"

if __name__ == "__main__":
    # 1. データ収集
    data = fetch_market_data()
    
    # 2. 層ごとの集計
    layer_metrics = aggregate_layer_metrics(data)
    
    # 3. 診断
    health_status = run_diagnostic(layer_metrics)
    
    # 結果表示
    output = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "layers": layer_metrics,
        "status": health_status,
        "details": data,
        "config": MONITOR_CONFIG # HTML側に構造を教えるため追加
    }
    
    # dashboard_data.json に保存
    with open('dashboard_data.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
        
    print(json.dumps(output, indent=2))
    print(f"[+] Diagnostic Result: {health_status}")
    print(f"[+] Data exported to dashboard_data.json")