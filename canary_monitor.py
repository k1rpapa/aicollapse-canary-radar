import yfinance as yf
import pandas as pd
import json
import datetime
import os
import requests

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
        
if __name__ == "__main__":
    main()
