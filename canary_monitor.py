import yfinance as yf
import json
import datetime
import os
import requests

INFRA_TIERS = {
    'TIER_0': ['UNG', 'UNL', 'EQT', 'KMI'],         # UNG(期近), UNL(12ヶ月分散)を利用してスプレッドを計算
    'TIER_1': ['CEG', 'VRT', 'ETN', 'EQIX'],        
    'TIER_1_5': ['SMCI', 'ANET'],                   
    'TIER_2': ['CRWV', 'NBIS'],                     
    'TIER_3': ['FCX', 'SCCO', 'CCJ', 'URA'],        
    'TIER_4': ['NOW', 'WDAY', 'CRM', 'SAP', 'VEEV', 'HUBS', 'SNOW', 'TDC', 'ZS', 'MDB', 'PAYC', 'INTU', 'ADBE']
}

def fetch_market_data():
    all_tickers = []
    for tickers in INFRA_TIERS.values():
        all_tickers.extend(tickers)
        
    print(f"[*] Fetching Infrastructure Snapshot v11.1: {all_tickers}")
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

def calculate_natgas_spread(details):
    """
    仕様書に基づく構造的カレンダースプレッドの近似計算
    UNG(期近特化) と UNL(12ヶ月分散) の価格比率から、遠月物のプレミアム/ディスカウントを判定
    """
    try:
        unl_price = details.get('UNL', {}).get('price', 0)
        ung_price = details.get('UNG', {}).get('price', 0)
        
        # 期近(UNG)が暴落し、遠月(UNL)が耐えている場合はノイズ。
        # 逆に、比率が縮小（遠月が売られている）場合は構造的崩壊のシグナル。
        if ung_price > 0:
            spread_ratio = unl_price / ung_price
            return round(spread_ratio, 3)
        return 0
    except:
        return 0

def run_diagnostic(tier_averages, spread_ratio, details):
    t0_avg = tier_averages.get('TIER_0', 0)
    t1 = tier_averages.get('TIER_1', 0)
    t2 = tier_averages.get('TIER_2', 0)
    t3 = tier_averages.get('TIER_3', 0)
    t4 = tier_averages.get('TIER_4', 0)

    # UNL(遠月分散) と UNG(期近) の変動を取得
    unl_change = details.get('UNL', {}).get('change', 0)
    ung_change = details.get('UNG', {}).get('change', 0)

    # 1. 🔴 状態1: 【需要幻滅の死】(Demand Collapse)
    # 遠月物(UNL)が急落 かつ 期近(UNG)より下落幅が大きい（スプレッド縮小）＋インフラ株安
    if unl_change < -1.5 and unl_change < ung_change and t1 < -1.0:
        return "🔴 【需要幻滅の死】遠月ガス(UNL)が主導する下落。DC建設計画自体の凍結・キャンセル警戒"

    # 2. 🟡 状態2: 【天候ノイズ・短期パニック】 (Weather/Short-Term Noise)
    # 期近(UNG)は急落しているが、遠月(UNL)は横ばい〜上昇 ＋インフラ株は無傷
    elif ung_change < -2.0 and unl_change >= 0 and t1 >= 0:
        return "🟡 【天候ノイズフィルター稼働】期近ガス(UNG)急落も遠月は無風。インフラの構造的需要は無傷"

    # 3. 🟠 状態3: 【コスト限界・スタグフレーション】 (Cost Squeeze)
    # 遠月(UNL)が異常急騰 ＋ インフラ株(T1)が下落
    elif unl_change > 2.0 and t1 < -1.0:
        return "🟠 【コスト限界】遠月ガス(UNL)急騰。インフラ企業の利益率が物理限界により圧迫されている"

    # --- 以下、既存の株式レイヤー判定 ---
    elif t1 < -1.0 and t2 < -1.0 and t4 > 0.5:
        return "🟢 【健全なローテーション】インフラ売却・データ資源買い。テクノロジー全体の崩壊ではない"

    elif t1 < -1.0 and t2 < -1.0 and t4 < -1.0:
        return "🔴 【真のパニック崩壊】インフラからデータ要塞まで全リスク資産からの資金流出"

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
    spread_ratio = calculate_natgas_spread(details)
    status_msg = run_diagnostic(tier_averages, spread_ratio, details)

    line_msg = f"⚠️ Canary Radar v11.1 (Macro-Integrated)\n判定: {status_msg}\n\n"
    line_msg += f"■ T0 (ｴﾈﾙｷﾞｰ): UNG={details.get('UNG',{}).get('change',0)}%, UNL={details.get('UNL',{}).get('change',0)}%\n"
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
        "spread_ratio": spread_ratio,
        "status": status_msg,
        "details": details
    }

    with open('dashboard_data.json', 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
        
if __name__ == "__main__":
    main()
