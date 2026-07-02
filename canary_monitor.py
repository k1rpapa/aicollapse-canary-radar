import os
import json
import requests
from datetime import datetime
from collections import defaultdict
import yfinance as yf

INFRA_TIERS = {
    'TIER_0': ['UNG', 'UNL', 'EQT', 'KMI'],
    'TIER_1': ['CEG', 'VRT', 'ETN', 'EQIX'],        
    'TIER_1_5': ['SMCI', 'ANET'],                   
    'TIER_2': ['CRWV', 'NBIS'],                     
    'TIER_3': ['FCX', 'SCCO', 'CCJ', 'URA'],        
    'TIER_4': ['NOW', 'WDAY', 'CRM', 'SAP', 'VEEV', 'HUBS', 'SNOW', 'TDC', 'ZS', 'MDB', 'PAYC', 'INTU', 'ADBE']
}

TICKER_INFO = {
    'UNG': {'name': 'US Natural Gas Fund', 'role': 'ガス期近・天候ノイズ'},
    'UNL': {'name': 'US 12-Month NatGas', 'role': 'ガス遠月・構造需要'},
    'EQT': {'name': 'EQT Corp', 'role': '天然ガス生産最大手'},
    'KMI': {'name': 'Kinder Morgan', 'role': 'ガスパイプライン網'},
    'CEG': {'name': 'Constellation Energy', 'role': '原子力発電・電力'},
    'VRT': {'name': 'Vertiv Holdings', 'role': 'DC冷却・熱管理'},
    'ETN': {'name': 'Eaton Corp', 'role': '配電・電力制御'},
    'EQIX': {'name': 'Equinix', 'role': 'DC不動産・コロケーション'},
    'SMCI': {'name': 'Super Micro Computer', 'role': '高密度AIサーバー'},
    'ANET': {'name': 'Arista Networks', 'role': '超高速ネットワーク'},
    'CRWV': {'name': 'CoreWeave Index', 'role': 'AI特化型クラウド'},
    'NBIS': {'name': 'Nebius Group', 'role': 'AIクラウドインフラ'},
    'FCX': {'name': 'Freeport-McMoRan', 'role': '銅（コッパー）生産'},
    'SCCO': {'name': 'Southern Copper', 'role': '銅（コッパー）生産'},
    'CCJ': {'name': 'Cameco Corp', 'role': 'ウラン採掘・精製'},
    'URA': {'name': 'Global X Uranium ETF', 'role': 'ウラン・原子力ETF'},
    'NOW': {'name': 'ServiceNow', 'role': 'IT・業務ワークフロー'},
    'WDAY': {'name': 'Workday', 'role': '人事・財務データ'},
    'CRM': {'name': 'Salesforce', 'role': '顧客・営業データ'},
    'SAP': {'name': 'SAP SE', 'role': '基幹業務・ERPデータ'},
    'VEEV': {'name': 'Veeva Systems', 'role': '製薬・治験・規制データ'},
    'HUBS': {'name': 'HubSpot', 'role': '中堅フロントオフィス'},
    'SNOW': {'name': 'Snowflake', 'role': 'クラウド・データレイク'},
    'TDC': {'name': 'Teradata', 'role': '重量級データ分析'},
    'ZS': {'name': 'Zscaler', 'role': 'クラウド・セキュリティ'},
    'MDB': {'name': 'MongoDB', 'role': '非構造化・モダンDB'},
    'PAYC': {'name': 'Paycom Software', 'role': '人事・給与ワークフロー'},
    'INTU': {'name': 'Intuit', 'role': '中小財務・税務データ'},
    'ADBE': {'name': 'Adobe', 'role': 'クリエイティブ・PDF規格'}
}

# --- 新規追加: Tier -1 (岩盤) の時系列データ取得 ---
def fetch_bedrock_data():
    print("[*] Fetching Tier -1 Bedrock Data (XLU / TLT)...")
    try:
        xlu_data = yf.download('XLU', period="1y")['Close']
        tlt_data = yf.download('TLT', period="1y")['Close']
        
        # 1次元シリーズとして取得するため squeeze() を使用
        if isinstance(xlu_data, pd.DataFrame): xlu_data = xlu_data.squeeze()
        if isinstance(tlt_data, pd.DataFrame): tlt_data = tlt_data.squeeze()

        df = pd.DataFrame({'XLU': xlu_data, 'TLT': tlt_data}).dropna()
        df['Ratio'] = df['XLU'] / df['TLT']
        df['SMA'] = df['Ratio'].rolling(window=50).mean()
        df['STD'] = df['Ratio'].rolling(window=50).std()
        df['Upper'] = df['SMA'] + (df['STD'] * 2)
        df = df.dropna()

        # JSONでフロントに渡すためリスト化
        return {
            "dates": df.index.strftime('%Y-%m-%d').tolist(),
            "ratio": df['Ratio'].round(3).tolist(),
            "sma": df['SMA'].round(3).tolist(),
            "upper": df['Upper'].round(3).tolist(),
            "current_ratio": round(float(df['Ratio'].iloc[-1]), 3),
            "ratio_change": round(float(((df['Ratio'].iloc[-1] / df['Ratio'].iloc[-2]) - 1) * 100), 2)
        }
    except Exception as e:
        print(f"[!] Error fetching Bedrock data: {e}")
        return None

def fetch_market_data():
    # ... (既存の fetch_market_data ロジックをそのまま維持) ...
    all_tickers = []
    for tickers in INFRA_TIERS.values():
        all_tickers.extend(tickers)
        
    try:
        data = yf.download(all_tickers, period="5d", group_by="ticker", auto_adjust=False)
    except:
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
                vol_surge = (volumes[-1] / (sum(volumes[:-1])/len(volumes[:-1]))) if len(volumes)>1 and sum(volumes[:-1])>0 else 1.0
                results[ticker] = {
                    "price": round(float(latest), 2), "change": round(float(change_pct), 2), "vol_surge": round(float(vol_surge), 2),
                    "name": TICKER_INFO.get(ticker, {}).get('name', ticker), "role": TICKER_INFO.get(ticker, {}).get('role', '')
                }
            else:
                results[ticker] = {"price": 0.0, "change": 0.0, "vol_surge": 1.0, "name": ticker, "role": ""}
        except:
            pass
    return results

def calculate_tier_averages(data_details):
    tier_averages = {}
    for tier_name, tickers in INFRA_TIERS.items():
        changes = [data_details[t]["change"] for t in tickers if t in data_details]
        tier_averages[tier_name] = round(sum(changes) / len(changes), 2) if changes else 0
    return tier_averages

def run_diagnostic(tier_averages, bedrock_data):
    t1 = tier_averages.get('TIER_1', 0)
    t4 = tier_averages.get('TIER_4', 0)
    
    # 岩盤崩壊アラートを最上位に追加
    if bedrock_data and bedrock_data['ratio_change'] < -1.5 and t1 < -1.0:
        return "🔴 【PPA岩盤崩壊】XLU/TLT比率が急落。Big Techの電力契約に対する信用収縮が発生！"
    
    if t1 < -1.0 and t4 > 0.5: return "🟢 【ローテーション】インフラ売却・データ資源買い"
    elif t1 < -1.0 and t4 < -1.0: return "🔴 【真のパニック崩壊】インフラからSaaSまで全面資金流出"
    elif t1 >= 0 and t4 < -1.0: return "🟡 【AI破壊懸念】インフラ堅調・既存SaaS売り"
    elif t1 >= 0 and t4 >= 0: return "🟢 【正常】エネルギーからデータ層まで資金循環"
    return "⚪ 【注視】各レイヤーで強弱が混在"

def main():
    details = fetch_market_data()
    bedrock_data = fetch_bedrock_data()
    if not details: return

    tier_averages = calculate_tier_averages(details)
    status_msg = run_diagnostic(tier_averages, bedrock_data)

    output_data = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "config": INFRA_TIERS,
        "layers": tier_averages,
        "bedrock": bedrock_data,
        "status": status_msg,
        "details": details
    }

    with open('dashboard_data.json', 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

def fetch_forward_curve():
    """天然ガス先物の期近・期先スプレッドを取得"""
    try:
        tickers = yf.Tickers("NG=F NGZ27.NYM")
        near_hist = tickers.tickers['NG=F'].history(period="1d")
        far_hist = tickers.tickers['NGZ27.NYM'].history(period="1d")
        
        if near_hist.empty or far_hist.empty:
            return None
            
        near_price = float(near_hist['Close'].iloc[-1])
        far_price = float(far_hist['Close'].iloc[-1])
        spread = far_price - near_price
        
        signal = "🚨 【警報】バックワーデーション（バブル崩壊の兆候）" if spread < 0 else "✅ 【正常】コンタンゴ（順ざや維持）"
            
        return {
            "near_month_ticker": "NG=F (Front Month)",
            "near_month_price": round(near_price, 3),
            "far_month_ticker": "NGZ27.NYM (Dec 2027)",
            "far_month_price": round(far_price, 3),
            "spread_delta": round(spread, 3),
            "signal": signal
        }
    except Exception as e:
        print(f"Forward Curve Error: {e}")
        return None

def fetch_physical_grid_data():
    """EIA APIからPJMの物理的電力需要を取得"""
    api_key = os.environ.get("EIA_API_KEY")
    if not api_key:
        print("Error: EIA_API_KEY is not set.")
        return None

    url = "https://api.eia.gov/v2/electricity/rto/daily-region-data/data/"
    current_year = datetime.now().year
    
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

        labels, hist_min, hist_max, hist_avg, curr_year = [], [], [], [], []
        for mm_dd in sorted(historical_data.keys()):
            labels.append(mm_dd)
            h_vals = historical_data[mm_dd]
            hist_min.append(min(h_vals))
            hist_max.append(max(h_vals))
            hist_avg.append(round(sum(h_vals) / len(h_vals), 2))
            curr_year.append(current_data_map.get(mm_dd, None))

        return {
            "labels": labels,
            "historical_min": hist_min,
            "historical_max": hist_max,
            "historical_avg": hist_avg,
            "current_year": curr_year
        }
    except Exception as e:
        print(f"EIA API Error: {e}")
        return None

if __name__ == "__main__":
    main()
