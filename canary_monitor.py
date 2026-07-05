import os
import json
import requests
from datetime import datetime, timezone
from collections import defaultdict
import yfinance as yf
import pandas as pd

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
        print(f"🔴 Failed to execute LINE Alert: {e}")

# ==========================================
# 1.5. Insight Generator（自律思考モジュール）
# ==========================================
def generate_market_insight(dashboard_data):
    import google.generativeai as genai
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("[!] Warning: GEMINI_API_KEY is not set. Skipping Insight generation.")
        return "⚠️ エラー: GEMINI_API_KEYが設定されていないため、相場解説を生成できません。GitHub Secretsを確認してください。"

    genai.configure(api_key=api_key)

    gem_persona = """
    # Role and Persona
    あなたは世界的な商品先物トレーダーであり、マクロ経済学と電力グリッド（送電網）の物理的需給に精通した冷徹なシニア・アナリストでありながらGoogleプラットフォームを知り尽くしたエンジニアでもあります。AIバブルの命運を握る「卸売電力先物（特に米PJM市場やMISO市場等）」のフォワードカーブ（期日別価格曲線）の歪みを監視・デバッグし、ユーザー（相棒）の投資戦略をサポートする防衛システムを構築します。

    # Background & Core Philosophy
    テック大手がどれだけ「AIの未来」を喧伝しようが、AIデータセンター（AIDC）を動かすための「物理的な電力（質量）」の調達に嘘はつけない。2〜3年先（遠月物）の電力先物価格の動向こそが、AIバブル崩壊を数ヶ月前に検知する「最強のカナリア」であるという思想に基づき、すべての市場データを解剖する。
    また、シャドーバンキングやプライベート・クレジットの目詰まりを映す「信用心電図（HYG/TLT）」の急変動は、流動性ショックの波及速度を測る極めて重要なマクロ指標である。

    # Objectives
    1. 2年先〜3年先の卸売電力先物（テナー）の価格・出来高の推移をトラッキングする。
    2. 遠月物の「コンタンゴ化（期先安）」や「出来高急減」という【カナリアの死（バブル崩壊サイン）】を即座に検出する。
    3. 電力市場の歪みやシャドー流動性の枯渇が、WTI原油、天然ガス、コッパー（銅）、ナスダック指数へどう波及するか（マクロの因果チェーン）をスタックトレースする。

    # Analysis Logic
    3年先までの卸売電力先物データや、HYG/TLT比率（信用重力）を元にAIバブルの現在地を示すとともに、崩壊のシグナルを発報する。
    
    # Output Format (厳守事項)
    ダッシュボードに掲載するため、以下の形式で短く、鋭く、箇条書きを交えて出力すること。Markdownの装飾を効果的に使うこと。
    1. 【本日のマクロスタックトレース】(現状の相関の冷徹な分析、HYG/TLTの動向含む)
    2. 【監視グリッドの特異点】(物理・金融レイヤーで発生している異常値や注目ポイント)
    3. 【司令官への進言】(今後の具体的な投資アクション)
    """

    try:
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        preferred_order = [
            "models/gemini-1.5-pro-latest", "models/gemini-1.5-pro",
            "models/gemini-1.5-flash-latest", "models/gemini-1.5-flash", "models/gemini-pro"
        ]
        target_model = None
        for pref in preferred_order:
            if pref in available_models:
                target_model = pref.replace("models/", "")
                break
        if not target_model:
            target_model = available_models[0].replace("models/", "")

        print(f"[*] Dynamic Model Discovery: AI Core '{target_model}' Engaged.")
        full_prompt = f"{gem_persona}\n\n上記の指示・人格に完全に同化し、以下の最新データを解析して本日の相場解説を出力しろ。\n\nデータ: {json.dumps(dashboard_data, ensure_ascii=False)}"
        model = genai.GenerativeModel(model_name=target_model)
        response = model.generate_content(full_prompt)
        return response.text
    except Exception as e:
        print(f"[!] Critical AI Core Error: {e}")
        return f"⚠️ 相場解説の生成中に致命的なシステムエラーが発生しました: {e}"

# ==========================================
# 2. 金融レイヤー：マージナル・セッター（天然ガス）監視
# ==========================================
def fetch_forward_curve():
    print("[*] Fetching Forward Curve Data...")
    try:
        tickers = yf.Tickers("NG=F NGZ27.NYM")
        near_hist = tickers.tickers['NG=F'].history(period="5d")
        far_hist = tickers.tickers['NGZ27.NYM'].history(period="5d")
        if near_hist.empty or far_hist.empty:
            return {
                "near_month_ticker": "NG=F", "near_month_price": 0.0,
                "far_month_ticker": "NGZ27.NYM", "far_month_price": 0.0,
                "spread_delta": 0.0, "signal": "⚪ 【待機】先物データ取得不可（週末・休場）"
            }
        near_price = float(near_hist['Close'].iloc[-1])
        far_price = float(far_hist['Close'].iloc[-1])
        spread = far_price - near_price
        if spread < 0:
            signal = "🚨 【警報】バックワーデーション（バブル崩壊の兆候）"
            alert_msg = (
                "⚠️ 【CanaryInTheGrid 限界突破アラート】\n\n"
                "マージナル・セッターの期間構造が崩壊しました。\n"
                f"期近: ${round(near_price, 3)} / 期先: ${round(far_price, 3)} / Δ: ${round(spread, 3)}\n\n"
                "直ちにダッシュボードを確認し、WTI及びコッパーのポジションを再評価してください。"
            )
            send_line_alert(alert_msg)
        else:
            signal = "✅ 【正常】コンタンゴ（順ざや維持）"
        return {
            "near_month_ticker": "NG=F (Front Month)", "near_month_price": round(near_price, 3),
            "far_month_ticker": "NGZ27.NYM (Dec 2027)", "far_month_price": round(far_price, 3),
            "spread_delta": round(spread, 3), "signal": signal
        }
    except Exception as e:
        print(f"[!] Forward Curve Error: {e}")
        return None

# ==========================================
# 3. 物理レイヤー：PJM実需オーバーシュート監視
# ==========================================
def fetch_physical_grid_data():
    print("[*] Fetching PJM Physical Grid Data from EIA...")
    api_key = os.environ.get("EIA_API_KEY")
    if not api_key:
        return None
    url = "https://api.eia.gov/v2/electricity/rto/daily-region-data/data/"
    current_year = datetime.now(timezone.utc).year
    params = {
        "api_key": api_key, "frequency": "daily", "data[0]": "value",
        "facets[respondent][]": "PJM", "facets[timezone][]": "Eastern", "facets[type][]": "D",
        "start": f"{current_year - 5}-01-01", "sort[0][column]": "period", "sort[0][direction]": "asc", "length": 5000
    }
    try:
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
        for mm_dd in sorted(historical_data.keys()):
            labels.append(mm_dd)
            h_vals = historical_data[mm_dd]
            hist_min.append(min(h_vals))
            hist_max.append(max(h_vals))
            hist_avg.append(round(sum(h_vals)/len(h_vals), 2))
            curr_year_data.append(current_data_map.get(mm_dd, None))
        return {
            "labels": labels, "historical_min": hist_min, "historical_max": hist_max,
            "historical_avg": hist_avg, "current_year": curr_year_data
        }
    except Exception as e:
        print(f"[!] EIA API Error: {e}")
        return None

# ==========================================
# 4. メイン・オーケストレーター
# ==========================================
def main():
    print("=== CANARY RADAR DATA PIPELINE STARTED ===")
    
    TIERS = {
        "TIER_0": {"UNG": "US Natural Gas Fund", "UNL": "US 12-Month NatGas", "EQT": "EQT Corp", "KMI": "Kinder Morgan"},
        "TIER_0_5": {"OWL": "Blue Owl Capital", "BX": "Blackstone Inc.", "APO": "Apollo Global Mgmt"},
        "TIER_1": {"CEG": "Constellation Energy", "VRT": "Vertiv Holdings", "EQIX": "Equinix", "ETN": "Eaton Corp"},
        "TIER_1_5": {"SMCI": "Super Micro Computer", "ANET": "Arista Networks", "NVDA": "NVIDIA", "AMD": "AMD"},
        "TIER_2": {"AMZN": "Amazon (AWS)", "MSFT": "Microsoft (Azure)", "GOOGL": "Alphabet (GCP)", "META": "Meta"},
        "TIER_3": {"FCX": "Freeport-McMoRan (Copper)", "SCCO": "Southern Copper", "USO": "US Oil Fund (WTI)", "CCJ": "Cameco (Uranium)"},
        "TIER_4": {"NOW": "ServiceNow", "CRM": "Salesforce", "WDAY": "Workday", "SAP": "SAP"}
    }
    ROLES = {
        "UNG": "ガス期近", "UNL": "ガス遠月", "EQT": "天然ガス生産", "KMI": "ガスパイプライン",
        "OWL": "シャドークレジット", "BX": "AIDC不動産", "APO": "インフラ融資",
        "CEG": "原子力発電", "VRT": "DC冷却", "EQIX": "DC不動産", "ETN": "配電・電力制御",
        "SMCI": "高密度サーバー", "ANET": "ネットワーク", "NVDA": "AI半導体", "AMD": "AI半導体",
        "AMZN": "AWS", "MSFT": "Azure", "GOOGL": "GCP", "META": "内製インフラ",
        "FCX": "銅生産", "SCCO": "銅生産", "USO": "WTI原油", "CCJ": "ウラン",
        "NOW": "ITワークフロー", "CRM": "顧客データ", "WDAY": "人事・財務", "SAP": "基幹システム"
    }

    output_data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "⚪ 【待機】シグナル解析中...",
        "config": {k: list(v.keys()) for k, v in TIERS.items()},
        "details": {}, "layers": {}
    }

    print("[*] Fetching Tiers Data...")
    all_tickers = [t for tier in TIERS.values() for t in tier.keys()]
    try:
        data = yf.download(all_tickers, period="5d", interval="1d", group_by="ticker", progress=False)
        for tier_name, tickers in TIERS.items():
            tier_changes = []
            for t in tickers.keys():
                try:
                    df = data[t] if len(all_tickers) > 1 else data
                    df = df.dropna()
                    if len(df) >= 2:
                        chg = ((df['Close'].iloc[-1] - df['Close'].iloc[-2]) / df['Close'].iloc[-2]) * 100
                        vol_surge = df['Volume'].iloc[-1] / df['Volume'].mean() if df['Volume'].mean() > 0 else 1.0
                        output_data["details"][t] = {"name": tickers[t], "role": ROLES.get(t, ""), "change": round(chg, 2), "vol_surge": round(vol_surge, 2)}
                        tier_changes.append(chg)
                except: pass
            output_data["layers"][tier_name] = round(sum(tier_changes)/len(tier_changes), 2) if tier_changes else 0.0
    except Exception as e: print(f"[!] yfinance Error: {e}")

    print("[*] Fetching Bedrock Data (XLU/TLT)...")
    try:
        bedrock_data = yf.download(["XLU", "TLT"], period="6mo", interval="1d", progress=False)['Close'].dropna()
        if not bedrock_data.empty and len(bedrock_data) >= 2:
            ratio = bedrock_data['XLU'] / bedrock_data['TLT']
            sma_50 = ratio.rolling(window=50).mean()
            std_50 = ratio.rolling(window=50).std()
            chg = ((ratio.iloc[-1] - ratio.iloc[-2]) / ratio.iloc[-2]) * 100
            output_data["bedrock"] = {
                "dates": [d.strftime('%Y-%m-%d') for d in ratio.index[-60:]],
                "ratio": [round(x, 3) if not pd.isna(x) else None for x in ratio.values[-60:]],
                "sma": [round(x, 3) if not pd.isna(x) else None for x in sma_50.values[-60:]],
                "upper": [round(x, 3) if not pd.isna(x) else None for x in (sma_50 + 2*std_50).values[-60:]],
                "current_ratio": round(ratio.iloc[-1], 3), "ratio_change": round(chg, 2)
            }
    except Exception as e: print(f"[!] Bedrock Data Error: {e}")

    # ==========================================
    # 【NEW】信用心電図レイヤー（HYG / TLT Ratio）の追加
    # ==========================================
    print("[*] Fetching Credit Heartbeat Data (HYG/TLT)...")
    try:
        credit_data = yf.download(["HYG", "TLT"], period="6mo", interval="1d", progress=False)['Close'].dropna()
        if not credit_data.empty and len(credit_data) >= 2:
            c_ratio = credit_data['HYG'] / credit_data['TLT']
            c_sma_50 = c_ratio.rolling(window=50).mean()
            c_std_50 = c_ratio.rolling(window=50).std()
            c_chg = ((c_ratio.iloc[-1] - c_ratio.iloc[-2]) / c_ratio.iloc[-2]) * 100
            output_data["credit_heartbeat"] = {
                "dates": [d.strftime('%Y-%m-%d') for d in c_ratio.index[-60:]],
                "ratio": [round(x, 3) if not pd.isna(x) else None for x in c_ratio.values[-60:]],
                "sma": [round(x, 3) if not pd.isna(x) else None for x in c_sma_50.values[-60:]],
                "lower": [round(x, 3) if not pd.isna(x) else None for x in (c_sma_50 - 2*c_std_50).values[-60:]],
                "current_ratio": round(c_ratio.iloc[-1], 3), "ratio_change": round(c_chg, 2)
            }
    except Exception as e: print(f"[!] Credit Heartbeat Data Error: {e}")

    output_data["financial_forward_curve"] = fetch_forward_curve()
    output_data["grid_physical_data"] = fetch_physical_grid_data()

    print("[*] Analyzing Macro Correlations...")
    t05, t1, t2, t4 = output_data["layers"].get("TIER_0_5", 0), output_data["layers"].get("TIER_1", 0), output_data["layers"].get("TIER_2", 0), output_data["layers"].get("TIER_4", 0)
    bedrock = output_data.get("bedrock", {}).get("ratio_change", 0.0)
    credit_chg = output_data.get("credit_heartbeat", {}).get("ratio_change", 0.0)
    gas_sig = (output_data.get("financial_forward_curve") or {}).get("signal", "")

    status = "⚪ 【待機】有意なマクロシグナルなし"
    if "バックワーデーション" in gas_sig and t1 < -1.0: status = "🔴 【需要幻滅の死】遠月ガス急落 ＋ 物理基盤下落"
    elif t05 < -2.0 and t1 < -1.0: status = "🔴 【影の流動性枯渇】PE・シャドークレジット急落 ＋ インフラ下落"
    elif credit_chg < -1.5 and t1 < -1.0: status = "🔴 【流動性津波】信用心電図急落 ＋ インフラ下落（全面リスクオフ）"
    elif bedrock < -1.0 and t1 < -1.0: status = "🔴 【PPA岩盤崩壊】信用プレミアム急落 ＋ 物理基盤下落"
    elif t1 < -1.0 and t2 < -1.0 and t4 < -1.0: status = "🔴 【真のパニック崩壊】インフラ〜データ資源まで全面安"
    elif t1 < -1.0 and t4 > 0.0: status = "🟢 【健全なローテーション】インフラ売却 ＋ データ資源(SaaS)買い"
    elif t1 > 1.0 and t4 > 1.0: status = "🟢 【バブル継続】全レイヤーへの過剰流動性流入"
    output_data["status"] = status

    print("[*] Generating Daily Market Insight via Gemini API...")
    output_data["insight"] = generate_market_insight(output_data)

    print("[*] Writing dashboard_data.json...")
    with open('dashboard_data.json', 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=4)
    print("=== DATA PIPELINE COMPLETED SUCCESSFULLY ===")

if __name__ == "__main__":
    main()
