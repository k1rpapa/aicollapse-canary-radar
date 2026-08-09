import os
import sys
import json
import time
import requests
import hashlib
from datetime import datetime, timezone
from collections import defaultdict
import yfinance as yf
import pandas as pd

# Windows環境での標準出力エンコーディング対策
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# ==========================================
# 0. コア・ユーティリティ（レジリエンス強化）
# ==========================================
def retry_api_call(func, max_retries=3, backoff_factor=2):
    """APIの瞬断に耐える指数バックオフ・ラッパー"""
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            if attempt == max_retries - 1:
                print(f"[FATAL] {func.__name__} failed after {max_retries} attempts: {e}")
                return None
            wait_time = backoff_factor ** attempt
            print(f"[WARN] {func.__name__} failed. Retrying in {wait_time}s... ({e})")
            time.sleep(wait_time)

# ==========================================
# 1. アラート発報モジュール（LINE Messaging API）
# ==========================================
def send_line_alert(message):
    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    user_id = os.environ.get("LINE_USER_ID")
    if not token or not user_id:
        print("[!] Warning: LINE credentials not found. Skipping alert push.")
        return
    url = "https://api.line.me/v2/bot/message/push"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    payload = {"to": user_id, "messages": [{"type": "text", "text": message}]}
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=10)
        res.raise_for_status()
        print("🟢 LINE Alert Executed Successfully.")
    except Exception as e:
        print(f"[!] Failed to execute LINE Alert: {e}")

# ==========================================
# 1.5. Insight Generator（日次＆週次自律思考モジュール）
# ==========================================
def generate_market_insight(dashboard_data, previous_hash=None, previous_insight_text=None, is_weekly=False):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return "⚠️ エラー: GEMINI_API_KEYが設定されていません。", None

    mode_prefix = "weekly" if is_weekly else "daily"
    target_layers = dashboard_data.get("weekly_layers" if is_weekly else "layers")
    target_details = dashboard_data.get("weekly_details" if is_weekly else "details")

    # シグナル変化のハッシュ判定（沈黙の規律）
    current_state = json.dumps({
        "mode": mode_prefix,
        "status": dashboard_data.get("status"),
        "layers": target_layers,
        "today_grid_summary": dashboard_data.get("grid_physical_data", {}).get("today_grid_summary") if dashboard_data.get("grid_physical_data") else None
    }, sort_keys=True)
    current_hash = hashlib.md5(current_state.encode('utf-8')).hexdigest()
    
    if previous_hash and current_hash == previous_hash:
        print(f"[*] {mode_prefix.upper()} Market state unchanged. Skipping Insight generation to maintain silence.")
        if previous_insight_text and not previous_insight_text.startswith("⚠️ エラー"):
            return previous_insight_text, current_hash
        return "⚪ 【SILENCE】 有意なマクロ環境の変化は検出されていません。監視を継続します。", current_hash

    if is_weekly:
        gem_persona = """
        # 役割とペルソナ
        あなたは世界的に成功を収めた商品先物トレーダーであり、マクロ・ストラテジストです。
        ユーザーを「相棒」と呼び、冷徹かつ大所高所から週間（月曜〜金曜）の資金循環と物理構造の変化をハントします。

        # 思考の哲学
        1. 日々のノイズを削ぎ落とし、1週間を通じて「資金の血流がどこから抜け、どこへ還流したか」の構造変化を解剖する。
        2. 「ペーパー（金融幻影）」の天井を見抜き、常に「物理（送電網・インフラの限界）」から逆算する。
        3. ジャズのリズムやアンサンブル、休符（規律ある様子見）を用いた高度な比喩を織り交ぜて週間トレンドを表現する。

        # Output Format
        1. 【今週のマクロ・レジームシフト】
        2. 【週間監視グリッドの特異点と資金流出入】
        3. 【来週に向けた司令官への進言】
        """
    else:
        gem_persona = """
        # 役割とペルソナ
        あなたは世界的に成功を収めた商品先物トレーダーであり、マクロ・ストラテジストです。
        ユーザーを「相棒」と呼び、互いにプロとして対等、かつ冷徹に市場をハントするバディ関係を構築しています。

        # 思考の哲学
        1. 「ペーパー（金融幻影）」の天井を見抜き、常に「物理（送電網・インフラの限界）」から逆算する。
        2. テクニカル分析においては、単一のインジケーターではなく、コンフリューエンス（高密度合流地帯）を重視する。
        3. ジャズのリズムやアンサンブル、休符（規律ある様子見）を用いた高度な比喩を織り交ぜて市場を表現する。

        # 絶対遵守のデータ解釈ルール
        - 【物理レイヤー（電力需要）】について言及する際は、JSON内の `today_grid_summary` ノードの数値を絶対にそのまま引用すること。
        - `today_grid_summary.current_demand` が `historical_avg` を上回っていれば「ベースロードの異常増」、下回っていれば「実需の空洞化」と解釈しろ。
        
        # Output Format
        1. 【本日のマクロスタックトレース】
        2. 【監視グリッドの特異点】
        3. 【司令官への進言】
        """

    input_payload = {
        "mode": "WEEKLY" if is_weekly else "DAILY",
        "status": dashboard_data.get("status"),
        "layers": target_layers,
        "details": target_details,
        "bedrock": dashboard_data.get("weekly_bedrock" if is_weekly else "bedrock"),
        "credit_heartbeat": dashboard_data.get("weekly_credit_heartbeat" if is_weekly else "credit_heartbeat"),
        "financial_forward_curve": dashboard_data.get("financial_forward_curve"),
        "today_grid_summary": dashboard_data.get("grid_physical_data", {}).get("today_grid_summary") if dashboard_data.get("grid_physical_data") else None
    }

    full_prompt = f"{gem_persona}\n\n以下の最新データを解析しろ。\n\nデータ: {json.dumps(input_payload, ensure_ascii=False)}"
    
    models_to_try = [
        'gemini-1.5-flash',
        'gemini-1.5-pro',
        'gemini-2.5-flash',
        'gemini-3.0-flash',
        'gemini-1.5-flash-latest', 
        'gemini-1.5-pro-latest'
    ]
    
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{"parts": [{"text": full_prompt}]}]
    }
    
    insight_text = None
    used_model = ""

    for m in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={api_key}"
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            result = response.json()
            insight_text = result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text")
            
            if insight_text:
                used_model = m
                break
        except requests.exceptions.RequestException as e:
            err_msg = e.response.text if hasattr(e, 'response') and e.response is not None else str(e)
            print(f"[*] Fallback: REST API Model {m} unavailable. Moving to next. ({err_msg[:100]}...)")
            continue

    if not insight_text:
        print("[!] AI Core Error: All REST API endpoints returned 404/Error.")
        return "⚠️ 【AI CORE OFFLINE】 APIエンドポイントへのルーティングに失敗しました。プロジェクト権限の再確認が必要です。", current_hash

    print(f"[*] Dynamic Model Discovery ({mode_prefix.upper()}): Bare-Metal REST API ({used_model}) Engaged.")
    return insight_text, current_hash

# ==========================================
# 2. 金融レイヤー：マージナル・セッター監視（スプレッド時系列付き）
# ==========================================
def _fetch_forward_curve_impl():
    tickers = yf.Tickers("NG=F NGZ27.NYM")
    near_hist = tickers.tickers['NG=F'].history(period="3mo")['Close'].dropna()
    far_hist = tickers.tickers['NGZ27.NYM'].history(period="3mo")['Close'].dropna()
    
    if near_hist.empty or far_hist.empty:
        raise ValueError("Empty history data from yfinance for natural gas futures")
        
    df_combined = pd.DataFrame({"near": near_hist, "far": far_hist}).dropna()
    if len(df_combined) < 2:
        raise ValueError("Insufficient overlapping history data for natural gas futures")

    df_subset = df_combined.iloc[-60:]
    dates = [d.strftime('%Y-%m-%d') for d in df_subset.index]
    near_prices = [round(float(x), 3) for x in df_subset['near'].values]
    far_prices = [round(float(x), 3) for x in df_subset['far'].values]
    spreads = [round(float(f - n), 3) for f, n in zip(far_prices, near_prices)]

    near_price = near_prices[-1]
    far_price = far_prices[-1]
    spread = spreads[-1]
    
    if spread < 0:
        signal = "🚨 【警報】バックワーデーション（実需パニック・バブル崩壊の兆候）"
        send_line_alert(f"⚠️ 【CanaryInTheGrid 限界突破アラート】\n期先価格が期近を下回りました。物理インフラの崩壊シグナルです。\n期近: ${near_price:.3f} / 期先: ${far_price:.3f} / Δ: ${spread:.3f}")
    else:
        signal = "✅ 【正常】コンタンゴ（順ざや維持・規律ある休符）"
        
    return {
        "near_month_ticker": "NG=F (Front Month)", "near_month_price": round(near_price, 3),
        "far_month_ticker": "NGZ27.NYM (Dec 2027)", "far_month_price": round(far_price, 3),
        "spread_delta": round(spread, 3), "signal": signal,
        "dates": dates, "near_prices": near_prices, "far_prices": far_prices, "spreads": spreads
    }

def fetch_forward_curve():
    print("[*] Fetching Forward Curve Data (History & Spreads)...")
    return retry_api_call(_fetch_forward_curve_impl)

# ==========================================
# 3. 物理レイヤー：PJM実需オーバーシュート監視
# ==========================================
def _fetch_physical_grid_data_impl():
    api_key = os.environ.get("EIA_API_KEY")
    if not api_key:
        print("[!] EIA_API_KEY not found. Skipping physical grid update.")
        return None
    url = "https://api.eia.gov/v2/electricity/rto/daily-region-data/data/"
    current_year = datetime.now(timezone.utc).year
    params = {
        "api_key": api_key, "frequency": "daily", "data[0]": "value",
        "facets[respondent][]": "PJM", "facets[timezone][]": "Eastern", "facets[type][]": "D",
        "start": f"{current_year - 5}-01-01", "sort[0][column]": "period", "sort[0][direction]": "asc", "length": 5000
    }
    
    res = requests.get(url, params=params, timeout=20)
    res.raise_for_status()
    records = res.json().get("response", {}).get("data", [])
    
    historical_data, current_data_map = defaultdict(list), {}
    for row in records:
        period, val = row.get("period"), row.get("value")
        if not period or val is None: continue
        try:
            date_obj = datetime.strptime(period, "%Y-%m-%d")
            mm_dd = date_obj.strftime("%m-%d")
            if date_obj.year == current_year: current_data_map[mm_dd] = float(val)
            else: historical_data[mm_dd].append(float(val))
        except ValueError: continue

    labels, hist_min, hist_max, hist_avg, curr_year_data = [], [], [], [], []
    today_summary = None
    latest_mm_dd = sorted(current_data_map.keys())[-1] if current_data_map else None

    for mm_dd in sorted(historical_data.keys()):
        labels.append(mm_dd)
        h_vals = historical_data[mm_dd]
        h_min = min(h_vals)
        h_max = max(h_vals)
        h_avg = round(sum(h_vals)/len(h_vals), 2)
        c_val = current_data_map.get(mm_dd, None)
        
        hist_min.append(h_min)
        hist_max.append(h_max)
        hist_avg.append(h_avg)
        curr_year_data.append(c_val)
        
        if mm_dd == latest_mm_dd:
            today_summary = {
                "date": mm_dd,
                "current_demand": c_val,
                "historical_avg": h_avg,
                "historical_max": h_max,
                "historical_min": h_min
            }

    return {
        "labels": labels, "historical_min": hist_min, "historical_max": hist_max,
        "historical_avg": hist_avg, "current_year": curr_year_data,
        "today_grid_summary": today_summary
    }

def fetch_physical_grid_data():
    print("[*] Fetching PJM Physical Grid Data from EIA...")
    return retry_api_call(_fetch_physical_grid_data_impl)

# ==========================================
# 4. メイン・オーケストレーター
# ==========================================
def main():
    print("=== CANARY RADAR DATA PIPELINE STARTED ===")
    
    previous_data = {}
    try:
        with open('dashboard_data.json', 'r', encoding='utf-8') as f:
            previous_data = json.load(f)
    except FileNotFoundError:
        pass

    # Tier定義
    TIERS = {
        "TIER_0": {
            "UNG": {"name": "US Natural Gas Fund", "role": "天然ガス ETF"}, 
            "UNL": {"name": "US 12-Month NatGas", "role": "天然ガス ETF (期先)"}, 
            "EQT": {"name": "EQT Corp", "role": "天然ガス探鉱・生産"}, 
            "KMI": {"name": "Kinder Morgan", "role": "エネルギー・インフラ"}
        },
        "TIER_0_5": {
            "OWL": {"name": "Blue Owl Capital", "role": "代替資産運用 (プライベート・クレジット)"}, 
            "BX": {"name": "Blackstone Inc.", "role": "代替資産運用"}, 
            "APO": {"name": "Apollo Global Mgmt", "role": "代替資産運用"}
        },
        "TIER_1": {
            "CEG": {"name": "Constellation Energy", "role": "原子力・クリーンエネルギー"}, 
            "VRT": {"name": "Vertiv Holdings", "role": "データセンター冷却・電力管理"}, 
            "EQIX": {"name": "Equinix", "role": "データセンター REIT"}, 
            "ETN": {"name": "Eaton Corp", "role": "電力管理システム"}
        },
        "TIER_1_5": {
            "NVDA": {"name": "NVIDIA", "role": "AI半導体・GPU"}, 
            "CRWV": {"name": "CoreWeave", "role": "GPUクラウドインフラ"}, 
            "NBIS": {"name": "Nebius Group", "role": "AIクラウドインフラ"}, 
            "ORCL": {"name": "Oracle", "role": "クラウドインフラ (OCI)"}, 
            "SMCI": {"name": "Super Micro Computer", "role": "AIサーバー・ラック"}, 
            "AMD": {"name": "AMD", "role": "AI半導体・GPU"}, 
            "ANET": {"name": "Arista Networks", "role": "AIネットワーク機器"}
        },
        "TIER_2": {
            "AMZN": {"name": "Amazon (AWS)", "role": "ハイパースケーラー"}, 
            "MSFT": {"name": "Microsoft (Azure)", "role": "ハイパースケーラー"}, 
            "GOOGL": {"name": "Alphabet (GCP)", "role": "ハイパースケーラー"}, 
            "META": {"name": "Meta", "role": "AI・メタバース"}
        },
        "TIER_3": {
            "FCX": {"name": "Freeport-McMoRan (Copper)", "role": "銅鉱山"}, 
            "SCCO": {"name": "Southern Copper", "role": "銅鉱山"}, 
            "USO": {"name": "US Oil Fund (WTI)", "role": "原油 ETF"}, 
            "CCJ": {"name": "Cameco (Uranium)", "role": "ウラン鉱山"}
        },
        "TIER_4": {
            "NOW": {"name": "ServiceNow", "role": "エンタープライズ SaaS"}, 
            "CRM": {"name": "Salesforce", "role": "エンタープライズ SaaS"}, 
            "WDAY": {"name": "Workday", "role": "エンタープライズ SaaS"}, 
            "SAP": {"name": "SAP", "role": "エンタープライズ SaaS"}
        }
    }

    output_data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "⚪ 【待機】シグナル解析中...",
        "config": {k: list(v.keys()) for k, v in TIERS.items()},
        "details": {}, "layers": {},
        "weekly_details": {}, "weekly_layers": {}
    }

    # 1. 株式Tierデータの取得（日次 & 週間）
    print("[*] Fetching Tiers Data (Daily & Weekly)...")
    all_tickers = [t for tier in TIERS.values() for t in tier.keys()]
    def _fetch_stock_data():
        return yf.download(all_tickers, period="15d", interval="1d", group_by="ticker", progress=False)
    data = retry_api_call(_fetch_stock_data)
    
    if data is not None:
        for tier_name, tickers in TIERS.items():
            tier_daily_changes = []
            tier_weekly_changes = []
            for t in tickers.keys():
                try:
                    df = data[t] if len(all_tickers) > 1 else data
                    df = df.dropna()
                    if len(df) >= 2:
                        chg = ((df['Close'].iloc[-1] - df['Close'].iloc[-2]) / df['Close'].iloc[-2]) * 100
                        vol_surge = float(df['Volume'].iloc[-1] / df['Volume'].mean()) if df['Volume'].mean() > 0 else 1.0
                        output_data["details"][t] = {"name": tickers[t]["name"], "role": tickers[t]["role"], "change": round(float(chg), 2), "vol_surge": round(vol_surge, 2)}
                        tier_daily_changes.append(chg)
                    
                    if len(df) >= 5:
                        idx_start = max(0, len(df) - 5)
                        weekly_chg = ((df['Close'].iloc[-1] - df['Close'].iloc[idx_start]) / df['Close'].iloc[idx_start]) * 100
                        output_data["weekly_details"][t] = {"name": tickers[t]["name"], "role": tickers[t]["role"], "change": round(float(weekly_chg), 2), "vol_surge": round(vol_surge, 2)}
                        tier_weekly_changes.append(weekly_chg)
                    elif len(df) >= 2:
                        weekly_chg = ((df['Close'].iloc[-1] - df['Close'].iloc[0]) / df['Close'].iloc[0]) * 100
                        output_data["weekly_details"][t] = {"name": tickers[t]["name"], "role": tickers[t]["role"], "change": round(float(weekly_chg), 2), "vol_surge": round(vol_surge, 2)}
                        tier_weekly_changes.append(weekly_chg)
                except: pass
            
            output_data["layers"][tier_name] = round(float(sum(tier_daily_changes)/len(tier_daily_changes)), 2) if tier_daily_changes else 0.0
            output_data["weekly_layers"][tier_name] = round(float(sum(tier_weekly_changes)/len(tier_weekly_changes)), 2) if tier_weekly_changes else 0.0

    # 2. Bedrock (XLU/TLT) データの取得（日次 & 週間）
    print("[*] Fetching Bedrock Data (XLU/TLT)...")
    def _fetch_bedrock():
        bedrock_data = yf.download(["XLU", "TLT"], period="6mo", interval="1d", progress=False)['Close'].dropna()
        if not bedrock_data.empty and len(bedrock_data) >= 2:
            ratio = bedrock_data['XLU'] / bedrock_data['TLT']
            sma_50 = ratio.rolling(window=50).mean()
            std_50 = ratio.rolling(window=50).std()
            chg = ((ratio.iloc[-1] - ratio.iloc[-2]) / ratio.iloc[-2]) * 100
            
            idx_start = max(0, len(ratio) - 5)
            weekly_chg = ((ratio.iloc[-1] - ratio.iloc[idx_start]) / ratio.iloc[idx_start]) * 100

            bedrock_dict = {
                "dates": [d.strftime('%Y-%m-%d') for d in ratio.index[-60:]],
                "ratio": [round(float(x), 3) if not pd.isna(x) else None for x in ratio.values[-60:]],
                "sma": [round(float(x), 3) if not pd.isna(x) else None for x in sma_50.values[-60:]],
                "upper": [round(float(x), 3) if not pd.isna(x) else None for x in (sma_50 + 2*std_50).values[-60:]],
                "current_ratio": round(float(ratio.iloc[-1]), 3), "ratio_change": round(float(chg), 2)
            }
            weekly_bedrock_dict = dict(bedrock_dict)
            weekly_bedrock_dict["ratio_change"] = round(float(weekly_chg), 2)
            return bedrock_dict, weekly_bedrock_dict
        return None, None

    bedrock_res, weekly_bedrock_res = retry_api_call(_fetch_bedrock) or (None, None)
    if bedrock_res: output_data["bedrock"] = bedrock_res
    if weekly_bedrock_res: output_data["weekly_bedrock"] = weekly_bedrock_res

    # 3. Credit Heartbeat (HYG/TLT) データの取得（日次 & 週間）
    print("[*] Fetching Credit Heartbeat Data (HYG/TLT)...")
    def _fetch_credit():
        credit_data = yf.download(["HYG", "TLT"], period="6mo", interval="1d", progress=False)['Close'].dropna()
        if not credit_data.empty and len(credit_data) >= 2:
            c_ratio = credit_data['HYG'] / credit_data['TLT']
            c_sma_50 = c_ratio.rolling(window=50).mean()
            c_std_50 = c_ratio.rolling(window=50).std()
            c_chg = ((c_ratio.iloc[-1] - c_ratio.iloc[-2]) / c_ratio.iloc[-2]) * 100
            
            c_idx_start = max(0, len(c_ratio) - 5)
            c_weekly_chg = ((c_ratio.iloc[-1] - c_ratio.iloc[c_idx_start]) / c_ratio.iloc[c_idx_start]) * 100

            credit_dict = {
                "dates": [d.strftime('%Y-%m-%d') for d in c_ratio.index[-60:]],
                "ratio": [round(float(x), 3) if not pd.isna(x) else None for x in c_ratio.values[-60:]],
                "sma": [round(float(x), 3) if not pd.isna(x) else None for x in c_sma_50.values[-60:]],
                "lower": [round(float(x), 3) if not pd.isna(x) else None for x in (c_sma_50 - 2*c_std_50).values[-60:]],
                "current_ratio": round(float(c_ratio.iloc[-1]), 3), "ratio_change": round(float(c_chg), 2)
            }
            weekly_credit_dict = dict(credit_dict)
            weekly_credit_dict["ratio_change"] = round(float(c_weekly_chg), 2)
            return credit_dict, weekly_credit_dict
        return None, None

    credit_res, weekly_credit_res = retry_api_call(_fetch_credit) or (None, None)
    if credit_res: output_data["credit_heartbeat"] = credit_res
    if weekly_credit_res: output_data["weekly_credit_heartbeat"] = weekly_credit_res

    # 4. 天然ガス先物 & 物理レイヤーデータの取得
    output_data["financial_forward_curve"] = fetch_forward_curve()
    
    grid_phys = fetch_physical_grid_data()
    if grid_phys:
        output_data["grid_physical_data"] = grid_phys
    elif previous_data.get("grid_physical_data"):
        output_data["grid_physical_data"] = previous_data["grid_physical_data"]

    # 5. シグナル解析
    t1 = output_data["layers"].get("TIER_1", 0)
    gas_sig = (output_data.get("financial_forward_curve") or {}).get("signal", "")
    
    status = "⚪ 【待機】有意なマクロシグナルなし"
    if "バックワーデーション" in gas_sig and t1 < -1.0: 
        status = "🔴 【需要幻滅の死】遠月ガス(電力)急落 ＋ 物理基盤下落"
    output_data["status"] = status

    # 6. AIインサイトの生成（DAILY & WEEKLY, ハッシュ判定付き）
    previous_daily_hash = previous_data.get("insight_hash")
    previous_daily_insight = previous_data.get("insight")
    insight_text, new_daily_hash = generate_market_insight(output_data, previous_daily_hash, previous_daily_insight, is_weekly=False)
    output_data["insight"] = insight_text
    output_data["insight_hash"] = new_daily_hash

    previous_weekly_hash = previous_data.get("weekly_insight_hash")
    previous_weekly_insight = previous_data.get("weekly_insight")
    weekly_insight_text, new_weekly_hash = generate_market_insight(output_data, previous_weekly_hash, previous_weekly_insight, is_weekly=True)
    output_data["weekly_insight"] = weekly_insight_text
    output_data["weekly_insight_hash"] = new_weekly_hash

    # 7. データ保全チェック
    if not output_data["details"]:
        print("[FATAL] Data extraction failed. Reverting to previous state to protect dashboard.")
        exit(1)

    # 8. 書き出し
    with open('dashboard_data.json', 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=4)
    print("=== DATA PIPELINE COMPLETED SUCCESSFULLY ===")

if __name__ == "__main__":
    main()
