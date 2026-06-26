import yfinance as yf
import json
import datetime
import os

# --- 監視対象の階層構造（Tier 1.5 構成） ---
INFRA_TIERS = {
    'TIER_1': ['CEG', 'VRT', 'ETN', 'EQIX'],  # Foundation (物理基盤)
    'TIER_1_5': ['SMCI', 'ANET'],             # Compute & Fabric (演算・接続)
    'TIER_2': ['CRWV', 'NBIS']                # Velocity (稼働・サービス)
}

def fetch_market_data():
    all_tickers = []
    for tickers in INFRA_TIERS.values():
        all_tickers.extend(tickers)
        
    print(f"[*] Fetching Infrastructure Snapshot: {all_tickers}")
    try:
        data = yf.download(all_tickers, period="2d", group_by="ticker", auto_adjust=False)
    except Exception as e:
        print(f"[!] Error fetching data: {e}")
        return None

    results = {}
    for ticker in all_tickers:
        try:
            if len(all_tickers) == 1:
                ticker_data = data
            else:
                ticker_data = data[ticker]
            
            closes = ticker_data['Close'].dropna().values
            if len(closes) >= 2:
                latest = closes[-1]
                prev = closes[-2]
                change_pct = ((latest - prev) / prev) * 100
                results[ticker] = {
                    "price": round(float(latest), 2),
                    "change": round(float(change_pct), 2)
                }
            else:
                # 新規上場などで2日分のデータがない場合のフォールバック
                latest = closes[-1] if len(closes) > 0 else 0
                results[ticker] = {
                    "price": round(float(latest), 2),
                    "change": 0.0
                }
        except Exception as e:
            print(f"[!] Could not process {ticker}: {e}")
            
    return results

def calculate_tier_averages(data_details):
    tier_averages = {}
    for tier_name, tickers in INFRA_TIERS.items():
        changes = [data_details[t]["change"] for t in tickers if t in data_details]
        avg = sum(changes) / len(changes) if changes else 0
        tier_averages[tier_name] = round(avg, 2)
    return tier_averages

def run_diagnostic(tier_averages):
    t1 = tier_averages.get('TIER_1', 0)
    t15 = tier_averages.get('TIER_1_5', 0)
    t2 = tier_averages.get('TIER_2', 0)

    if t1 < -1.0 and t2 < -1.0:
        return "🔴 【崩壊確定】物理・演算ともに資金流出。インフラバブルの破裂"
    elif t1 >= 0 and t2 < -1.0:
        return "🟡 【質の逃避】物理基盤は堅調だが、期待値層(Tier 2)から資金が抜けている"
    elif t1 < 0 and t15 > 1.0:
        return "🟠 【ボトルネック警戒】基盤構築よりサーバー投資が過熱。供給網の歪み"
    elif t1 >= 0 and t2 >= 0:
        return "🟢 【正常】物理基盤と演算層に資金が流入しており健全"
    else:
        return "⚪ 【注視】各層で強弱が混在。トレンドの明確化を待て"

def main():
    details = fetch_market_data()
    if not details:
        return

    tier_averages = calculate_tier_averages(details)
    status_msg = run_diagnostic(tier_averages)

    output_data = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "config": INFRA_TIERS,
        "layers": tier_averages,
        "status": status_msg,
        "details": details
    }

    # JSONファイルとして出力
    with open('dashboard_data.json', 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
        
    print(f"[+] Diagnostic Result: {status_msg}")
    print("[+] Data saved to dashboard_data.json")

if __name__ == "__main__":
    main()
