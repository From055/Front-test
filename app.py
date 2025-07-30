# 파일명: app.py
# 기능: 수익률 계산 시 첫날이 누락되는 오류를 수정한 최종본 (v2.2)
# 이번 요청에서는 백엔드 코드는 변경할 필요가 없어! 아래 코드를 그대로 사용하면 돼.

from flask import Flask, request, jsonify
from flask_cors import CORS
import FinanceDataReader as fdr
import pandas as pd
from tqdm import tqdm
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)

# --- 서버 시작 시 데이터 미리 로드 ---
ALL_STOCKS_LIST = []
try:
    print("국내 및 해외 주식/ETF 목록을 로드하는 중... (시간이 걸릴 수 있습니다)")
    all_dfs = []
    market_list = {
        'KOSPI': 'KOSPI', 
        'KOSDAQ': 'KOSDAQ', 
        'ETF': 'ETF-KR', 
        'NASDAQ': 'NASDAQ', 
        'NYSE': 'NYSE'
    }

    for market_name, market_code in market_list.items():
        try:
            print(f"- {market_name} 목록 로드 중...")
            df = fdr.StockListing(market_code)
            if 'Symbol' in df.columns:
                df.rename(columns={'Symbol': 'Code'}, inplace=True)
            all_dfs.append(df[['Code', 'Name']])
            print(f"- {market_name} 로드 완료.")
        except Exception as e:
            print(f"!! {market_name} 목록 로드 실패 (무시하고 계속 진행): {e}")

    if all_dfs:
        stocks = pd.concat(all_dfs, ignore_index=True)
        stocks = stocks.dropna().drop_duplicates(subset=['Code']).reset_index(drop=True)
        ALL_STOCKS_LIST = stocks.to_dict(orient='records')
        print(f"전체 종목 목록 로드 완료. 총 {len(ALL_STOCKS_LIST)}개 종목/ETF.")
    else:
        print("!!! 모든 시장의 종목 목록을 로드하는 데 실패했습니다.")
        
except Exception as e:
    print(f"종목 목록 로드 중 심각한 오류 발생: {e}")

# --- API 엔드포인트 ---
@app.route('/api/all-stocks', methods=['GET'])
def get_all_stocks():
    if not ALL_STOCKS_LIST:
        return jsonify({"error": "서버에서 종목 목록을 로드하지 못했습니다."}), 500
    return jsonify({"stocks": ALL_STOCKS_LIST})

def resample_and_calculate_returns(price_df, timeframe):
    if timeframe == 'D':
        return price_df['Close'].pct_change() * 100

    resample_period = {'W': 'W-FRI', 'M': 'M'}.get(timeframe)
    resampled_price = price_df['Close'].resample(resample_period).last()
    return resampled_price.pct_change() * 100

@app.route('/api/stock-data', methods=['POST'])
def get_stock_data():
    data = request.get_json()
    themes = data.get('themes', [])
    start_date = data.get('startDate')
    end_date = data.get('endDate')
    timeframe = data.get('timeframe', 'D')

    if not all([start_date, end_date]) or not themes:
        return jsonify({"error": "필수 파라미터가 누락되었습니다."}), 400

    start_date_dt = datetime.strptime(start_date, '%Y-%m-%d')
    effective_start_date = (start_date_dt - timedelta(days=7)).strftime('%Y-%m-%d')

    themed_returns_data = {}
    stock_level_returns = []

    for theme in tqdm(themes, desc="테마 데이터 처리 중"):
        theme_name = theme.get('name')
        theme_codes = theme.get('codes', [])
        
        theme_period_returns_list = []
        for code in theme_codes:
            try:
                stock_info = next((item for item in ALL_STOCKS_LIST if item["Code"] == code), None)
                stock_name = stock_info['Name'] if stock_info else code
                
                price_df = fdr.DataReader(code, effective_start_date, end_date)
                
                if not price_df.empty:
                    period_return = resample_and_calculate_returns(price_df, timeframe)
                    theme_period_returns_list.append(period_return)
                    
                    if timeframe == 'D':
                        daily_return = price_df['Close'].pct_change() * 100
                        stock_df = pd.DataFrame({
                            'date': daily_return.index.strftime('%Y-%m-%d'),
                            'stock_name': f"{stock_name} ({code})",
                            'value': daily_return.round(2)
                        }).dropna()
                        stock_level_returns.append(stock_df[stock_df['date'] >= start_date])
            except Exception:
                continue
        
        if theme_period_returns_list:
            theme_avg_return = pd.concat(theme_period_returns_list, axis=1).mean(axis=1)
            themed_returns_data[theme_name] = theme_avg_return.dropna()

    if not themed_returns_data:
        return jsonify({"error": "데이터를 계산할 수 없습니다."}), 500

    correlation_df = pd.DataFrame(themed_returns_data)
    correlation_df = correlation_df.loc[start_date:]
    correlation_matrix = correlation_df.corr()
    
    final_themed_returns = []
    for theme_name, return_series in themed_returns_data.items():
        filtered_series = return_series.loc[start_date:]
        theme_df = pd.DataFrame({
            'date': filtered_series.index.strftime('%Y-%m-%d'),
            'sector': theme_name, 
            'value': filtered_series.round(2)
        })
        final_themed_returns.extend(theme_df.to_dict(orient='records'))
        
    final_stock_df = pd.concat(stock_level_returns) if stock_level_returns else pd.DataFrame()

    response_data = {
        "themed_returns": final_themed_returns,
        "stock_level_returns": final_stock_df.to_dict(orient='records'),
        "correlation_matrix": correlation_matrix.to_dict(orient='index')
    }
    
    return jsonify(response_data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)

