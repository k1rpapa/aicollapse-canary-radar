import yfinance as yf
import json
import datetime
import os
import requests

# --- 監視対象の階層構造（Tier 3 追加のフルスタック構成） ---
INFRA_TIERS = {
    'TIER_1': ['CEG', 'VRT', 'ETN', 'EQIX'],  # Foundation (物理基盤: 電力・冷却)
    'TIER_1_5': ['SMCI', 'ANET'],             # Compute & Fabric (演算・接続: サーバー・網)
    'TIER_2': ['CRWV', 'NBIS'],               # Velocity (稼働・サービス: AIクラウド)
    'TIER_3': ['FCX', 'SCCO', 'CCJ', 'URA']   # Upstream (資源・素材: 銅・ウラン)
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
    t3 = tier_averages.get('TIER_3', 0)

    # 1. 最悪のシナリオ: 資源高騰(T3>0) ＋ インフラ投資死滅(T1,T2崩壊)
    if t3 > 0 and t1 < -1.0 and t2 < -1.0:
        return "🔴 【致命的崩壊】資源高騰下でのインフラ投資死滅。最悪のスタグフレーション"
    
    # 2. 全面崩壊: 資源から末端まで全てから資金流出 (T3の微マイナスも拾うように修正)
    elif t1 < -1.0 and t2 < -1.0 and t3 <= 0:
        return "🔴 【全面崩壊】資源からクラウドまでAIインフラ全層からの資金流出"

    # 3. コスト限界: 資源が高騰し、インフラ基盤の採算が悪化し始めている
    elif t3 > 1.0 and t1 < 0:
        return "🟠 【コスト限界】資源(銅/ウラン)高騰がインフラ構築の採算を圧迫している"

    # 4. 質の逃避: 物理は買われているが、夢(クラウド)が売られている
    elif t1 >= 0 and t2 < -1.0:
        return "🟡 【質の逃避】物理基盤は堅調だが、期待値層(Tier 2)から資金が抜けている"

    # 5. ボトルネック警戒: 箱(物理)が建っていないのに、中身(サーバー)だけ買われている
    elif t1 < 0 and t15 > 1.0:
        return "🟡 【供給網歪み】基盤構築よりサーバー投資が過熱。ボトルネック警戒"

    # 6. 完全正常
    elif t1 >= 0 and t15 >= 0 and t2 >= 0 and t3 >= 0:
        return "🟢 【正常】資源から演算層まで資金が循環しており極めて健全"

    # 7. その他(トレンド形成待ち)
    else:
        return "⚪ 【注視】各レイヤーで強弱が混在。トレンドの明確化を待て"

def send_line_notify(message):
    token = os.environ.get("LINE_NOTIFY_TOKEN")
    if not token:
        print("[-] LINE_NOTIFY_TOKEN is not set. Skipping LINE notification.")
        return
    url = "https://notify-api.line.me/api/notify"
    headers = {"Authorization": f"Bearer {token}"}
    data = {"message": message}
    try:
        response = requests.post(url, headers=headers, data=data)
        if response.status_code == 200:
            print("[+] LINE notification sent successfully.")
        else:
            print(f"[!] LINE API Error: {response.status_code}")
    except Exception as e:
        print(f"[!] Failed to send LINE notification: {e}")

def main():
    details = fetch_market_data()
    if not details:
        return

    tier_averages = calculate_tier_averages(details)
    status_msg = run_diagnostic(tier_averages)

    # LINE通知用のメッセージ構築
    line_msg = f"\n⚠️ AIインフラ監視レポート\n"
    line_msg += f"判定: {status_msg}\n\n"
    line_msg += f"■ T1 (物理基盤): {tier_averages['TIER_1']}%\n"
    line_msg += f"■ T1.5 (演算基盤): {tier_averages['TIER_1_5']}%\n"
    line_msg += f"■ T2 (AIサービス): {tier_averages['TIER_2']}%\n"
    line_msg += f"■ T3 (資源・上流): {tier_averages['TIER_3']}%\n"
    line_msg += f"\nダッシュボードを確認:\nhttps://k1rpapa.github.io/aicollapse-canary-radar/"
    
    # LINE送信
    send_line_notify(line_msg)

    output_data = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "config": INFRA_TIERS,
        "layers": tier_averages,
        "status": status_msg,
        "details": details
    }

    with open('dashboard_data.json', 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
        
    print(f"[+] Diagnostic Result: {status_msg}")
    print("[+] Data saved to dashboard_data.json")

if __name__ == "__main__":
    main()
