import yfinance as yf
import json
import datetime
import os
import requests

# --- Canary Radar v11.0: Tier 0 (Macro Energy) 統合構成 ---
INFRA_TIERS = {
    'TIER_0': ['NG=F', 'EQT', 'KMI'],               # Macro Energy (天然ガス先物/インフラプロキシ)
    'TIER_1': ['CEG', 'VRT', 'ETN', 'EQIX'],        # Foundation (物理基盤)
    'TIER_1_5': ['SMCI', 'ANET'],                   # Compute & Fabric (演算・接続)
    'TIER_2': ['CRWV', 'NBIS'],                     # Velocity (AIクラウド)
    'TIER_3': ['FCX', 'SCCO', 'CCJ', 'URA'],        # Upstream (資源・素材)
    'TIER_4': ['NOW', 'WDAY', 'CRM', 'SAP', 'VEEV', 
               'HUBS', 'SNOW', 'TDC', 'ZS', 'MDB', 
               'PAYC', 'INTU', 'ADBE']              # True Asset (データ資源・関所)
}

def fetch_market_data():
    all_tickers = []
    for tickers in INFRA_TIERS.values():
        all_tickers.extend(tickers)
        
    print(f"[*] Fetching Infrastructure Snapshot v11.0: {all_tickers}")
    try:
        data = yf.download(all_tickers, period="5d", group_by="ticker", auto_adjust=False)
    except Exception as e:
        print(f"[!] Error fetching data: {e}")
        return None

    results = {}
    for ticker in all_tickers:
        try:
            ticker_data = data if len(all_tickers) == 1 else data[ticker]
            closes = ticker_data['Close'].dropna().values
            volumes = ticker_data['Volume'].dropna().values
            
            if len(closes) >= 2:
                latest = closes[-1]
                prev = closes[-2]
                change_pct = ((latest - prev) / prev) * 100
                
                # ボリューム・サージ算出 (NG=F等の先物はVolumeが0/NaNになる場合があるため安全処理)
                vol_surge = 1.0
                if len(volumes) > 1 and sum(volumes[:-1]) > 0:
                    avg_vol = sum(volumes[:-1]) / len(volumes[:-1])
                    vol_surge = (volumes[-1] / avg_vol) if avg_vol > 0 else 1.0

                results[ticker] = {
                    "price": round(float(latest), 2),
                    "change": round(float(change_pct), 2),
                    "vol_surge": round(float(vol_surge), 2)
                }
            else:
                results[ticker] = {"price": 0.0, "change": 0.0, "vol_surge": 1.0}
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
    t0 = tier_averages.get('TIER_0', 0)
    t1 = tier_averages.get('TIER_1', 0)
    t2 = tier_averages.get('TIER_2', 0)
    t3 = tier_averages.get('TIER_3', 0)
    t4 = tier_averages.get('TIER_4', 0)

    # 1. Tier 0 発動: 根源的な需要幻滅（エネルギー限界の崩壊）
    if t0 < -2.0 and t1 < -1.0:
        return "🔴 【需要幻滅】Tier 0(エネルギー)崩壊。データセンター建設計画自体の凍結・キャンセル警戒"

    # 2. Tier 0 発動: コスト限界・スタグフレーション（燃料高騰による利益圧迫）
    elif t0 > 2.0 and t1 < -1.0:
        return "🟠 【コスト限界】Tier 0(ガス・燃料)急騰。インフラ企業の利益率が物理限界により圧迫されている"

    # 3. 資金ローテーション（インフラ安・データ資源高）
    elif t1 < -1.0 and t2 < -1.0 and t4 > 0.5:
        return "🟢 【健全なローテーション】インフラ売却・データ資源買い。テクノロジー全体の崩壊ではない"

    # 4. 真の全面崩壊（相関1のパニック）
    elif t1 < -1.0 and t2 < -1.0 and t4 < -1.0:
        return "🔴 【真のパニック崩壊】インフラからデータ要塞まで全リスク資産からの資金流出"

    # 5. データ資源の単独安（AIによる既存SaaSの破壊懸念）
    elif t1 >= 0 and t4 < -1.0:
        return "🟡 【AI破壊の恐れ】インフラは堅調だが、既存のデータ資源層(Tier 4)が売られている"

    elif t1 >= 0 and t2 >= 0 and t4 >= 0:
        return "🟢 【正常】エネルギーからデータ層まで資金が循環"
    
    else:
        return "⚪ 【注視】各レイヤーで強弱が混在"

def send_line_messaging_api(message):
    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    user_id = os.environ.get("LINE_USER_ID")
    if not token or not user_id: return
        
    url = "https://api.line.me/v2/bot/message/push"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    data = {"to": user_id, "messages": [{"type": "text", "text": message}]}
    requests.post(url, headers=headers, json=data)

def main():
    details = fetch_market_data()
    if not details: return

    tier_averages = calculate_tier_averages(details)
    status_msg = run_diagnostic(tier_averages)

    line_msg = f"⚠️ Canary Radar v11.0\n判定: {status_msg}\n\n"
    line_msg += f"■ T0 (ｴﾈﾙｷﾞｰ): {tier_averages['TIER_0']}%\n"
    line_msg += f"■ T1 (物理基盤): {tier_averages['TIER_1']}%\n"
    line_msg += f"■ T2 (AIクラウド): {tier_averages['TIER_2']}%\n"
    line_msg += f"■ T3 (資源素材): {tier_averages['TIER_3']}%\n"
    line_msg += f"■ T4 (データ資源): {tier_averages['TIER_4']}%\n"
    line_msg += f"\nダッシュボード:\nhttps://k1rpapa.github.io/aicollapse-canary-radar/"
    
    send_line_messaging_api(line_msg)

    output_data = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "config": INFRA_TIERS,
        "layers": tier_averages,
        "status": status_msg,
        "details": details
    }

    with open('dashboard_data.json', 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
        
if __name__ == "__main__":
    main()
