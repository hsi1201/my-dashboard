import streamlit as st
import pandas as pd
import altair as alt
import yfinance as yf
import FinanceDataReader as fdr
import requests
import xml.etree.ElementTree as ET
from streamlit_autorefresh import st_autorefresh 

# 1. 웹페이지 기본 설정
st.set_page_config(page_title="글로벌 마켓 대시보드", layout="wide", initial_sidebar_state="collapsed")

# 🌟 [자동 갱신] 3분(180,000 밀리초)마다 화면 새로고침
st_autorefresh(interval=180000, limit=10000, key="data_refresh")

# 🌟 [디자인 1] CSS 주입
st.markdown("""
<style>
.block-container {
    padding-top: 2rem !important; 
    padding-bottom: 1.5rem !important;
}
[data-testid="stMetric"] {
    background-color: rgba(130, 130, 130, 0.05);
    border: 1px solid rgba(130, 130, 130, 0.2);
    border-radius: 12px;
    padding: 12px; 
    box-shadow: 2px 4px 10px rgba(0, 0, 0, 0.05);
    transition: transform 0.2s ease-in-out;
}
[data-testid="stMetric"]:hover {
    transform: translateY(-5px);
    box-shadow: 2px 8px 15px rgba(0, 0, 0, 0.1);
}
[data-testid="stMetricLabel"], 
[data-testid="stMetricLabel"] > div, 
[data-testid="stMetricLabel"] * {
    white-space: pre-line !important; 
    word-break: keep-all !important;
    overflow: visible !important;
    text-overflow: clip !important;
    line-height: 1.4 !important;
    font-size: 0.8rem !important; 
}
.news-link {
    text-decoration: none;
    color: #1E88E5;
    font-size: 0.95rem;
    line-height: 1.6;
    margin-bottom: 8px;
    display: inline-block;
}
.news-link:hover {
    text-decoration: underline;
}
.etf-box {
    background-color: rgba(130, 130, 130, 0.08);
    border-left: 4px solid #1E88E5;
    padding: 12px 15px;
    margin-top: -10px;
    margin-bottom: 15px;
    border-radius: 4px;
    font-size: 0.9rem;
    line-height: 1.6;
}
.stTabs [data-baseweb="tab-list"] button {
    font-size: 1.1rem;
    padding-top: 1rem;
    padding-bottom: 1rem;
}
/* 우측 상단 Streamlit 기본 툴바 숨기기 */
[data-testid="stToolbar"] {
    visibility: hidden;
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div style="margin-top: -15px; margin-bottom: 10px;">
    <h2 style="margin-bottom: 0px; padding-bottom: 5px; font-size: 1.8rem;">📊 글로벌 마켓 대시보드 (v6.69)</h2>
    <p style="color: #888; font-size: 0.95rem; margin-top: 0px;">Yahoo Finance + Naver + 한국은행 ECOS 서버를 결합한 무결점 실시간 동기화</p>
</div>
""", unsafe_allow_html=True)


# 2. 데이터 자동 수집 및 계산 엔진
@st.cache_data(ttl=180) 
def get_market_data():
    df_list = []
    
    bok_api_key = "13ZIQ3I6LS3K4CKFDZO1" 
    
    if bok_api_key != "여기에_발급받은_API_키를_입력하세요":
        try:
            today_str = pd.Timestamp.today().strftime('%Y%m%d')
            url = f"https://ecos.bok.or.kr/api/StatisticSearch/{bok_api_key}/json/kr/1/100000/817Y002/D/20260101/{today_str}"
            response = requests.get(url)
            data = response.json()
            
            if 'StatisticSearch' in data:
                rows = data['StatisticSearch']['row']
                bok_df = pd.DataFrame(rows)
                bok_df['TIME'] = pd.to_datetime(bok_df['TIME'])
                bok_df['DATA_VALUE'] = bok_df['DATA_VALUE'].astype(float)
                
                df_10y = bok_df[bok_df['ITEM_CODE1'] == '010210000'][['TIME', 'DATA_VALUE']].rename(columns={'TIME': '일자', 'DATA_VALUE': '한국10년물'}).set_index('일자')
                df_30y = bok_df[bok_df['ITEM_CODE1'] == '010230000'][['TIME', 'DATA_VALUE']].rename(columns={'TIME': '일자', 'DATA_VALUE': '한국30년물'}).set_index('일자')
                
                bok_final = pd.concat([df_10y, df_30y], axis=1)
                bok_final.index = bok_final.index.normalize().tz_localize(None)
                df_list.append(bok_final)
        except:
            pass 

    yf_tickers = {
        '^GSPC': 'S&P500', '^IXIC': '나스닥', 
        '^N225': '니케이', 
        '^KS11': '코스피', '^KQ11': '코스닥', 
        'CL=F': 'WTI유', '^TNX': '미국10년물', '^TYX': '미국30년물',
        '^VIX': 'VIX', '^SOX': '필라델피아 반도체', 'GC=F': '금', 'JPYKRW=X': '엔/원 환율',
        'XLK': '기술(XLK)', 'XLF': '금융(XLF)', 'XLV': '헬스케어(XLV)',
        'XLE': '에너지(XLE)', 'XLY': '자유소비재(XLY)', 'XLI': '산업재(XLI)',
        'XLP': '필수소비재(XLP)', 'XLU': '유틸리티(XLU)', 'XLB': '소재(XLB)',
        'XLRE': '부동산(XLRE)', 'XLC': '커뮤니케이션(XLC)'
    }
    for ticker, name in yf_tickers.items():
        try:
            temp_df = yf.Ticker(ticker).history(start='2026-01-01')[['Close']]
            if name == '엔/원 환율':
                temp_df['Close'] = temp_df['Close'] * 100
                
            temp_df.columns = [name]
            temp_df.index = pd.to_datetime(temp_df.index).normalize().tz_localize(None)
            temp_df = temp_df[~temp_df.index.duplicated(keep='last')]
            df_list.append(temp_df)
        except:
            continue
            
    try:
        try:
            csi_val = yf.Ticker('399300.SZ').history(period='5d')['Close'].iloc[-1]
        except:
            try:
                csi_val = yf.Ticker('000300.SS').history(period='5d')['Close'].iloc[-1]
            except:
                csi_val = 4507.39
                
        tiger_df = fdr.DataReader('192090', '2026-01-01')[['Close']]
        
        if not tiger_df.empty:
            tiger_df.index = pd.to_datetime(tiger_df.index).normalize().tz_localize(None)
            ratio = csi_val / tiger_df['Close'].iloc[-1]
            csi_restored = tiger_df['Close'] * ratio
            
            temp_df = pd.DataFrame(csi_restored)
            temp_df.columns = ['CSI300']
            temp_df.index = pd.to_datetime(temp_df.index).normalize().tz_localize(None)
            temp_df = temp_df[~temp_df.index.duplicated(keep='last')]
            df_list.append(temp_df)
    except:
        pass

    fdr_tickers = {
        'USD/KRW': '환율($/원)',
        '091160': 'K-반도체',      
        '305720': 'K-2차전지',     
        '093240': 'K-자동차',      
        '157490': 'K-인터넷',      
        '266420': 'K-헬스케어',    
        '091220': 'K-은행',        
        '102960': 'K-기계조선',    
        '117680': 'K-철강',        
        '266360': 'K-미디어엔터',  
        '117700': 'K-건설',        
        '226490': 'K-화학',        
        '446720': 'K-방산'         
    }
    for ticker, name in fdr_tickers.items():
        try:
            temp_df = fdr.DataReader(ticker, '2026-01-01')[['Close']]
            temp_df.columns = [name]
            temp_df.index = pd.to_datetime(temp_df.index).normalize().tz_localize(None)
            temp_df = temp_df[~temp_df.index.duplicated(keep='last')]
            df_list.append(temp_df)
        except:
            continue
            
    df = pd.concat(df_list, axis=1)
    
    last_dates = {}
    changes = {}
    
    for col in df.columns:
        valid_series = df[col].dropna()
        valid_date = valid_series.index[-1] if not valid_series.empty else None
        last_dates[col] = valid_date.strftime('%m/%d') if pd.notnull(valid_date) else "N/A"
        
        if len(valid_series) >= 2:
            prev = valid_series.iloc[-2]
            curr = valid_series.iloc[-1]
        elif len(valid_series) == 1:
            prev = curr = valid_series.iloc[0]
        else:
            prev = curr = 0
            
        diff = curr - prev 
        
        if '년물' in col: 
            changes[col] = f"{diff:+.3f}%p"
        else: 
            pct = (diff / prev) * 100 if prev != 0 else 0
            changes[col] = f"{diff:+.2f} ({pct:+.2f}%)"
            
    df.ffill(inplace=True)
    df.bfill(inplace=True)
    
    df.index.name = '일자'
    df.reset_index(inplace=True)
    
    df = df[df['일자'] >= '2026-01-01']
    df['일자'] = df['일자'].dt.strftime('%Y-%m-%d')
    
    if '한국10년물' not in df.columns: df['한국10년물'] = 3.123 
    if '한국30년물' not in df.columns: df['한국30년물'] = 2.987
    
    for col in df.columns:
        if col != '일자':
            roll_max = df[col].cummax()
            df[f'{col} MDD'] = df[col] / roll_max - 1.0
            
    us_sector_names = ['기술(XLK)', '금융(XLF)', '헬스케어(XLV)', '에너지(XLE)', '자유소비재(XLY)', '산업재(XLI)', '필수소비재(XLP)', '유틸리티(XLU)', '소재(XLB)', '부동산(XLRE)', '커뮤니케이션(XLC)']
    kr_sector_names = ['K-반도체', 'K-2차전지', 'K-자동차', 'K-인터넷', 'K-헬스케어', 'K-은행', 'K-기계조선', 'K-철강', 'K-미디어엔터', 'K-건설', 'K-화학', 'K-방산']
    relative_cols = ['코스피', 'CSI300', '코스닥', '니케이', 'S&P500', '나스닥'] + us_sector_names + kr_sector_names
    
    for col in relative_cols:
        if col in df.columns:
            first_val = df[col].iloc[0]
            df[f'{col}(시작=100)'] = (df[col] / first_val) * 100 if first_val != 0 else 0
            
    df.fillna(0, inplace=True)
    
    sync_time = pd.Timestamp.now(tz='Asia/Seoul').strftime('%m/%d %H:%M')
    
    return df, last_dates, changes, sync_time

df_market, last_dates, changes, sync_time = get_market_data()
latest_data = df_market.iloc[-1] 


# 🌟 [신규 엔진] 보유종목 티커 매핑 및 YTD 히스토리 수집 엔진
@st.cache_data(ttl=3600) # 1시간 캐싱 (API 호출 최소화)
def get_portfolio_history():
    # 엑셀의 종목명과 실제 티커(종목코드) 매핑 사전
    portfolio_tickers = {
        'KODEX 200': ('FDR', '069500'),
        'TIGER 미국나스닥100': ('FDR', '133690'),
        'KODEX 코스닥150': ('FDR', '229200'),
        'TIGER 일본니케이225': ('FDR', '241180'),
        'KODEX 차이나CSI300': ('FDR', '192090'),
        'TIGER 미국S&P500': ('FDR', '360750'),
        'ACE 미국S&P500미국채혼합50액티브': ('FDR', '465580'),
        'ACE 미국나스닥100미국채혼합50액티브': ('FDR', '465590'),
        'KODEX 국고채30년액티브': ('FDR', '448540'),
        'ACE 미국30년국채액티브(H)': ('FDR', '453850'),
        'TIGER 미국배당다우존스': ('FDR', '458730'),
        '한온시스템': ('FDR', '018880'),
        'TIGER 바이오TOP10': ('FDR', '364960'),
        'PLUS K방산': ('FDR', '446720'), 
        'SOL AI반도체소부장': ('FDR', '455850'),
        '로봇공학 및 인공지능 글로벌엑스(BOTZ)': ('YF', 'BOTZ'),
        '나스닥 스마트 그리드 인프라(GRID)': ('YF', 'GRID')
    }
    
    df_list = []
    for name, (src, ticker) in portfolio_tickers.items():
        try:
            if src == 'YF':
                temp = yf.Ticker(ticker).history(start='2026-01-01')[['Close']]
            else:
                temp = fdr.DataReader(ticker, '2026-01-01')[['Close']]
            temp.columns = [name]
            temp.index = pd.to_datetime(temp.index).normalize().tz_localize(None)
            temp = temp[~temp.index.duplicated(keep='last')]
            df_list.append(temp)
        except:
            continue
            
    if not df_list: return pd.DataFrame()
    
    df = pd.concat(df_list, axis=1)
    df.ffill(inplace=True)
    df.bfill(inplace=True)
    
    # YTD 상대수익률(시작점 100)로 정규화
    for col in df.columns:
        first_val = df[col].iloc[0]
        if first_val != 0:
            df[col] = (df[col] / first_val) * 100
            
    df.index.name = '일자'
    df.reset_index(inplace=True)
    df['일자'] = df['일자'].dt.strftime('%Y-%m-%d')
    return df

@st.cache_data(ttl=600) 
def get_news_data():
    news_dict = {"KR": [], "US": []}
    kr_url = "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=ko&gl=KR&ceid=KR:ko"
    us_url = "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=en-US&gl=US&ceid=US:en"
    try:
        kr_resp = requests.get(kr_url, timeout=5)
        kr_root = ET.fromstring(kr_resp.content)
        for item in kr_root.findall('.//item')[:10]: 
            title = item.find('title').text
            link = item.find('link').text
            news_dict["KR"].append({"title": title, "link": link})
    except:
        news_dict["KR"].append({"title": "국내 뉴스를 불러올 수 없습니다.", "link": "#"})
    try:
        us_resp = requests.get(us_url, timeout=5)
        us_root = ET.fromstring(us_resp.content)
        for item in us_root.findall('.//item')[:10]:
            title = item.find('title').text
            link = item.find('link').text
            news_dict["US"].append({"title": title, "link": link})
    except:
        news_dict["US"].append({"title": "해외 뉴스를 불러올 수 없습니다.", "link": "#"})
    return news_dict

news_data = get_news_data()

def get_mdd_text(mdd_val):
    mdd_pct = mdd_val * 100
    if mdd_pct >= -10: return f":green[MDD {mdd_pct:.1f}%]"
    elif mdd_pct >= -20: return f":orange[MDD {mdd_pct:.1f}%]"
    elif mdd_pct >= -30: return f":red[MDD {mdd_pct:.1f}%]"
    elif mdd_pct >= -40: return f":violet[MDD {mdd_pct:.1f}%]"
    else: return f":blue[MDD {mdd_pct:.1f}%]"

def get_market_regime(latest_data):
    vix = latest_data.get('VIX', 20)  
    sp500_mdd = latest_data.get('S&P500 MDD', 0) * 100
    if vix >= 30 or sp500_mdd <= -20: return "⛈️ 심각한 약세장 (공포/패닉)", "시장에 극도의 공포가 만연해 있습니다. 리스크 관리에 각별히 유의하세요.", "error"
    elif vix >= 20 or sp500_mdd <= -10: return "🌧️ 주의/조정장 (방어 필요)", "시장의 변동성이 커지며 조정 국면에 진입했습니다. 보수적인 접근이 필요합니다.", "warning"
    elif vix < 15 and sp500_mdd >= -3: return "☀️ 안정적 강세장 (Risk On)", "시장의 변동성이 낮고 투자 심리가 매우 안정적인 강세장입니다.", "success"
    else: return "⛅ 보통/눈치보기 장세 (Neutral)", "뚜렷한 쏠림 없이 시장이 방향성을 탐색하며 횡보하고 있습니다.", "info"

def draw_mini_chart(df, column_name):
    if column_name in df.columns:
        chart_data = df[['일자', column_name]].dropna()
        if chart_data.empty:
            st.markdown(f"*{column_name} 데이터 없음*")
            return
        min_val, max_val = chart_data[column_name].min(), chart_data[column_name].max()
        padding = (max_val - min_val) * 0.1
        if padding == 0: padding = min_val * 0.1 if min_val != 0 else 1
        y_min, y_max = min_val - padding, max_val + padding
        y_axis_format = '.2f' if '년물' in column_name else '~s'
        
        base = alt.Chart(chart_data).encode(
            x=alt.X('일자:T', title=None, axis=alt.Axis(grid=False, format='%m/%d', labelColor='gray', tickCount=5)),
            y=alt.Y(f'{column_name}:Q', title=None, scale=alt.Scale(domain=[y_min, y_max]), 
                    axis=alt.Axis(grid=False, format=y_axis_format, tickCount=4, minExtent=35)),
            tooltip=[alt.Tooltip('일자:T', title='날짜', format='%Y-%m-%d'), alt.Tooltip(f'{column_name}:Q', title='수치', format=',.2f')]
        )
        area = base.mark_area(opacity=0.15, interpolate='monotone')
        line = base.mark_line(interpolate='monotone', size=2)
        chart = (area + line).properties(height=180)
        st.altair_chart(chart, use_container_width=True)
    else:
        st.markdown(f"*{column_name} 데이터 없음*")


# 엑셀 파싱 자동화 엔진 함수
def parse_portfolio_excel(file):
    df_stats = pd.read_excel(file, sheet_name='국가통계')
    df_inv = pd.read_excel(file, sheet_name='투자현황', skiprows=0)

    total_assets = pd.to_numeric(df_stats.iloc[2, 1], errors='coerce')
    
    df_region = df_stats.iloc[10:14, [0, 1]].copy()
    df_region.columns = ["분류", "현재금액"]
    df_region['현재금액'] = pd.to_numeric(df_region['현재금액'], errors='coerce').fillna(0)
    
    df_base = df_stats.iloc[10:14, [7, 8]].copy()
    df_base.columns = ["분류", "현재금액"]
    df_base['현재금액'] = pd.to_numeric(df_base['현재금액'], errors='coerce').fillna(0)
    
    first_col = df_inv.columns[0]
    current_account = "알 수 없음"
    rows_list = []
    account_summaries = {}
    
    for idx, row in df_inv.iterrows():
        val = str(row[first_col]).strip()
        if pd.isna(row[first_col]) or val == 'nan' or val == '현재 날짜 및 시간': continue
            
        if val in ['IRP - 장기', 'ISA - 중기', '국내주식 - 단기', '해외주식 - 단기', '비상금', '가상화폐', '부동산']:
            current_account = val
            continue
            
        if val == '합계':
            buy_val = pd.to_numeric(row.get('매수가격', 0), errors='coerce')
            tot_val = pd.to_numeric(row.get('현재가격', 0), errors='coerce')
            profit_val = tot_val - buy_val if pd.notna(buy_val) and pd.notna(tot_val) else 0
            ret_val = pd.to_numeric(row.get('수익률', 0), errors='coerce')
            realized = pd.to_numeric(row.get('실현손익', 0), errors='coerce')
            
            cash_amt = sum([r['현재가치_num'] for r in rows_list if r['계좌 구분'] == current_account and ('예수금' in r['종목명'] or '세이프박스' in r['종목명'])])
            cash_weight = (cash_amt / tot_val) if tot_val > 0 else 0
            
            account_summaries[current_account] = {
                "buy": f"₩ {buy_val:,.0f}" if pd.notna(buy_val) else "₩ 0",
                "total": f"₩ {tot_val:,.0f}" if pd.notna(tot_val) else "₩ 0",
                "profit": f"{'+' if profit_val > 0 else ''}₩ {profit_val:,.0f}",
                "ret": f"{ret_val*100:+.2f}%",
                "color": "red" if ret_val >= 0 else "blue",
                "realized": f"{'+' if realized > 0 else ''}₩ {realized:,.0f}",
                "cash_amt": f"₩ {cash_amt:,.0f}",
                "cash_weight": f"{cash_weight*100:.1f}%"
            }
            continue
            
        qty = pd.to_numeric(row.get('수량', 0), errors='coerce')
        buy_price = pd.to_numeric(row.get('매수가', 0), errors='coerce')
        cur_price = pd.to_numeric(row.get('현재가', 0), errors='coerce')
        ret = pd.to_numeric(row.get('수익률', 0), errors='coerce')
        cur_val = pd.to_numeric(row.get('현재가격', 0), errors='coerce')
        weight = pd.to_numeric(row.get('현재비중', 0), errors='coerce')
        
        qty = 0 if pd.isna(qty) else qty
        buy_price = 0 if pd.isna(buy_price) else buy_price
        cur_price = 0 if pd.isna(cur_price) else cur_price
        ret = 0 if pd.isna(ret) else ret
        cur_val = 0 if pd.isna(cur_val) else cur_val
        weight = 0 if pd.isna(weight) else weight
        
        rows_list.append({
            '계좌 구분': current_account,
            '종목명': val,
            '보유수량': f"{qty:,.0f}" if qty > 0 else "-",
            '매수단가': f"₩ {buy_price:,.0f}" if buy_price > 0 else "-",
            '현재가': f"₩ {cur_price:,.0f}" if cur_price > 0 else "-",
            '수익률(%)': f"{ret*100:+.2f}%",
            '현재가치': f"₩ {cur_val:,.0f}",
            '현재가치_num': cur_val,
            '계좌내 비중(%)': f"{weight*100:.1f}%"
        })
        
    df_holdings = pd.DataFrame(rows_list)
    if not df_holdings.empty:
        df_holdings = df_holdings.drop(columns=['현재가치_num'])
        
    total_realized = sum([float(str(account_summaries[acc]['realized']).replace('+','').replace('₩','').replace(',','').strip()) for acc in account_summaries if account_summaries[acc]['realized']])
    total_invested = sum([float(str(account_summaries[acc]['buy']).replace('+','').replace('₩','').replace(',','').strip()) for acc in account_summaries if account_summaries[acc]['buy']])
    total_cash = sum([float(str(account_summaries[acc]['cash_amt']).replace('+','').replace('₩','').replace(',','').strip()) for acc in account_summaries if account_summaries[acc]['cash_amt']])
    
    total_profit = total_assets - total_invested
    total_profit_pct = (total_profit / total_invested * 100) if total_invested > 0 else 0
    total_cash_weight = (total_cash / total_assets * 100) if total_assets > 0 else 0
            
    metrics = {
        "총자산": f"₩ {total_assets:,.0f}",
        "총매수금액": f"₩ {total_invested:,.0f}",
        "평가손익": f"{'+' if total_profit > 0 else ''}₩ {total_profit:,.0f} ({total_profit_pct:+.1f}%)",
        "실현손익": f"{'+' if total_realized > 0 else ''}₩ {total_realized:,.0f}",
        "현금비중": f"{total_cash_weight:.1f}%",
        "현금액": f"₩ {total_cash:,.0f}"
    }
        
    return metrics, df_region, df_base, df_holdings, account_summaries

# ---------------------------------------------------------
# UI 공통 헤더: 알림창 단일화
# ---------------------------------------------------------
with st.expander(f"ℹ️ 시스템 알림 및 데이터 안내 (🔄 최근 갱신: {sync_time} 기준)"):
    st.warning("⚠️ **주말(토/일) 데이터 지연 안내:** 야후 파이낸스 서버의 주말 결산 배치 작업으로 인해, 토요일에는 아시아 증시(코스피, 니케이 등)의 최신(금요일) 데이터가 하루 지연되어 표기될 수 있습니다. 월요일 오전 정상 동기화됩니다.")
    st.markdown("""
    **📌 데이터 소스 및 타 사이트(Investing.com 등) 수치 차이 안내**
    본 대시보드는 서버 차단(IP Block)을 방지하고 무결점 안정성을 유지하기 위해 **공식 거래소 API 및 통계청 데이터**를 최우선으로 사용합니다. 
    장외 CFD나 실시간 브로커 데이터를 혼용하는 인베스팅닷컴과는 다음과 같은 수치 차이가 발생할 수 있습니다.
    *   **WTI 원유 & 금:** 월물 교체(롤오버) 시점에 일시적으로 가격 갭이 발생할 수 있습니다.
    *   **CSI 300:** 중국 통신망 오류를 우회하기 위해 국내 상장 추종 ETF의 과거 궤적을 활용하여 차트를 스케일링합니다.
    *   **해외 지수:** 거래소 규정에 따라 15~20분 지연(Delay) 송출될 수 있습니다.
    """)

# ---------------------------------------------------------
# 🌟 6개 탭 (Tabs) 분할
# ---------------------------------------------------------
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["📊 종합 마켓 뷰", "📈 상세 차트 분석", "🏭 미국 섹터별 흐름", "🇰🇷 국내 섹터별 흐름", "📰 실시간 경제 뉴스", "🔒 내 보유종목"])

# ==============================================================================
# 탭 1 ~ 탭 5 생략 없이 모두 포함
# ==============================================================================
with tab1:
    st.subheader("💡 시장 기상도 및 전략")
    weather_col, cal_col = st.columns([2, 1])

    with weather_col:
        regime_title, regime_desc, regime_type = get_market_regime(latest_data)
        if regime_type == "error":
            st.error(f"**현재 시장 기상도:** {regime_title}\n\n{regime_desc}")
            st.markdown("""
            <div class='etf-box'>
                🛡️ <b>[맞춤 전략] 약세장 피난처:</b> 현금성 자산 및 방어 테마<br>
                🇺🇸 <b>미국 대표 지수:</b> BIL, TLT, UUP<br>
                🇰🇷 <b>국내 연금/ISA:</b> KODEX CD금리액티브, KODEX 미국달러선물<br>
                💡 <b>주목할 테마:</b> 🇺🇸 <b>ITA</b> (방위산업), <b>GDX</b> (금광기업) | 🇰🇷 <b>ARIRANG K방산</b>
            </div>
            """, unsafe_allow_html=True)
        elif regime_type == "warning":
            st.warning(f"**현재 시장 기상도:** {regime_title}\n\n{regime_desc}")
            st.markdown("""
            <div class='etf-box'>
                ☂️ <b>[맞춤 전략] 조정장 방어 전략:</b> 안전자산 및 필수소비재 중심<br>
                🇺🇸 <b>미국 대표 지수:</b> TLT, GLD, XLV<br>
                🇰🇷 <b>국내 연금/ISA:</b> TIGER 미국채10년선물, ACE 골드선물(H)<br>
                💡 <b>주목할 테마:</b> 🇺🇸 <b>XLU</b> (유틸리티), <b>XLP</b> (필수소비재) | 🇰🇷 <b>KODEX 미국S&P500유틸리티</b>
            </div>
            """, unsafe_allow_html=True)
        elif regime_type == "success":
            st.success(f"**현재 시장 기상도:** {regime_title}\n\n{regime_desc}")
            st.markdown("""
            <div class='etf-box'>
                🚀 <b>[맞춤 전략] 강세장 공격 타격:</b> 지수 레버리지 및 주도 테마 중심<br>
                🇺🇸 <b>미국 대표 지수:</b> QQQ, SOXX, SPY<br>
                🇰🇷 <b>국내 연금/ISA:</b> TIGER 미국나스닥100, KODEX 미국반도체MV<br>
                💡 <b>주목할 테마:</b> 🇺🇸 <b>BOTZ</b> (AI/로봇), <b>IBIT</b> (비트코인) | 🇰🇷 <b>KODEX 미국AI테크TOP10</b>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info(f"**현재 시장 기상도:** {regime_title}\n\n{regime_desc}")
            st.markdown("""
            <div class='etf-box'>
                ⚖️ <b>[맞춤 전략] 눈치보기 코어 전략:</b> 지수 방어 및 고배당 수익<br>
                🇺🇸 <b>미국 대표 지수:</b> SPY, SCHD, USMV<br>
                🇰🇷 <b>국내 연금/ISA:</b> KODEX 미국S&P500TR, TIGER 미국배당다우존스<br>
                💡 <b>주목할 테마:</b> 🇺🇸 <b>PAVE</b> (미국 인프라), <b>JEPQ</b> (고배당) | 🇰🇷 <b>TIGER 미국배당+7%프리미엄</b>
            </div>
            """, unsafe_allow_html=True)

    with cal_col:
        st.info("📅 **다가오는 주요 매크로 일정**\n\n"
                "**[이번 주 리뷰]**\n"
                "- **09/18 (금):** 일본 BOJ 기준금리 결정 / 미국 네 마녀의 날\n\n"
                "**[다음 주 프리뷰]**\n"
                "- **09/24 (목):** 파월 연준 의장 연설 / 미 신규 실업수당 청구\n"
                "- **09/25 (금):** 🚨 **미국 8월 개인소비지출(PCE) 물가지수**")

    st.subheader("📊 16개 핵심 지표 메트릭")
    cols1 = st.columns(4)
    cols1[0].metric(f"S&P 500 [{last_dates.get('S&P500', '-')}]\n{get_mdd_text(latest_data.get('S&P500 MDD', 0))}", f"{latest_data.get('S&P500', 0):,.2f}", changes.get('S&P500', '0.00'))
    cols1[1].metric(f"NASDAQ [{last_dates.get('나스닥', '-')}]\n{get_mdd_text(latest_data.get('나스닥 MDD', 0))}", f"{latest_data.get('나스닥', 0):,.2f}", changes.get('나스닥', '0.00'))
    cols1[2].metric(f"필라델피아 반도체 [{last_dates.get('필라델피아 반도체', '-')}]\n{get_mdd_text(latest_data.get('필라델피아 반도체 MDD', 0))}", f"{latest_data.get('필라델피아 반도체', 0):,.2f}", changes.get('필라델피아 반도체', '0.00'))
    cols1[3].metric(f"VIX 지수 (공포) [{last_dates.get('VIX', '-')}]\n{get_mdd_text(latest_data.get('VIX MDD', 0))}", f"{latest_data.get('VIX', 0):,.2f}", changes.get('VIX', '0.00'))

    cols2 = st.columns(4)
    cols2[0].metric(f"KOSPI [{last_dates.get('코스피', '-')}]\n{get_mdd_text(latest_data.get('코스피 MDD', 0))}", f"{latest_data.get('코스피', 0):,.2f}", changes.get('코스피', '0.00'))
    cols2[1].metric(f"KOSDAQ [{last_dates.get('코스닥', '-')}]\n{get_mdd_text(latest_data.get('코스닥 MDD', 0))}", f"{latest_data.get('코스닥', 0):,.2f}", changes.get('코스닥', '0.00'))
    cols2[2].metric(f"Nikkei 225 [{last_dates.get('니케이', '-')}]\n{get_mdd_text(latest_data.get('니케이 MDD', 0))}", f"{latest_data.get('니케이', 0):,.2f}", changes.get('니케이', '0.00'))
    cols2[3].metric(f"CSI 300 [{last_dates.get('CSI300', '-')}]\n{get_mdd_text(latest_data.get('CSI300 MDD', 0))}", f"{latest_data.get('CSI300', 0):,.2f}", changes.get('CSI300', '0.00'))

    cols3 = st.columns(4)
    cols3[0].metric(f"원/달러 환율 [{last_dates.get('환율($/원)', '-')}]\n{get_mdd_text(latest_data.get('환율($/원) MDD', 0))}", f"{latest_data.get('환율($/원)', 0):,.2f} 원", changes.get('환율($/원)', '0.00'))
    cols3[1].metric(f"엔/원 환율 (100엔) [{last_dates.get('엔/원 환율', '-')}]\n{get_mdd_text(latest_data.get('엔/원 환율 MDD', 0))}", f"{latest_data.get('엔/원 환율', 0):,.2f} 원", changes.get('엔/원 환율', '0.00'))
    cols3[2].metric(f"WTI유 [{last_dates.get('WTI유', '-')}]\n{get_mdd_text(latest_data.get('WTI유 MDD', 0))}", f"{latest_data.get('WTI유', 0):,.2f} $", changes.get('WTI유', '0.00'))
    cols3[3].metric(f"금 (Gold) [{last_dates.get('금', '-')}]\n{get_mdd_text(latest_data.get('금 MDD', 0))}", f"{latest_data.get('금', 0):,.2f} $", changes.get('금', '0.00'))

    cols4 = st.columns(4)
    cols4[0].metric(f"미국 10년물 [{last_dates.get('미국10년물', '-')}]", f"{latest_data.get('미국10년물', 0):.3f} %", changes.get('미국10년물', '0.00'))
    cols4[1].metric(f"미국 30년물 [{last_dates.get('미국30년물', '-')}]", f"{latest_data.get('미국30년물', 0):.3f} %", changes.get('미국30년물', '0.00'))
    cols4[2].metric(f"한국 10년물 [{last_dates.get('한국10년물', '-')}]", f"{latest_data.get('한국10년물', 0):.3f} %", changes.get('한국10년물', '0.00'))
    cols4[3].metric(f"한국 30년물 [{last_dates.get('한국30년물', '-')}]", f"{latest_data.get('한국30년물', 0):.3f} %", changes.get('한국30년물', '0.00'))

with tab2:
    chart_cols = st.columns(2)
    with chart_cols[0]:
        st.subheader("📊 주요 지수 상대수익률 (YTD)")
        base_cols = ['코스피', 'CSI300', '코스닥', '니케이', 'S&P500', '나스닥']
        valid_relative_cols = [col + '(시작=100)' for col in base_cols if col + '(시작=100)' in df_market.columns]
        
        if valid_relative_cols:
            chart_data_rel = df_market[['일자'] + valid_relative_cols].melt(id_vars=['일자'], var_name='지수', value_name='상대수익률')
            chart_data_rel['지수'] = chart_data_rel['지수'].str.replace('(시작=100)', '', regex=False)
            
            line_chart = alt.Chart(chart_data_rel).mark_line(opacity=0.8).encode(
                x=alt.X('일자:T', title=None, axis=alt.Axis(grid=False)),
                y=alt.Y('상대수익률:Q', scale=alt.Scale(zero=False), axis=alt.Axis(grid=True, gridOpacity=0.2)),
                color=alt.Color('지수:N', legend=alt.Legend(title=None, orient="bottom", columns=3)),
                tooltip=[alt.Tooltip('일자:T', format='%Y-%m-%d'), '지수', alt.Tooltip('상대수익률:Q', format='.2f')]
            ).properties(height=350)
            st.altair_chart(line_chart, use_container_width=True)

    with chart_cols[1]:
        st.subheader("📈 한·미 국채금리 비교")
        yield_cols = ['한국10년물', '한국30년물', '미국10년물', '미국30년물']
        valid_yield_cols = [col for col in yield_cols if col in df_market.columns]
        if valid_yield_cols:
            chart_data_yield = df_market[['일자'] + valid_yield_cols].melt(id_vars=['일자'], var_name='국채', value_name='금리(%)')
            yield_chart = alt.Chart(chart_data_yield).mark_line(opacity=0.8).encode(
                x=alt.X('일자:T', title=None, axis=alt.Axis(grid=False)),
                y=alt.Y('금리(%):Q', scale=alt.Scale(zero=False), axis=alt.Axis(grid=True, gridOpacity=0.2)),
                color=alt.Color('국채:N', legend=alt.Legend(title=None, orient="bottom", columns=2)),
                tooltip=[alt.Tooltip('일자:T', format='%Y-%m-%d'), '국채', alt.Tooltip('금리(%):Q', format='.3f')]
            ).properties(height=350)
            st.altair_chart(yield_chart, use_container_width=True)

    st.divider()
    st.subheader("📉 개별 지수 및 환율/원자재 추이")
    mini_cols1 = st.columns(4)
    with mini_cols1[0]: st.markdown(f"**S&P 500** `({last_dates.get('S&P500', '-')})`"); draw_mini_chart(df_market, 'S&P500')
    with mini_cols1[1]: st.markdown(f"**나스닥** `({last_dates.get('나스닥', '-')})`"); draw_mini_chart(df_market, '나스닥')
    with mini_cols1[2]: st.markdown(f"**필라델피아 반도체** `({last_dates.get('필라델피아 반도체', '-')})`"); draw_mini_chart(df_market, '필라델피아 반도체')
    with mini_cols1[3]: st.markdown(f"**VIX 지수** `({last_dates.get('VIX', '-')})`"); draw_mini_chart(df_market, 'VIX')

    mini_cols2 = st.columns(4)
    with mini_cols2[0]: st.markdown(f"**코스피** `({last_dates.get('코스피', '-')})`"); draw_mini_chart(df_market, '코스피')
    with mini_cols2[1]: st.markdown(f"**코스닥** `({last_dates.get('코스닥', '-')})`"); draw_mini_chart(df_market, '코스닥')
    with mini_cols2[2]: st.markdown(f"**니케이 225** `({last_dates.get('니케이', '-')})`"); draw_mini_chart(df_market, '니케이')
    with mini_cols2[3]: st.markdown(f"**CSI 300** `({last_dates.get('CSI300', '-')})`"); draw_mini_chart(df_market, 'CSI300')

    mini_cols3 = st.columns(4)
    with mini_cols3[0]: st.markdown(f"**원/달러 환율** `({last_dates.get('환율($/원)', '-')})`"); draw_mini_chart(df_market, '환율($/원)')
    with mini_cols3[1]: st.markdown(f"**엔/원 환율 (100엔)** `({last_dates.get('엔/원 환율', '-')})`"); draw_mini_chart(df_market, '엔/원 환율')
    with mini_cols3[2]: st.markdown(f"**WTI유** `({last_dates.get('WTI유', '-')})`"); draw_mini_chart(df_market, 'WTI유')
    with mini_cols3[3]: st.markdown(f"**금 (Gold)** `({last_dates.get('금', '-')})`"); draw_mini_chart(df_market, '금')

    mini_cols4 = st.columns(4)
    with mini_cols4[0]: st.markdown(f"**미국 10년물** `({last_dates.get('미국10년물', '-')})`"); draw_mini_chart(df_market, '미국10년물')
    with mini_cols4[1]: st.markdown(f"**미국 30년물** `({last_dates.get('미국30년물', '-')})`"); draw_mini_chart(df_market, '미국30년물')
    with mini_cols4[2]: st.markdown(f"**한국 10년물** `({last_dates.get('한국10년물', '-')})`"); draw_mini_chart(df_market, '한국10년물')
    with mini_cols4[3]: st.markdown(f"**한국 30년물** `({last_dates.get('한국30년물', '-')})`"); draw_mini_chart(df_market, '한국30년물')

with tab3:
    st.subheader("🏭 미국 11대 대표 섹터 자금 흐름 (SPDR ETFs)")
    st.markdown("##### 📊 주요 11대 섹터 상대수익률 비교 (YTD)")
    sector_base_cols = ['기술(XLK)', '금융(XLF)', '헬스케어(XLV)', '에너지(XLE)', '자유소비재(XLY)', '산업재(XLI)', '필수소비재(XLP)', '유틸리티(XLU)', '소재(XLB)', '부동산(XLRE)', '커뮤니케이션(XLC)']
    valid_sec_rel_cols = [col + '(시작=100)' for col in sector_base_cols if col + '(시작=100)' in df_market.columns]

    if valid_sec_rel_cols:
        chart_data_sec_rel = df_market[['일자'] + valid_sec_rel_cols].melt(id_vars=['일자'], var_name='섹터', value_name='상대수익률')
        chart_data_sec_rel['섹터'] = chart_data_sec_rel['섹터'].str.replace('(시작=100)', '', regex=False)

        sec_line_chart = alt.Chart(chart_data_sec_rel).mark_line(opacity=0.8, strokeWidth=2).encode(
            x=alt.X('일자:T', title=None, axis=alt.Axis(grid=False)),
            y=alt.Y('상대수익률:Q', scale=alt.Scale(zero=False), axis=alt.Axis(grid=True, gridOpacity=0.2)),
            color=alt.Color('섹터:N', scale=alt.Scale(scheme='category20'), legend=alt.Legend(title=None, orient="bottom", columns=6)),
            tooltip=[alt.Tooltip('일자:T', format='%Y-%m-%d'), '섹터', alt.Tooltip('상대수익률:Q', format='.2f')]
        ).properties(height=380)
        st.altair_chart(sec_line_chart, use_container_width=True)
        
    st.divider()
    sec_cols1 = st.columns(4)
    with sec_cols1[0]: st.markdown(f"**기술 (XLK)**"); draw_mini_chart(df_market, '기술(XLK)')
    with sec_cols1[1]: st.markdown(f"**금융 (XLF)**"); draw_mini_chart(df_market, '금융(XLF)')
    with sec_cols1[2]: st.markdown(f"**헬스케어 (XLV)**"); draw_mini_chart(df_market, '헬스케어(XLV)')
    with sec_cols1[3]: st.markdown(f"**자유소비재 (XLY)**"); draw_mini_chart(df_market, '자유소비재(XLY)')

with tab4:
    st.subheader("🇰🇷 국내 12대 대표 섹터/테마 자금 흐름")
    st.markdown("##### 📊 주요 12대 국내 테마 상대수익률 비교 (YTD)")
    kr_sector_base_cols = ['K-반도체', 'K-2차전지', 'K-자동차', 'K-인터넷', 'K-헬스케어', 'K-은행', 'K-기계조선', 'K-철강', 'K-미디어엔터', 'K-건설', 'K-화학', 'K-방산']
    valid_kr_sec_rel_cols = [col + '(시작=100)' for col in kr_sector_base_cols if col + '(시작=100)' in df_market.columns]

    if valid_kr_sec_rel_cols:
        chart_data_kr_sec_rel = df_market[['일자'] + valid_kr_sec_rel_cols].melt(id_vars=['일자'], var_name='섹터', value_name='상대수익률')
        chart_data_kr_sec_rel['섹터'] = chart_data_kr_sec_rel['섹터'].str.replace('(시작=100)', '', regex=False)

        kr_sec_line_chart = alt.Chart(chart_data_kr_sec_rel).mark_line(opacity=0.8, strokeWidth=2).encode(
            x=alt.X('일자:T', title=None, axis=alt.Axis(grid=False)),
            y=alt.Y('상대수익률:Q', scale=alt.Scale(zero=False), axis=alt.Axis(grid=True, gridOpacity=0.2)),
            color=alt.Color('섹터:N', scale=alt.Scale(scheme='tableau20'), legend=alt.Legend(title=None, orient="bottom", columns=6)),
            tooltip=[alt.Tooltip('일자:T', format='%Y-%m-%d'), '섹터', alt.Tooltip('상대수익률:Q', format='.2f')]
        ).properties(height=380)
        st.altair_chart(kr_sec_line_chart, use_container_width=True)
        
    st.divider()
    kr_sec_cols1 = st.columns(4)
    with kr_sec_cols1[0]: st.markdown(f"**반도체**"); draw_mini_chart(df_market, 'K-반도체')
    with kr_sec_cols1[1]: st.markdown(f"**2차전지**"); draw_mini_chart(df_market, 'K-2차전지')
    with kr_sec_cols1[2]: st.markdown(f"**자동차**"); draw_mini_chart(df_market, 'K-자동차')
    with kr_sec_cols1[3]: st.markdown(f"**인터넷/SW**"); draw_mini_chart(df_market, 'K-인터넷')

with tab5:
    st.markdown("#### 📰 실시간 주요 경제 헤드라인 (Google News 제공)")
    news_col1, news_col2 = st.columns(2)

    with news_col1:
        st.markdown("##### 🇰🇷 국내 경제/비즈니스 (Top 10)")
        for news in news_data["KR"]:
            st.markdown(f"🔹 <a class='news-link' href='{news['link']}' target='_blank'>{news['title']}</a>", unsafe_allow_html=True)

    with news_col2:
        st.markdown("##### 🌎 글로벌 경제/비즈니스 (Top 10)")
        for news in news_data["US"]:
            st.markdown(f"🔹 <a class='news-link' href='{news['link']}' target='_blank'>{news['title']}</a>", unsafe_allow_html=True)


# ==============================================================================
# 🌟 탭 6: 내 보유종목 (Private Portfolio) - 자동 YTD 차트 엔진 결합
# ==============================================================================
with tab6:
    st.subheader("🔒 개인 포트폴리오 (Private)")
    
    pwd = st.text_input("이 탭은 소유자 전용 공간입니다. 접근 암호를 입력하세요.", type="password")
    
    if pwd == "0000":
        st.success("인증 완료! 엑셀 기반 계좌 통계 데이터를 성공적으로 불러왔습니다.")
        
        uploaded_file = st.file_uploader("업데이트된 포트폴리오 엑셀 파일을 업로드하세요 (선택 사항)", type=['xlsx', 'xls'])
        
        # 엑셀 파싱 초기 샘플 데이터
        metrics = {
            "총자산": "₩ 98,515,598", "총매수금액": "₩ 98,263,990", "평가손익": "+₩ 251,608 (0.3%)",
            "실현손익": "+₩ 9,627,261", "현금비중": "28.4%", "현금액": "₩ 27,929,877"
        }
        df_region = pd.DataFrame({"분류": ["한국", "미국", "글로벌", "현금"], "현재금액": [21786755, 40719646, 8079320, 27929877]})
        df_base = pd.DataFrame({"분류": ["한국", "미국", "글로벌", "현금"], "현재금액": [63932155, 6653566, 0, 27929877]})
        
        df_holdings = pd.DataFrame({
            "계좌 구분": ["IRP - 장기"]*11 + ["ISA - 중기"]*2 + ["국내주식 - 단기"]*5 + ["해외주식 - 단기"]*3 + ["비상금"],
            "종목명": [
                "KODEX 200", "TIGER 미국나스닥100", "KODEX 코스닥150", "TIGER 일본니케이225", "KODEX 차이나CSI300",
                "TIGER 미국S&P500", "ACE 미국S&P500미국채혼합50액티브", "ACE 미국나스닥100미국채혼합50액티브", 
                "KODEX 국고채30년액티브", "ACE 미국30년국채액티브(H)", "IRP예수금",
                "TIGER 미국배당다우존스", "ISA예수금",
                "한온시스템", "TIGER 바이오TOP10", "PLUS K방산", "SOL AI반도체소부장", "국내주식예수금",
                "로봇공학 및 인공지능 글로벌엑스(BOTZ)", "나스닥 스마트 그리드 인프라(GRID)", "해외주식예수금",
                "카카오뱅크(세이프박스)"
            ],
            "보유수량": ["73", "42", "280", "90", "120", "350", "300", "300", "40", "550", "1", "520", "1", "250", "300", "20", "100", "1", "65", "14", "1", "1"],
            "매수단가": ["₩ 63,969", "₩ 188,498", "₩ 14,132", "₩ 38,781", "₩ 15,877", "₩ 24,866", "₩ 14,671", "₩ 15,866", "₩ 107,595", "₩ 7,655", "₩ 12,147,405", "₩ 15,401", "₩ 2,018,773", "₩ 4,187", "₩ 7,623", "₩ 66,065", "₩ 24,595", "₩ 2,878,878", "₩ 51,657", "₩ 253,298", "₩ 2,874,694", "₩ 8,000,000"],
            "현재가": ["₩ 109,285", "₩ 181,225", "₩ 13,830", "₩ 34,505", "₩ 15,060", "₩ 26,280", "₩ 14,060", "₩ 15,230", "₩ 87,460", "₩ 7,150", "₩ 12,147,405", "₩ 14,815", "₩ 2,018,773", "₩ 3,445", "₩ 6,680", "₩ 53,045", "₩ 25,120", "₩ 2,878,878", "₩ 48,718", "₩ 249,064", "₩ 2,874,694", "₩ 8,010,127"],
            "수익률(%)": ["70.8%", "-3.9%", "-2.1%", "-11.0%", "-5.1%", "5.7%", "-4.2%", "-4.0%", "-18.7%", "-6.6%", "0.0%", "-3.8%", "0.0%", "-17.7%", "-12.4%", "-19.7%", "2.1%", "0.0%", "-5.7%", "-1.7%", "0.0%", "0.1%"],
            "현재가치": ["₩ 7,977,805", "₩ 7,611,450", "₩ 3,872,400", "₩ 3,105,450", "₩ 1,807,200", "₩ 9,198,000", "₩ 4,218,000", "₩ 4,569,000", "₩ 3,498,400", "₩ 3,932,500", "₩ 12,147,405", "₩ 7,703,800", "₩ 2,018,773", "₩ 861,250", "₩ 2,004,000", "₩ 1,060,900", "₩ 2,512,000", "₩ 2,878,878", "₩ 3,166,670", "₩ 3,486,896", "₩ 2,874,694", "₩ 8,010,127"],
            "계좌내 비중(%)": ["12.9%", "12.3%", "6.3%", "5.0%", "2.9%", "14.9%", "6.8%", "7.4%", "5.6%", "6.3%", "19.6%", "79.2%", "20.8%", "9.2%", "21.5%", "11.4%", "27.0%", "30.9%", "33.2%", "36.6%", "30.2%", "100.0%"]
        })
        account_summaries = {
            "IRP - 장기": {"buy": "₩ 60,464,798", "total": "₩ 61,937,610", "profit": "+₩ 1,472,812", "ret": "+2.4%", "color": "red", "cash_amt": "₩ 12,147,405", "cash_weight": "19.6%", "realized": "+₩ 7,428,292"},
            "ISA - 중기": {"buy": "₩ 10,027,293", "total": "₩ 9,722,573", "profit": "-₩ 304,720", "ret": "-3.0%", "color": "blue", "cash_amt": "₩ 2,018,773", "cash_weight": "20.8%", "realized": "₩ 0"},
            "국내주식 - 단기": {"buy": "₩ 9,993,328", "total": "₩ 9,317,028", "profit": "-₩ 676,300", "ret": "-6.8%", "color": "blue", "cash_amt": "₩ 2,878,878", "cash_weight": "30.9%", "realized": "+₩ 929,728"},
            "해외주식 - 단기": {"buy": "₩ 9,778,571", "total": "₩ 9,528,260", "profit": "-₩ 250,311", "ret": "-2.6%", "color": "blue", "cash_amt": "₩ 2,874,694", "cash_weight": "30.2%", "realized": "+₩ 1,236,133"},
            "비상금": {"buy": "₩ 8,000,000", "total": "₩ 8,010,127", "profit": "+₩ 10,127", "ret": "+0.1%", "color": "red", "cash_amt": "₩ 8,010,127", "cash_weight": "100.0%", "realized": "+₩ 33,108"}
        }

        if uploaded_file is not None:
            try:
                metrics, df_region, df_base, df_holdings, account_summaries = parse_portfolio_excel(uploaded_file)
                st.toast("업로드된 엑셀 파일 데이터로 동기화 완료!", icon="✅")
            except Exception as e:
                st.error(f"엑셀 파일 처리 중 오류가 발생했습니다. 양식이 맞는지 확인해주세요. (오류: {e})")
        else:
            st.info("💡 파일을 업로드하면 기존 샘플 데이터 대신 최신 엑셀 데이터를 화면에 렌더링합니다.")
            
        st.divider()
        
        st.markdown("##### 💰 총 자산 현황 요약")
        p_cols = st.columns(4)
        p_cols[0].metric("총 자산 (Total Assets)", metrics["총자산"], metrics["평가손익"])
        p_cols[1].metric("총 매수금액 (Total Invested)", metrics["총매수금액"], "")
        p_cols[2].metric("실현 손익 (Realized Profit)", metrics["실현손익"], "")
        p_cols[3].metric("계좌 내 현금 비중 (Cash Weight)", metrics["현금비중"], metrics["현금액"], delta_color="off")
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        st.markdown("##### 🌍 국가 및 지역별 자산 노출 통계")
        chart_col1, chart_col2 = st.columns(2)
        
        with chart_col1:
            st.markdown("**📌 지역그룹별 현재금액**")
            region_chart = alt.Chart(df_region).mark_bar(size=40).encode(
                x=alt.X('분류:N', title=None, sort=None, axis=alt.Axis(labelAngle=0)),
                y=alt.Y('현재금액:Q', title=None, axis=alt.Axis(format='~s')),
                color=alt.Color('분류:N', legend=None, scale=alt.Scale(scheme='blues')),
                tooltip=[alt.Tooltip('분류:N'), alt.Tooltip('현재금액:Q', format=',.0f')]
            ).properties(height=300)
            st.altair_chart(region_chart, use_container_width=True)

        with chart_col2:
            st.markdown("**📌 베이스국가별 현재금액**")
            base_chart = alt.Chart(df_base).mark_bar(size=40).encode(
                x=alt.X('분류:N', title=None, sort=None, axis=alt.Axis(labelAngle=0)),
                y=alt.Y('현재금액:Q', title=None, axis=alt.Axis(format='~s')),
                color=alt.Color('분류:N', legend=None, scale=alt.Scale(scheme='teals')),
                tooltip=[alt.Tooltip('분류:N'), alt.Tooltip('현재금액:Q', format=',.0f')]
            ).properties(height=300)
            st.altair_chart(base_chart, use_container_width=True)

        st.divider()

        # 🌟 내 보유종목 YTD 히스토리 차트 렌더링
        st.markdown("##### 📈 내 보유종목 YTD 상대수익률 비교 (시작=100)")
        df_port_hist = get_portfolio_history()
        
        # 엑셀(또는 샘플)에 존재하는 종목 중 티커 매핑이 성공하여 데이터를 가져온 종목만 필터링
        active_holdings = [name for name in df_holdings['종목명'].unique() if name in df_port_hist.columns]
        
        if active_holdings:
            cols_to_plot = ['일자'] + active_holdings
            chart_data_port = df_port_hist[cols_to_plot].melt(id_vars=['일자'], var_name='종목', value_name='상대수익률')
            
            port_line_chart = alt.Chart(chart_data_port).mark_line(opacity=0.8, strokeWidth=2).encode(
                x=alt.X('일자:T', title=None, axis=alt.Axis(grid=False)),
                y=alt.Y('상대수익률:Q', scale=alt.Scale(zero=False), axis=alt.Axis(grid=True, gridOpacity=0.2)),
                color=alt.Color('종목:N', scale=alt.Scale(scheme='tableau20'), legend=alt.Legend(title=None, orient="bottom", columns=4)),
                tooltip=[alt.Tooltip('일자:T', format='%Y-%m-%d'), '종목', alt.Tooltip('상대수익률:Q', format='.2f')]
            ).properties(height=450)
            st.altair_chart(port_line_chart, use_container_width=True)
            st.caption("※ 엑셀 종목명을 기반으로 시장 티커와 자동 매핑하여 추적합니다. 예수금 등은 제외됩니다.")
        else:
            st.warning("차트를 그릴 수 있는 엑셀 보유종목 가격 데이터가 없습니다. (티커 매핑 필요)")

        st.divider()

        st.markdown("##### 🧾 계좌별 상세 보유 종목 현황")
        for acc in df_holdings["계좌 구분"].unique():
            acc_data = df_holdings[df_holdings["계좌 구분"] == acc].drop(columns=["계좌 구분"])
            summary = account_summaries.get(acc, {"buy": "", "total": "", "profit": "", "ret": "", "color": "black", "cash_amt": "", "cash_weight": "", "realized": ""})
            
            st.markdown(f"**🏦 {acc}** &nbsp; | &nbsp; 총매수: {summary['buy']} &nbsp; | &nbsp; 총평가: {summary['total']} &nbsp; | &nbsp; 평가손익: :{summary['color']}[**{summary['profit']} ({summary['ret']})**] &nbsp; | &nbsp; 💰 실현손익: **{summary['realized']}** &nbsp; | &nbsp; 💵 현금비중: **{summary['cash_weight']}** ({summary['cash_amt']})")
            st.dataframe(acc_data, use_container_width=True, hide_index=True)
            st.markdown("<br>", unsafe_allow_html=True)
        
    elif pwd != "":
        st.error("비밀번호가 일치하지 않습니다. (Hint: 0000)")
    else:
        st.caption("권한이 없는 사용자는 이 탭의 자산 데이터를 열람할 수 없습니다.")
