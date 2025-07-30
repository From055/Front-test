# main.py
import pandas as pd
import FinanceDataReader as fdr
import seaborn as sns
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from tqdm import tqdm

def setup_korean_font():
    """
    한글 폰트를 설정하는 함수.
    matplotlib에서 한글이 깨지지 않도록 설정합니다.
    나눔고딕 폰트가 없는 경우 다른 사용 가능한 폰트를 찾습니다.
    """
    # 사용 가능한 폰트 목록 확인
    font_paths = fm.findSystemFonts(fontpaths=None, fontext='ttf')
    nanum_gothic_path = next((path for path in font_paths if 'NanumGothic' in path), None)

    if nanum_gothic_path:
        font_name = fm.FontProperties(fname=nanum_gothic_path).get_name()
        plt.rc('font', family=font_name)
        print(f"'{font_name}' 폰트를 설정했습니다.")
    else:
        print("나눔고딕 폰트를 찾을 수 없습니다. 기본 폰트를 사용합니다. 한글이 깨질 수 있습니다.")
    
    # 마이너스 부호 깨짐 방지
    plt.rcParams['axes.unicode_minus'] = False


def get_sector_daily_performance(sectors_to_analyze, start_date, end_date):
    """
    지정된 섹터의 일별 주가 등락률을 계산하고 시각화하는 함수.

    Args:
        sectors_to_analyze (list): 분석할 섹터 이름 리스트.
        start_date (str): 분석 시작일 (예: '2024-01-01').
        end_date (str): 분석 종료일 (예: '2024-01-31').
    
    Returns:
        pandas.DataFrame: 섹터별 일별 평균 등락률 데이터프레임.
    """
    try:
        # 1. 데이터 준비: KRX 상장 종목 목록과 섹터 정보 가져오기
        print("한국거래소(KRX) 상장 종목 목록을 가져오는 중...")
        krx_stocks = fdr.StockListing('KRX')
        krx_stocks = krx_stocks[['Code', 'Name', 'Sector']].dropna()
        krx_stocks = krx_stocks[krx_stocks['Sector'].isin(sectors_to_analyze)]
        print(f"분석 대상 종목 수: {len(krx_stocks)}개")

        if krx_stocks.empty:
            print("분석할 종목이 없습니다. 섹터 이름을 확인해주세요.")
            return None

        # 2. 주가 데이터 가져오기 및 수익률 계산
        all_returns = []
        print(f"\n{start_date}부터 {end_date}까지 주가 데이터를 가져오는 중...")

        # tqdm을 사용하여 진행 상황 표시
        for code, name, sector in tqdm(krx_stocks.itertuples(index=False), total=len(krx_stocks), desc="종목 데이터 처리 중"):
            try:
                # 종목의 일별 주가 데이터 가져오기
                price_df = fdr.DataReader(code, start=start_date, end=end_date)
                
                if not price_df.empty:
                    # 일일 수익률(%) 계산
                    daily_return = price_df['Close'].pct_change() * 100
                    daily_return.name = name
                    
                    # 섹터 정보 추가
                    return_df = daily_return.to_frame()
                    return_df['Sector'] = sector
                    all_returns.append(return_df)

            except Exception as e:
                # print(f"{name}({code}) 데이터 처리 중 오류 발생: {e}")
                continue # 오류 발생 시 다음 종목으로 넘어감

        if not all_returns:
            print("수익률을 계산할 데이터가 없습니다.")
            return None

        # 3. 데이터 통합 및 섹터별 평균 수익률 계산
        print("\n데이터 통합 및 섹터별 평균 수익률 계산 중...")
        combined_df = pd.concat(all_returns)
        
        # 날짜(Date)를 인덱스에서 컬럼으로 이동
        combined_df.reset_index(inplace=True)

        # 섹터별 일일 평균 수익률 계산
        sector_daily_returns = combined_df.groupby(['Date', 'Sector']).mean(numeric_only=True)
        
        # 컬럼 이름 변경 ('종목명' -> 'Return')
        sector_daily_returns.rename(columns={sector_daily_returns.columns[0]: 'Return'}, inplace=True)


        # 4. 시각화를 위한 데이터 재구성 (피벗 테이블)
        heatmap_data = sector_daily_returns.unstack(level='Sector')['Return']
        heatmap_data = heatmap_data.fillna(0) # 결측값은 0으로 채움

        return heatmap_data

    except Exception as e:
        print(f"전체 프로세스 중 오류 발생: {e}")
        return None

def plot_heatmap(heatmap_data, title):
    """
    데이터프레임을 히트맵으로 시각화하는 함수.
    
    Args:
        heatmap_data (pandas.DataFrame): 히트맵으로 그릴 데이터.
        title (str): 차트 제목.
    """
    if heatmap_data is None or heatmap_data.empty:
        print("시각화할 데이터가 없습니다.")
        return

    print("\n히트맵 시각화 생성 중...")
    plt.figure(figsize=(20, 10))
    sns.heatmap(
        heatmap_data.T,         # 행과 열을 바꿔서 섹터를 y축에 표시
        annot=True,             # 각 셀에 값 표시
        fmt=".2f",              # 소수점 둘째 자리까지 표시
        cmap="RdYlGn",          # 빨강-노랑-초록 색상 맵 사용
        linewidths=.5,          # 셀 사이의 간격
        center=0                # 색상 맵의 중앙값을 0으로 설정
    )
    plt.title(title, fontsize=20, pad=20)
    plt.xlabel("날짜", fontsize=15)
    plt.ylabel("섹터", fontsize=15)
    plt.xticks(rotation=45)
    plt.yticks(rotation=0)
    plt.tight_layout()
    plt.show()


if __name__ == '__main__':
    # --- 설정 ---
    # 1. 분석하고 싶은 섹터를 리스트 형태로 입력
    # 어떤 섹터가 있는지 확인하려면: 
    # krx = fdr.StockListing('KRX')
    # print(krx['Sector'].unique())
    SECTORS_TO_ANALYZE = [
        'IT서비스', 
        '소프트웨어', 
        '반도체와반도체장비',
        '은행', 
        '증권',
        '자동차'
    ]

    # 2. 분석 기간 설정
    START_DATE = '2024-05-01'
    END_DATE = '2024-05-31'
    # --- 설정 끝 ---

    # 한글 폰트 설정
    setup_korean_font()

    # 섹터별 일별 등락 데이터 가져오기
    sector_performance_data = get_sector_daily_performance(SECTORS_TO_ANALYZE, START_DATE, END_DATE)

    # 히트맵으로 시각화
    chart_title = f"섹터별 일일 평균 등락률 (%) ({START_DATE} ~ {END_DATE})"
    plot_heatmap(sector_performance_data, chart_title)

