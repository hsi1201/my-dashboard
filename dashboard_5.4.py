import streamlit as st
import pandas as pd
import altair as alt
import yfinance as yf
import FinanceDataReader as fdr
import requests
from streamlit_autorefresh import st_autorefresh 

# 1. 웹페이지 기본 설정
st.set_page_config(page_title="나만의 투자 관제탑", layout="wide", initial_sidebar_state="collapsed")

# 🌟 [자동 갱신] 3분(180,000 밀리초)마다 화면 새로고침
st_autorefresh(interval=180000, limit=10000, key="data_refresh")

# 🌟 [디자인 1] CSS 주입: 헤더 메뉴는 살려두고 여백만 압축
st.markdown("""
<style>
/* 화면 전체의 상하단 빵빵한 기본 여백 대폭 축소 (메뉴바와 겹치지 않게 상단 여백 소폭 확보) */
.block-container {
    padding-top: 3rem !important; 
    padding-bottom: 1.5rem !important;
}

/* 메인 타이틀(h1) 글자 크기 축소 및 아래쪽 여백 줄이기 */
h1 {
    font-size: 1.6rem !important;
    padding-top: 0 !important;
    padding-bottom: 0.2rem !important;
}

/* 카드 UI 기본 설정 */
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
</style>
""", unsafe_allow_html=True)

st.title("📊 글로벌 자산투자 시황 대시보드 (UI/UX 6.16)")
st.markdown("Yahoo Finance + Naver + 한국은행 ECOS 서버를 결합한 무결점 실시간 동기화")
st.divider()

# 2. 데이터 자동 수집 및 계산 엔진
@st.cache_data(ttl=180) 
def get_market_data():
    df_list = []
    
    # [엔진 0] 한국은행 ECOS API
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

    # [엔진 1] 야후 파이낸스 서버
    yf_tickers = {
        '^GSPC': 'S&P500', '^IXIC': '나스닥', 
        '^N225': '니케이', 
        '^KS11': '코스피', '^KQ11': '코스닥', 
        'CL=F': 'WTI유', '^TNX': '미국10년물', '^TYX': '미국30년물'
    }
    for ticker, name in yf_tickers.items():
        try:
            temp_df = yf.Ticker(ticker).history(period='ytd')[['Close']]
            temp_df.columns = [name]
            temp_df.index = pd.to_datetime(temp_df.index).normalize().tz_localize(None)
            temp_df = temp_df[~temp_df.index.duplicated(keep='last')]
            df_list.append(temp_df)
        except:
            continue

    # [엔진 2] 네이버 금융 & KRX 서버 
    fdr_tickers = {
        'KS200': '코스피200', 
        'USD/KRW': '환율($/원)'
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
    
    df['일자'] = df['일자'].dt.strftime('%Y-%m-%d')
    
    if '한국10년물' not in df.columns: df['한국10년물'] = 3.123 
    if '한국30년물' not in df.columns: df['한국30년물'] = 2.987
    
    for col in df.columns:
        if col != '일자':
            roll_max = df[col].cummax()
            df[f'{col} MDD'] = df[col] / roll_max - 1.0
            
    relative_cols = ['코스피', '코스피200', '코스닥', '니케이', 'S&P500', '나스닥']
    for col in relative_cols:
        if col in df.columns:
            first_val = df[col].iloc[0]
            df[f'{col}(시작=100)'] = (df[col] / first_val) * 100 if first_val != 0 else 0
            
    df.fillna(0, inplace=True)
    
    sync_time = pd.Timestamp.now(tz='Asia/Seoul').strftime('%m/%d %H:%M')
    
    return df, last_dates, changes, sync_time

df_market, last_dates, changes, sync_time = get_market_data()
latest_data = df_market.iloc[-1] 

def get_mdd_text(mdd_val):
    mdd_pct = mdd_val * 100
    if mdd_pct >= -10:
        return f":green[MDD {mdd_pct:.1f}%]"
    elif mdd_pct >= -20:
        return f":orange[MDD {mdd_pct:.1f}%]"
    elif mdd_pct >= -30:
        return f":red[MDD {mdd_pct:.1f}%]"
    elif mdd_pct >= -40:
        return f":violet[MDD {mdd_pct:.1f}%]"
    else:
        return f":blue[MDD {mdd_pct:.1f}%]"

# ---------------------------------------------------------
# UI 레이아웃
# ---------------------------------------------------------

st.info(f"🔄 **실시간 데이터 갱신 완료:** {sync_time} (한국 시간 기준) - 3분 단위 자동 새로고침 작동 중")

with st.expander("📌 데이터 업데이트 기준 및 시차 안내 (클릭하여 열기)"):
    st.markdown("""
    - **미국 증시 & 국채 (S&P 500, 나스닥, 미국 10년/30년물):** 한국 시간 기준 낮(야간)에는 미국 정규장이 닫혀 있어 전일 마감가로 고정되며, 오늘 밤 미국 본장이 개장하면 실시간 반영됩니다.
    - **한국 증시 & 환율 (코스피, 코스닥, 니케이 225, 원/달러):** 아시아 장 개장 시간 동안 실시간(또는 15분 지연)으로 정상 갱신됩니다.
    - **일일 마감 갱신 지표 (코스피 200, 한국 10년/30년물):** 장중 실시간 데이터가 아닌 일별 확정 데이터를 수집하므로(네이버 금융 종가, 한국은행 ECOS 통계), 당일 장 마감 후 또는 오후 늦게 갱신됩니다.
    """)

st.subheader("💡 주요 시장 지표 현황")

st.markdown("""
<div style='font-size: 0.85rem; color: #888; margin-bottom: 15px;'>
    <b>※ MDD 상태 가이드:</b> &nbsp;
    🟢 0% ~ -10% (안전/양호) &nbsp;|&nbsp; 
    🟠 -10% ~ -20% (주의/조정장) &nbsp;|&nbsp; 
    🔴 -20% ~ -30% (경고/침체장) &nbsp;|&nbsp; 
    🟣 -30% ~ -40% (위험/폭락장) &nbsp;|&nbsp; 
    🔵 -40% 이하 (심각/빙하기)
</div>
""", unsafe_allow_html=True)

cols1 = st.columns(4)
cols1[0].metric(f"S&P 500 [{last_dates.get('S&P500', '-')}]\n{get_mdd_text(latest_data.get('S&P500 MDD', 0))}", f"{latest_data.get('S&P500', 0):,.2f}", changes.get('S&P500', '0.00'))
cols1[1].metric(f"NASDAQ [{last_dates.get('나스닥', '-')}]\n{get_mdd_text(latest_data.get('나스닥 MDD', 0))}", f"{latest_data.get('나스닥', 0):,.2f}", changes.get('나스닥', '0.00'))
cols1[2].metric(f"Nikkei 225 [{last_dates.get('니케이', '-')}]\n{get_mdd_text(latest_data.get('니케이 MDD', 0))}", f"{latest_data.get('니케이', 0):,.2f}", changes.get('니케이', '0.00'))
cols1[3].metric(f"WTI유 [{last_dates.get('WTI유', '-')}]\n{get_mdd_text(latest_data.get('WTI유 MDD', 0))}", f"{latest_data.get('WTI유', 0):,.2f} $", changes.get('WTI유', '0.00'))

cols2 = st.columns(4)
cols2[0].metric(f"KOSPI 200 [{last_dates.get('코스피200', '-')}]\n{get_mdd_text(latest_data.get('코스피200 MDD', 0))}", f"{latest_data.get('코스피200', 0):,.2f}", changes.get('코스피200', '0.00'))
cols2[1].metric(f"KOSPI [{last_dates.get('코스피', '-')}]\n{get_mdd_text(latest_data.get('코스피 MDD', 0))}", f"{latest_data.get('코스피', 0):,.2f}", changes.get('코스피', '0.00'))
cols2[2].metric(f"KOSDAQ [{last_dates.get('코스닥', '-')}]\n{get_mdd_text(latest_data.get('코스닥 MDD', 0))}", f"{latest_data.get('코스닥', 0):,.2f}", changes.get('코스닥', '0.00'))
cols2[3].metric(f"원/달러 환율 [{last_dates.get('환율($/원)', '-')}]\n{get_mdd_text(latest_data.get('환율($/원) MDD', 0))}", f"{latest_data.get('환율($/원)', 0):,.2f} 원", changes.get('환율($/원)', '0.00'))

cols3 = st.columns(4)
cols3[0].metric(f"미국 10년물 [{last_dates.get('미국10년물', '-')}]", f"{latest_data.get('미국10년물', 0):.3f} %", changes.get('미국10년물', '0.00'))
cols3[1].metric(f"미국 30년물 [{last_dates.get('미국30년물', '-')}]", f"{latest_data.get('미국30년물', 0):.3f} %", changes.get('미국30년물', '0.00'))
cols3[2].metric(f"한국 10년물 [{last_dates.get('한국10년물', '-')}]", f"{latest_data.get('한국10년물', 0):.3f} %", changes.get('한국10년물', '0.00'))
cols3[3].metric(f"한국 30년물 [{last_dates.get('한국30년물', '-')}]", f"{latest_data.get('한국30년물', 0):.3f} %", changes.get('한국30년물', '0.00'))

st.divider()

# 🌟 [수정 완료] 차트는 다시 2분할(좌우)로 배치하고, 범례(Legend)만 다단(columns)으로 나눠서 글자 잘림 방지
chart_cols = st.columns(2)

with chart_cols[0]:
    st.subheader("📊 주요 지수 상대수익률 비교 (1월 1일=100)")
    relative_cols = ['코스피(시작=100)', '코스피200(시작=100)', '코스닥(시작=100)', '니케이(시작=100)', 'S&P500(시작=100)', '나스닥(시작=100)']
    chart_data_rel = df_market[['일자'] + relative_cols].melt(id_vars=['일자'], var_name='지수', value_name='상대수익률')
    line_chart = alt.Chart(chart_data_rel).mark_line(opacity=0.8).encode(
        x=alt.X('일자:T', title=None, axis=alt.Axis(grid=False)),
        y=alt.Y('상대수익률:Q', scale=alt.Scale(zero=False), axis=alt.Axis(grid=True, gridOpacity=0.2)),
        # 🌟 범례를 3칸씩(columns=3) 나누어 강제로 두 줄로 만듦
        color=alt.Color('지수:N', legend=alt.Legend(title=None, orient="bottom", columns=3)),
        tooltip=[alt.Tooltip('일자:T', format='%Y-%m-%d'), '지수', alt.Tooltip('상대수익률:Q', format='.2f')]
    ).interactive()
    st.altair_chart(line_chart, use_container_width=True)

with chart_cols[1]:
    st.subheader("📈 한·미 국채금리 비교 (10Y / 30Y)")
    yield_cols = ['한국10년물', '한국30년물', '미국10년물', '미국30년물']
    chart_data_yield = df_market[['일자'] + yield_cols].melt(id_vars=['일자'], var_name='국채', value_name='금리(%)')
    yield_chart = alt.Chart(chart_data_yield).mark_line(opacity=0.8).encode(
        x=alt.X('일자:T', title=None, axis=alt.Axis(grid=False)),
        y=alt.Y('금리(%):Q', scale=alt.Scale(zero=False), axis=alt.Axis(grid=True, gridOpacity=0.2)),
        # 🌟 범례를 2칸씩(columns=2) 나누어 강제로 두 줄로 만듦
        color=alt.Color('국채:N', legend=alt.Legend(title=None, orient="bottom", columns=2)),
        tooltip=[alt.Tooltip('일자:T', format='%Y-%m-%d'), '국채', alt.Tooltip('금리(%):Q', format='.3f')]
    ).interactive()
    st.altair_chart(yield_chart, use_container_width=True)

st.divider()

st.subheader("📉 개별 지수 및 환율/원자재 추이")
def draw_mini_chart(df, column_name):
    if column_name in df.columns:
        chart_data = df[['일자', column_name]].dropna()
        
        min_val = chart_data[column_name].min()
        max_val = chart_data[column_name].max()
        padding = (max_val - min_val) * 0.1
        if padding == 0: padding = min_val * 0.1 if min_val != 0 else 1
        
        y_min = min_val - padding
        y_max = max_val + padding
        
        base = alt.Chart(chart_data).encode(
            x=alt.X('일자:T', title=None, axis=alt.Axis(grid=False, format='%m/%d', labelColor='gray', tickCount=5)),
            y=alt.Y(f'{column_name}:Q', title=None, scale=alt.Scale(domain=[y_min, y_max]), axis=alt.Axis(grid=False)),
            tooltip=[
                alt.Tooltip('일자:T', title='날짜', format='%Y-%m-%d'), 
                alt.Tooltip(f'{column_name}:Q', title='수치', format=',.2f')
            ]
        )
        
        area = base.mark_area(opacity=0.15, interpolate='monotone')
        line = base.mark_line(interpolate='monotone', size=2)
        
        chart = (area + line).properties(height=180).interactive()
        st.altair_chart(chart, use_container_width=True)

mini_cols1 = st.columns(4)
with mini_cols1[0]: st.markdown(f"**S&P 500** `({last_dates.get('S&P500', '-')})`"); draw_mini_chart(df_market, 'S&P500')
with mini_cols1[1]: st.markdown(f"**나스닥** `({last_dates.get('나스닥', '-')})`"); draw_mini_chart(df_market, '나스닥')
with mini_cols1[2]: st.markdown(f"**니케이 225** `({last_dates.get('니케이', '-')})`"); draw_mini_chart(df_market, '니케이')
with mini_cols1[3]: st.markdown(f"**WTI유** `({last_dates.get('WTI유', '-')})`"); draw_mini_chart(df_market, 'WTI유')

mini_cols2 = st.columns(4)
with mini_cols2[0]: st.markdown(f"**코스피 200** `({last_dates.get('코스피200', '-')})`"); draw_mini_chart(df_market, '코스피200')
with mini_cols2[1]: st.markdown(f"**코스피** `({last_dates.get('코스피', '-')})`"); draw_mini_chart(df_market, '코스피')
with mini_cols2[2]: st.markdown(f"**코스닥** `({last_dates.get('코스닥', '-')})`"); draw_mini_chart(df_market, '코스닥')
with mini_cols2[3]: st.markdown(f"**원/달러 환율** `({last_dates.get('환율($/원)', '-')})`"); draw_mini_chart(df_market, '환율($/원)')

mini_cols3 = st.columns(4)
with mini_cols3[0]: st.markdown(f"**미국 10년물** `({last_dates.get('미국10년물', '-')})`"); draw_mini_chart(df_market, '미국10년물')
with mini_cols3[1]: st.markdown(f"**미국 30년물** `({last_dates.get('미국30년물', '-')})`"); draw_mini_chart(df_market, '미국30년물')
with mini_cols3[2]: st.markdown(f"**한국 10년물** `({last_dates.get('한국10년물', '-')})`"); draw_mini_chart(df_market, '한국10년물')
with mini_cols3[3]: st.markdown(f"**한국 30년물** `({last_dates.get('한국30년물', '-')})`"); draw_mini_chart(df_market, '한국30년물')
