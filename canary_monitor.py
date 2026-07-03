import os
import json
import requests
from datetime import datetime, timezone, timedelta
from collections import defaultdict
import yfinance as yf
import pandas as pd

# ==========================================
# 1. アラート発報モジュール（LINE Messaging API）
# ==========================================
def send_line_alert(message):
    """異常値を検知した際、直ちにLINEへプッシュ通知を飛ばす"""
    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    user_id = os.environ.get("LINE_USER_ID")

    if not token or not user_id:
        print("Warning: LINE credentials not found. Skipping alert push.")
        return

    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    payload = {
        "to": user_id,
        "messages": [{"type": "text", "text": message}]
    }

    try:
        res = requests.post(url, headers=headers, json=payload, timeout=10)
        res.raise_for_status()
        print("🟢 LINE Alert Executed Successfully.")
    except Exception as e:
        print(f"🔴 Failed to execute LINE Alert: {e}")

# ==========================================
# 2. 金融レイヤー：マージナル・セッター（天然ガス）監視
# ==========================================
def fetch_forward_curve():
    """Henry Hub天然ガス先物の期近・期先スプレッドを算出し、死のカナリアを検知する"""
    print("[*] Fetching Forward Curve Data...")
    try:
        tickers = yf.Tickers("NG=F NGZ27.NYM")
        near_hist = tickers.tickers['NG=F'].history(period="1d")
        far_hist = tickers.tickers['NGZ27.NYM'].history(period="1d")
        
        if near_hist.empty or far_hist.empty:
            return None
            
        near_price = float(near_hist['Close'].iloc[-1])
        far_price = float(far_hist['Close'].iloc[-1])
        spread = far_price - near_price
        
        # 物理限界（バックワーデーション）の検知トリガー
        if spread < 0:
            signal = "🚨 【警報】バックワーデーション（バブル崩壊の兆候）"
            alert_msg = (
                "⚠️ 【CanaryInTheGrid 限界突破アラート】\n\n"
                "マージナル・セッター（天然ガス先物）の期間構造が崩壊しました。\n"
                "AIデータセンター増設の物理的限界を市場が織り込み始めた可能性があります。\n\n"
                f"期近 (NG=F): ${round(near_price, 3)}\n"
                f"期先 (Dec 27): ${round(far_price, 3)}\n"
                f"スプレッド(Δ): ${round(spread, 3)}\n\n"
                "直ちにダッシュボードを確認し、WTI及びコッパーのショート/ロングを再評価してください。"
            )
            send_line_alert(alert_msg)
        else:
            signal = "✅ 【正常】コンタンゴ（順ざや維持）"
            
        return {
            "near_month_ticker": "NG=F (Front Month)",
            "near_month_price": round(near_price, 3),
            "far_month_ticker": "NGZ27.NYM (Dec 2027)",
            "far_month_price": round(far_price, 3),
            "spread_delta": round(spread, 3),
            "signal": signal
        }
    except Exception as e:
        print(f"[!] Forward Curve Error: {e}")
        return None

# ==========================================
# 3. 物理レイヤー：PJM実需オーバーシュート監視
# ==========================================
def fetch_physical_grid_data():
    """EIA APIから米国東部(PJM)の物理的な電力需要を取得し、5年レンジと比較する"""
    print("[*] Fetching PJM Physical Grid Data from EIA...")
    api_key = os.environ.get("EIA_API_KEY")
    if not api_key:
        print("[!] Error: EIA_API_KEY is not set.")
        return None

    url = "https://api.eia.gov/v2/electricity/rto/daily-region-data/data/"
    current_year = datetime.now(timezone.utc).year
    
    params = {
        "api_key": api_key,
        "frequency": "daily",
        "data[0]": "value",
        "facets[respondent][]": "PJM",
        "facets[timezone][]": "Eastern",
        "facets[type][]": "D",
        "start": f"{current_year - 5}-01-01",
        "sort[0][column]": "period",
        "sort[0][direction]": "asc",
        "length": 5000
    }

    try:
        res = requests.get(url, params=params, timeout=20)
        res.raise_for_status()
        records = res.json().get("response", {}).get("data", [])
        
        historical_data = defaultdict(list)
        current_data_map = {}

        for row in records:
            period = row.get("period")
            val = row.get("value")
            if not period or val is None:
                continue
            try:
                date_obj = datetime.strptime(period, "%Y-%m-%d")
                mm_dd = date_obj.strftime("%m-%d")
                if date_obj.year == current_year:
                    current_data_map[mm_dd] = float(val)
                else:
                    historical_data[mm_dd].append(float(val))
            except ValueError:
                continue

        labels, hist_min, hist_max, hist_avg, curr_year_data = [], [], [], [], []
        for mm_dd in sorted(historical_data.keys()):
            labels.append(mm_dd)
            h_vals = historical_data[mm_dd]
            hist_min.append(min(h_vals))
            hist_max.append(max(h_vals))
            hist_avg.append(round(sum(h_vals) / len(h_vals), 2))
            curr_year_data.append(current_data_map.get(mm_dd, None))

        return {
            "labels": labels,
            "historical_min": hist_min,
            "historical_max": hist_max,
            "historical_avg": hist_avg,
            "current_year": curr_year_data
        }
    except Exception as e:
        print(f"[!] EIA API Error: {e}")
        return None

# ==========================================
# 4. メイン・オーケストレーター（データ統合）
# ==========================================
def main():
    print("=== CANARY RADAR DATA PIPELINE STARTED ===")
    
    # 監視対象銘柄群（WTI/コッパーの波及監視もここに統合済み）
    TIERS = {
        "TIER_0": {"UNG": "US Natural Gas Fund", "UNL": "US 12-Month NatGas", "EQT": "EQT Corp", "KMI": "Kinder Morgan"},
        "TIER_1": {"CEG": "Constellation Energy", "VRT": "Vertiv Holdings", "EQIX": "Equinix", "ETN": "Eaton Corp"},
        "TIER_1_5": {"SMCI": "Super Micro Computer", "ANET": "Arista Networks", "NVDA": "NVIDIA", "AMD": "AMD"},
        "TIER_2": {"AMZN": "Amazon (AWS)", "MSFT": "Microsoft (Azure)", "GOOGL": "Alphabet (GCP)", "META": "Meta"},
        "TIER_3": {"FCX": "Freeport-McMoRan (Copper)", "SCCO": "Southern Copper", "USO": "US Oil Fund (WTI)", "CCJ": "Cameco (Uranium)"},
        "TIER_4": {"NOW": "ServiceNow", "CRM": "Salesforce", "WDAY": "Workday", "SAP": "SAP"}
    }
    
    ROLES = {
        "UNG": "ガス期近・天候ノイズ", "UNL": "ガス遠月・構造需要", "EQT": "天然ガス生産最大手", "KMI": "ガスパイプライン網",
        "CEG": "原子力発電・電力", "VRT": "DC冷却・熱管理", "EQIX": "DC不動産(REIT)", "ETN": "配電・電力制御",
        "SMCI": "高密度AIサーバー", "ANET": "超高速ネットワーク", "NVDA": "AI半導体・独占", "AMD": "AI半導体・対抗",
        "AMZN": "ハイパースケーラー", "MSFT": "ハイパースケーラー", "GOOGL": "ハイパースケーラー", "META": "内製AIインフラ",
        "FCX": "銅（コッパー）生産", "SCCO": "銅（コッパー）生産", "USO": "WTI原油 ETF", "CCJ": "ウラン採掘・精製",
        "NOW": "ITワークフロー独占", "CRM": "顧客データ基盤", "WDAY": "人事・財務データ", "SAP": "基幹システム"
    }

    output_data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "🟢 【ローテーション】インフラ売却・データ資源買い",
        "config": {k: list(v.keys()) for k, v in TIERS.items()},
        "details": {},
        "layers": {}
    }

    # 4-1. 株式レイヤー（各Tier）の取得
    print("[*] Fetching Tiers Data...")
    all_tickers = [ticker for tier in TIERS.values() for ticker in tier.keys()]
    try:
        data = yf.download(all_tickers, period="5d", interval="1d", group_by="ticker", progress=False)
        for tier_name, tickers in TIERS.items():
            tier_changes = []
            for t in tickers.keys():
                try:
                    df = data[t] if len(all_tickers) > 1 else data
                    df = df.dropna()
                    if len(df) >= 2:
                        close_today = df['Close'].iloc[-1]
                        close_yday = df['Close'].iloc[-2]
                        vol_today = df['Volume'].iloc[-1]
                        vol_avg = df['Volume'].mean()
                        
                        change = ((close_today - close_yday) / close_yday) * 100
                        vol_surge = vol_today / vol_avg if vol_avg > 0 else 1.0
                        
                        output_data["details"][t] = {
                            "name": tickers[t],
                            "role": ROLES.get(t, ""),
                            "change": round(change, 2),
                            "vol_surge": round(vol_surge, 2)
                        }
                        tier_changes.append(change)
                except Exception as e:
                    print(f"  [!] Error processing {t}: {e}")
            output_data["layers"][tier_name] = round(sum(tier_changes)/len(tier_changes), 2) if tier_changes else 0.0
    except Exception as e:
        print(f"[!] yfinance Download Error: {e}")

    # 4-2. Tier -1 Bedrock (XLU / TLT Ratio) の取得
    print("[*] Fetching Tier -1 Bedrock Data (XLU / TLT)...")
    try:
        bedrock_data = yf.download(["XLU", "TLT"], period="6mo", interval="1d", progress=False)['Close'].dropna()
        ratio = bedrock_data['XLU'] / bedrock_data['TLT']
        sma_50 = ratio.rolling(window=50).mean()
        std_50 = ratio.rolling(window=50).std()
        upper_band = sma_50 + (2 * std_50)
        
        dates_str = [d.strftime('%Y-%m-%d') for d in ratio.index[-60:]]
        ratio_vals = ratio.values[-60:].tolist()
        sma_vals = sma_50.values[-60:].tolist()
        upper_vals = upper_band.values[-60:].tolist()
        
        current_r = ratio_vals[-1]
        prev_r = ratio_vals[-2]
        chg = ((current_r - prev_r) / prev_r) * 100

        output_data["bedrock"] = {
            "dates": dates_str,
            "ratio": [round(x, 3) if not pd.isna(x) else None for x in ratio_vals],
            "sma": [round(x, 3) if not pd.isna(x) else None for x in sma_vals],
            "upper": [round(x, 3) if not pd.isna(x) else None for x in upper_vals],
            "current_ratio": round(current_r, 3),
            "ratio_change": round(chg, 2)
        }
    except Exception as e:
        print(f"[!] Bedrock Data Error: {e}")

    # 4-3. 物理・金融レイヤーの取得とマージ
    output_data["financial_forward_curve"] = fetch_forward_curve()
    output_data["grid_physical_data"] = fetch_physical_grid_data()

# ==========================================
    # 4-3.5 【自動化】相関分析とステータス判定（スタックトレース）
    # ==========================================
    print("[*] Analyzing Macro Correlations...")
    
    tier1_chg = output_data["layers"].get("TIER_1", 0.0)
    tier2_chg = output_data["layers"].get("TIER_2", 0.0)
    tier4_chg = output_data["layers"].get("TIER_4", 0.0)
    bedrock_chg = output_data.get("bedrock", {}).get("ratio_change", 0.0)
    gas_signal = output_data.get("financial_forward_curve", {}).get("signal", "")

    # デフォルトステータス
    current_status = "⚪ 【待機】有意なマクロシグナルなし"

    # 判定ロジック（STRATEGY DOCSのドクトリンに準拠）
    if "バックワーデーション" in gas_signal and tier1_chg < -1.0:
        current_status = "🔴 【需要幻滅の死】遠月ガス急落 ＋ 物理基盤下落（即時ショート推奨）"
    elif bedrock_chg < -1.0 and tier1_chg < -1.0:
        current_status = "🔴 【PPA岩盤崩壊】信用プレミアム急落 ＋ 物理基盤下落"
    elif tier1_chg < -1.0 and tier2_chg < -1.0 and tier4_chg < -1.0:
        current_status = "🔴 【真のパニック崩壊】インフラ〜データ資源まで全面安（相関の崩壊）"
    elif tier1_chg < -1.0 and tier4_chg > 0.0:
        current_status = "🟢 【健全なローテーション】インフラ売却 ＋ データ資源(SaaS)買い"
    elif tier1_chg > 1.0 and tier4_chg > 1.0:
        current_status = "🟢 【バブル継続】全レイヤーへの過剰流動性流入"

    output_data["status"] = current_status

    # 4-4. JSONの書き出し
    print("[*] Writing dashboard_data.json...")
    with open('dashboard_data.json', 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=4)
        
    print("=== DATA PIPELINE COMPLETED SUCCESSFULLY ===")

if __name__ == "__main__":
    main()
