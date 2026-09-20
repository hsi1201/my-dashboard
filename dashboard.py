import streamlit as st
import pandas as pd
import altair as alt
import yfinance as yf
import FinanceDataReader as fdr
import requests
import xml.etree.ElementTree as ET
import hashlib
import re
import urllib.parse
import urllib3
import os
from streamlit_autorefresh import st_autorefresh 

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(page_title="글로벌 마켓 대시보드", layout="wide", initial_sidebar_state="collapsed")
st_autorefresh(interval=1800000, limit=10000, key="data_refresh")

st.markdown("""
<style>
.block-container { padding-top: 2rem !important; padding-bottom: 1.5rem !important; }
[data-testid="stMetric"] { background-color: rgba(130, 130, 130, 0.05); border: 1px solid rgba(130, 130, 130, 0.2); border-radius: 12px; padding: 12px; box-shadow: 2px 4px 10px rgba(0, 0, 0, 0.05); transition: transform 0.2s; }
[data-testid="stMetric"]:hover { transform: translateY(-5px); box-shadow: 2px 8px 15px rgba(0, 0, 0, 0.1); }
[data-testid="stMetricLabel"], [data-testid="stMetricLabel"] * { white-space: pre-line !important; word-break: keep-all !important; line-height: 1.4 !important; font-size: 0.8rem !important; }
[data-testid="stMetricValue"], [data-testid="stMetricValue"] > div { font-size: 1.4rem !important; letter-spacing: -0.5px !important; }
@media (max-width: 768px) { [data-testid="stMetricValue"], [data-testid="stMetricValue"] > div { font-size: 1.15rem !important; } }
.news-link { text-decoration: none; color: #1E88E5; font-size: 0.95rem; line-height: 1.6; margin-bottom: 8px; display: inline-block; }
.news-link:hover { text-decoration: underline; }
.etf-box { background-color: rgba(130, 130, 130, 0.08); border-left: 4px solid #1E88E5; padding: 12px 15px; margin-top: -10px; margin-bottom: 15px; border-radius: 4px; font-size: 0.9rem; line-height: 1.6; }
.stTabs [data-baseweb="tab-list"] button { font-size: 1.1rem; padding-top: 1rem; padding-bottom: 1rem; }
</style>
""", unsafe_allow_html=True)

st.markdown("""<div style="margin-top:-15px; margin-bottom:10px;"><h2 style="margin-bottom:0px; padding-bottom:5px; font-size:1.8rem;">📊 글로벌 마켓 대시보드 (v1.0.49 최적화 오류 수정본)</h2></div>""", unsafe_allow_html=True)

# ---------------------------------------------------------
# 🌟 [스마트 캘린더] 일정 데이터
# ---------------------------------------------------------
MACRO_EVENTS = {
    "2026-09-18": "일본 BOJ 기준금리 결정 / 미국 네 마녀의 날",
    "2026-09-24": "파월 연준 의장 연설 / 미 신규 실업수당 청구",
    "2026-09-25": "🚨 미국 8월 개인소비지출(PCE) 물가지수",
    "2026-10-02": "미국 9월 고용동향보고서",
    "2026-10-08": "FOMC 의사록 공개",
    "2026-10-10": "한국은행 금융통화위원회",
    "2026-10-15": "🚨 미국 9월 소비자물가지수(CPI)",
    "2026-10-30": "미국 3분기 GDP (속보치)",
    "2026-10-31": "미국 9월 개인소비지출(PCE)",
    "2026-11-03": "🇺🇸 미국 중간선거 (Midterm Election)",
    "2026-11-05": "🚨 미국 FOMC 기준금리 결정",
    "2026-11-12": "미국 10월 소비자물가지수(CPI)",
    "2026-11-26": "미국 추수감사절 (증시 휴장)",
    "2026-12-04": "미국 11월 고용동향보고서",
    "2026-12-10": "미국 11월 소비자물가지수(CPI)",
    "2026-12-18": "🚨 미국 FOMC 기준금리 결정 (점도표)"
}

# ---------------------------------------------------------
# 🌟 [데이터 파서] 엑셀 처리
# ---------------------------------------------------------
def clean_currency_str(val):
    if pd.isna(val) or val is None: return "0"
    cleaned = str(val).replace('+', '').replace('₩', '').replace('\\', '').replace(',', '').strip()
    return cleaned if cleaned else "0"

def parse_portfolio_excel(file):
    df_stats = pd.read_excel(file, sheet_name='국가통계', engine='openpyxl')
    df_inv = pd.read_excel(file, sheet_name='투자현황', skiprows=0, engine='openpyxl')
    total_assets = pd.to_numeric(df_stats.iloc[2, 1], errors='coerce')
    valid_inv = df_inv[df_inv[df_inv.columns[0]] != '합계'].copy()
    valid_inv['현재가격'] = pd.to_numeric(valid_inv['현재가격'], errors='coerce').fillna(0)
    
    df_region = valid_inv.groupby('지역그룹')['현재가격'].sum().reset_index().rename(columns={'지역그룹':'분류', '현재가격':'현재금액'})
    df_base = valid_inv.groupby('베이스국가')['현재가격'].sum().reset_index().rename(columns={'베이스국가':'분류', '현재가격':'현재금액'})
    df_asset = valid_inv.groupby('자산군')['현재가격'].sum().reset_index().rename(columns={'자산군':'분류', '현재가격':'현재금액'})
    
    first_col = df_inv.columns[0]
    current_account = "IRP - 장기"
    val_header_clean = str(first_col).replace(" ", "").upper()
    if val_header_clean == 'ISA-중기': current_account = 'ISA - 중기'
    elif val_header_clean == '국내주식-단기': current_account = '국내주식 - 단기'
    elif val_header_clean == '해외주식-단기': current_account = '해외주식 - 단기'
    elif val_header_clean == '비상금': current_account = '비상금'
        
    rows_list, account_summaries = [], {}
    
    for idx, row in df_inv.iterrows():
        val = str(row[first_col]).strip()
        if pd.isna(row[first_col]) or val == 'nan' or val == '현재 날짜 및 시간' or re.match(r'^\d{4}-\d{2}-\d{2}', val): continue
            
        val_clean = val.replace(" ", "").upper()
        if val_clean in ['IRP-장기', 'ISA-중기', '국내주식-단기', '해외주식-단기', '비상금', '가상화폐', '부동산']:
            current_account = val_clean.replace("-", " - ") if "-" in val_clean else val_clean
            continue
            
        if val_clean == '합계':
            b, t = pd.to_numeric(row.get('매수가격', 0), errors='coerce'), pd.to_numeric(row.get('현재가격', 0), errors='coerce')
            p, r, rlz = t - b if pd.notna(b) and pd.notna(t) else 0, pd.to_numeric(row.get('수익률', 0), errors='coerce'), pd.to_numeric(row.get('실현손익', 0), errors='coerce')
            cash_amt = sum([r['현재가치_num'] for r in rows_list if r['계좌 구분'] == current_account and any(k in r['종목명'] for k in ['예수금', '세이프박스', '예금', '외화', 'CMA', '현금'])])
            
            account_summaries[current_account] = {
                "buy": f"₩ {b:,.0f}" if pd.notna(b) else "₩ 0", "total": f"₩ {t:,.0f}" if pd.notna(t) else "₩ 0",
                "profit": f"{'+' if p > 0 else ''}₩ {p:,.0f}", "ret": f"{r*100:+.2f}%", "color": "red" if r >= 0 else "blue",
                "realized": f"{'+' if rlz > 0 else ''}₩ {rlz:,.0f}", "cash_amt": f"₩ {cash_amt:,.0f}", "cash_weight": f"{(cash_amt/t*100) if t>0 else 0:.1f}%"
            }
            continue
            
        qty, bp, cp = pd.to_numeric(row.get('수량', 0), errors='coerce'), pd.to_numeric(row.get('매수가', 0), errors='coerce'), pd.to_numeric(row.get('현재가', 0), errors='coerce')
        cv, pl, w = pd.to_numeric(row.get('현재가격', 0), errors='coerce'), pd.to_numeric(row.get('손익', 0), errors='coerce'), pd.to_numeric(row.get('현재비중', 0), errors='coerce')
        
        rows_list.append({
            '계좌 구분': current_account, '종목명': val, '보유수량': f"{qty:,.0f}" if pd.notna(qty) and qty > 0 else "-",
            '매수단가_num': bp if pd.notna(bp) else 0, '현재가_num': cp if pd.notna(cp) else 0,
            '매수단가': f"₩ {bp:,.0f}" if pd.notna(bp) and bp > 0 else "-", '현재가': f"₩ {cp:,.0f}" if pd.notna(cp) and cp > 0 else "-",
            '현재가치': f"₩ {cv:,.0f}" if pd.notna(cv) else "₩ 0", '평가손익': f"{'+' if pl > 0 else '-'}₩ {abs(pl):,.0f}" if pd.notna(pl) and pl != 0 else "₩ 0", 
            '수익률(%)': f"{pd.to_numeric(row.get('수익률',0), errors='coerce')*100:+.2f}%", '현재가치_num': cv if pd.notna(cv) else 0, '계좌내 비중(%)': f"{w*100:.1f}%" if pd.notna(w) else "0.0%"
        })
        
    df_h = pd.DataFrame(rows_list)
    if not df_h.empty: df_h.drop(columns=['현재가치_num'], inplace=True)
        
    t_rlz = sum([float(clean_currency_str(account_summaries[a].get('realized', '0'))) for a in account_summaries])
    t_inv = sum([float(clean_currency_str(account_summaries[a].get('buy', '0'))) for a in account_summaries])
    t_csh = sum([float(clean_currency_str(account_summaries[a].get('cash_amt', '0'))) for a in account_summaries])
    t_prof = total_assets - t_inv
    
    metrics = {
        "총자산": f"₩ {total_assets:,.0f}", "총매수금액": f"₩ {t_inv:,.0f}", "실현손익": f"{'+' if t_rlz > 0 else ''}₩ {t_rlz:,.0f}",
        "평가손익": f"{'+' if t_prof > 0 else ''}₩ {t_prof:,.0f} ({(t_prof/t_inv*100) if t_inv>0 else 0:+.1f}%)",
        "현금비중": f"{(t_csh/total_assets*100) if total_assets>0 else 0:.1f}%", "현금액": f"₩ {t_csh:,.0f}"
    }
    return metrics, df_region, df_base, df_asset, df_h, account_summaries

def parse_asset_flow_excel(file):
    df = pd.read_excel(file, sheet_name='자산현황', header=None, engine='openpyxl')
    def extract_tbl(start_kw):
        idx = df[df[0] == start_kw].index
        if len(idx) == 0: return []
        data = []
        for i in range(idx[0] + 1, len(df)):
            if str(df.iloc[i, 0]).strip() in ['nan', 'None', '']: break
            data.append({"항목": str(df.iloc[i,0]).strip(), "금액_num": pd.to_numeric(df.iloc[i,1], errors='coerce'), "비고": str(df.iloc[i,2]).replace('nan','')})
        return data

    def f_krw(v): return f"{'-' if v < 0 else ''}₩ {abs(v):,.0f}" if pd.notna(v) else "₩ 0"

    t_assets, f_assets, c_flow = extract_tbl('총자산 구성'), extract_tbl('금융자산 구성'), extract_tbl('월 현금흐름')
    
    df_t = pd.DataFrame([{"자산 항목": d["항목"], "금액": f_krw(d["금액_num"]), "비고": d["비고"]} for d in t_assets])
    df_f = pd.DataFrame([{"항목": d["항목"], "금액": f_krw(d["금액_num"]), "비고": d["비고"]} for d in f_assets])
    df_c = pd.DataFrame([{"분류": d["항목"], "금액": f_krw(d["금액_num"]), "비고": d["비고"]} for d in c_flow])

    t_net = next((d['금액_num'] for d in t_assets if '총 순자산' in d['항목']), 0)
    r_est = next((d['금액_num'] for d in t_assets if '부동산' in d['항목'] and '순자산' in d['항목']), 0)
    car = next((d['금액_num'] for d in t_assets if '자동차' in d['항목']), 0)
    f_net = next((d['금액_num'] for d in t_assets if '금융 순자산' in d['항목']), 0)
    
    df_tp = pd.DataFrame([{"분류": "부동산 순자산", "현재금액": r_est}, {"분류": "자동차 순자산", "현재금액": car}, {"분류": "금융 순자산", "현재금액": f_net}])
    pen_isa = sum(d['금액_num'] for d in f_assets if any(x in d['항목'] for x in ['IRP', '퇴직금', 'ISA']))
    stk = sum(d['금액_num'] for d in f_assets if any(x in d['항목'] for x in ['주식', '가상화폐']))
    df_fp = pd.DataFrame([{"분류": "연금/ISA", "현재금액": pen_isa}, {"분류": "주식투자", "현재금액": stk}, {"분류": "현금/기타", "현재금액": max(0, f_net - pen_isa - stk)}])

    inc = next((d['금액_num'] for d in c_flow if '실수령액' in d['항목']), 0)
    sp_csh = next((d['금액_num'] for d in c_flow if '여유금' in d['항목']), 0)

    m2 = {
        "총순자산": f_krw(t_net), "총순자산_원": f"{t_net//100000000}억 {(t_net%100000000)//10000}만 원" if t_net >= 100000000 else f_krw(t_net),
        "부동산": f_krw(r_est), "부동산비중": f"비중: {(r_est/t_net*100) if t_net>0 else 0:.1f}%",
        "금융": f_krw(f_net), "금융비중": f"비중: {(f_net/t_net*100) if t_net>0 else 0:.1f}%",
        "여유금": f_krw(sp_csh), "여유금비중": f"실수령액 대비 {(sp_csh/inc*100) if inc>0 else 0:.1f}%"
    }

    f_row = df.isin(['월평균 고정지출']).any(axis=1).idxmax() + 1
    df_fix = pd.DataFrame({"항목": ["학원비", "공과금", "세금", "보험료"], "금액": [f_krw(pd.to_numeric(df.iloc[f_row, i], errors='coerce')) for i in [5, 8, 11, 14]]})
    
    i_s, e_s, s_s, b_s = 0, 0, 0, 0
    for r in range(len(df)):
        for c in range(len(df.columns)-1):
            v = str(df.iloc[r, c]).strip()
            num = pd.to_numeric(df.iloc[r, c+1], errors='coerce')
            if pd.notna(num):
                if '수입 합계' in v: i_s = num
                elif '지출 합계' in v: e_s = num
                elif '주택담보대출원금' in v: s_s = num
                elif v == '잔고': b_s = num

    df_b = pd.DataFrame({"항목": ["1. 총 수입", "2. 총 지출", "3. 저축", "4. 잔고"], "금액": [i_s or inc, e_s, s_s, b_s]})
    return m2, df_tp, df_fp, df_t, df_f, df_c, df_fix, df_b

def get_default_portfolio_data(): return {}, pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), {}
def get_default_asset_data(): return {}, pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

# ---------------------------------------------------------
# 🌟 [파일 관리 & 인증 컴포넌트 최적화]
# ---------------------------------------------------------
LOCAL_EXCEL_PATH = "자산투자관리.xlsx"

def get_file_mod_time(): return os.path.getmtime(LOCAL_EXCEL_PATH) if os.path.exists(LOCAL_EXCEL_PATH) else 0

@st.cache_data(show_spinner=False)
def load_local_excel_data(mod_time):
    if os.path.exists(LOCAL_EXCEL_PATH):
        try: return parse_portfolio_excel(LOCAL_EXCEL_PATH), parse_asset_flow_excel(LOCAL_EXCEL_PATH)
        except Exception: pass 
    return get_default_portfolio_data(), get_default_asset_data()

curr_mod_time = get_file_mod_time()
if "local_mod_time" not in st.session_state or curr_mod_time != st.session_state.local_mod_time:
    st.session_state.local_mod_time = curr_mod_time
    st.session_state.tab6_data, st.session_state.tab7_data = load_local_excel_data(curr_mod_time)
    st.session_state.last_uploaded_hash = None

def process_global_upload(uploaded_file):
    if uploaded_file:
        file_hash = hashlib.md5(uploaded_file.getvalue()).hexdigest()
        if st.session_state.get('last_uploaded_hash') != file_hash:
            try:
                uploaded_file.seek(0)
                st.session_state.tab6_data = parse_portfolio_excel(uploaded_file)
                uploaded_file.seek(0)
                st.session_state.tab7_data = parse_asset_flow_excel(uploaded_file)
                st.session_state.last_uploaded_hash = file_hash
                st.toast("업데이트 완료!", icon="✅")
                st.rerun() 
            except Exception as e: st.error(f"오류: {e}")

def render_auth_and_upload(key_suffix):
    """UI 중복 제거를 위한 인증 및 파일 업로드 통합 모듈"""
    pwd = st.text_input("암호 입력", type="password", key=f"pwd_{key_suffix}", placeholder="소유자 전용 공간입니다. 접근 암호를 입력하세요.", label_visibility="collapsed")
    if pwd == "1016":
        col1, col2 = st.columns(2)
        with col1:
            st.success("✅ 인증 완료! '자산투자관리.xlsx' 연동됨")
            if st.button("🔄 즉시 업데이트", key=f"btn_upd_{key_suffix}", type="primary", use_container_width=True):
                load_local_excel_data.clear()
                st.session_state.tab6_data, st.session_state.tab7_data = load_local_excel_data(get_file_mod_time())
                st.toast("갱신 완료!", icon="✅")
                st.rerun()
        with col2:
            with st.expander("☁️ 클라우드 수동 업로드 (펼치기)"):
                process_global_upload(st.file_uploader("", type=['xlsx', 'xls'], key=f"up_{key_suffix}", label_visibility="collapsed"))
        st.divider()
        return True
    elif pwd: st.error("비밀번호 불일치 (Hint: 1016)")
    return False

t6_metrics, df_region, df_base, df_asset, df_holdings, account_summaries = st.session_state.tab6_data
t7_metrics, df_t_pie, df_f_pie, df_t_table, df_f_table, df_c_table, df_fixed, df_bar = st.session_state.tab7_data

# ---------------------------------------------------------
# 🌟 [마켓 데이터 엔진 최적화]
# ---------------------------------------------------------
@st.cache_data(ttl=180) 
def get_market_data():
    df_list = []
    
    def fetch_ecos(code, name):
        url = f"https://ecos.bok.or.kr/api/StatisticSearch/13ZIQ3I6LS3K4CKFDZO1/json/kr/1/500/817Y002/D/20260101/{pd.Timestamp.today(tz='Asia/Seoul').strftime('%Y%m%d')}/{code}"
        for proxy in [url, f"https://api.allorigins.win/raw?url={urllib.parse.quote(url)}"]:
            try:
                r = requests.get(proxy, headers={'User-Agent': 'Mozilla/5.0'}, timeout=3, verify=False).json()
                if 'StatisticSearch' in r:
                    df = pd.DataFrame(r['StatisticSearch']['row'])[['TIME', 'DATA_VALUE']].rename(columns={'TIME':'일자', 'DATA_VALUE':name})
                    df['일자'], df[name] = pd.to_datetime(df['일자']), pd.to_numeric(df[name], errors='coerce')
                    return df.set_index('일자')
            except: pass
        return pd.DataFrame()

    for df in [fetch_ecos('010210000', '한국10년물'), fetch_ecos('010230000', '한국30년물')]:
        if not df.empty: df_list.append(df.tz_localize(None))

    try:
        vix = yf.Ticker('^VIX').history(start='2026-01-01')[['Close']].rename(columns={'Close':'VIX'})
        df_list.append(vix.tz_localize(None)[~vix.index.duplicated(keep='last')])
    except: pass

    yf_map = {'^GSPC': 'S&P500', '^IXIC': '나스닥', '^N225': '니케이', '^KS11': '코스피', '^KQ11': '코스닥', 'CL=F': 'WTI유', '^TNX': '미국10년물', '^TYX': '미국30년물', '^SOX': '필라델피아 반도체', 'GC=F': '금', 'JPYKRW=X': '엔/원 환율', 'XLK': '기술(XLK)', 'XLF': '금융(XLF)', 'XLV': '헬스케어(XLV)', 'XLE': '에너지(XLE)', 'XLY': '자유소비재(XLY)', 'XLI': '산업재(XLI)', 'XLP': '필수소비재(XLP)', 'XLU': '유틸리티(XLU)', 'XLB': '소재(XLB)', 'XLRE': '부동산(XLRE)', 'XLC': '커뮤니케이션(XLC)'}
    try:
        yf_d = yf.download(list(yf_map.keys()), start='2026-01-01', progress=False)
        yf_c = yf_d['Close'] if isinstance(yf_d.columns, pd.MultiIndex) else yf_d
        for t, n in yf_map.items():
            if t in yf_c:
                tmp = yf_c[[t]].dropna()
                if n == '엔/원 환율': tmp[t] *= 100
                tmp.columns = [n]
                df_list.append(tmp.tz_localize(None)[~tmp.index.duplicated(keep='last')])
    except: pass
            
    try:
        csi = yf.Ticker('399300.SZ').history(period='5d')['Close'].iloc[-1]
        tiger = fdr.DataReader('192090', '2026-01-01')[['Close']]
        tiger.columns = ['CSI300']
        tiger['CSI300'] *= csi / tiger['CSI300'].iloc[-1]
        df_list.append(tiger.tz_localize(None)[~tiger.index.duplicated(keep='last')])
    except: pass

    fdr_map = {'USD/KRW':'환율($/원)', '091160':'K-반도체', '305720':'K-2차전지', '091180':'K-자동차', '157490':'K-인터넷', '227540':'K-헬스케어', '091220':'K-은행', '139230':'K-기계조선', '139240':'K-철강', '315270':'K-미디어엔터', '139220':'K-건설', '139250':'K-화학', '449450':'K-방산'}
    for t, n in fdr_map.items():
        try:
            tmp = fdr.DataReader(t, '2026-01-01')[['Close']].rename(columns={'Close':n})
            df_list.append(tmp.tz_localize(None)[~tmp.index.duplicated(keep='last')])
        except: pass
            
    if not df_list: return pd.DataFrame(), {}, {}, ""
    
    df = pd.concat(df_list, axis=1).ffill().bfill().reset_index().rename(columns={'index':'일자'})
    df = df[df['일자'] >= '2026-01-01']
    df['일자'] = df['일자'].dt.strftime('%Y-%m-%d')
    
    ld, chg = {}, {}
    for c in df.columns[1:]:
        s = df[c]
        ld[c] = pd.to_datetime(df['일자'].iloc[-1]).strftime('%m/%d')
        p, cr = (s.iloc[-2], s.iloc[-1]) if len(s)>1 else (s.iloc[0], s.iloc[0])
        d = cr - p
        chg[c] = f"{d:+.3f}%p" if '년물' in c else f"{d:+.2f} ({(d/p*100) if p!=0 else 0:+.2f}%)"
        df[f'{c} MDD'] = s / s.cummax() - 1.0
        if c in list(yf_map.values())[:6] + list(yf_map.values())[-11:] + list(fdr_map.values())[1:]:
            df[f'{c}(시작=100)'] = (s / s.iloc[0]) * 100 if s.iloc[0] != 0 else 0
            
    return df.fillna(0), ld, chg, pd.Timestamp.now(tz='Asia/Seoul').strftime('%m/%d %H:%M')

df_market, last_dates, changes, sync_time = get_market_data()
latest_data = df_market.iloc[-1] if not df_market.empty else {}

@st.cache_data(ttl=3600)
def get_portfolio_history():
    tkrs = {'KODEX 200':'069500', 'TIGER 미국나스닥100':'133690', 'KODEX 코스닥150':'229200', 'TIGER 일본니케이225':'241180', 'KODEX 차이나CSI300':'283580', 'TIGER 미국S&P500':'360750', 'ACE 미국S&P500미국채혼합50액티브':'438080', 'ACE 미국나스닥100미국채혼합50액티브':'438100', 'KODEX 국고채30년액티브':'439870', 'ACE 미국30년국채액티브(H)':'453850', 'TIGER 미국배당다우존스':'458730', '한온시스템':'018880', 'TIGER 바이오TOP10':'364960', 'PLUS K방산':'449450', 'SOL AI반도체소부장':'455850', 'BOTZ':'BOTZ', 'GRID':'GRID'}
    dls = []
    for n, t in tkrs.items():
        try:
            tmp = yf.Ticker(t).history(start='2026-01-01')[['Close']] if t in ['BOTZ', 'GRID'] else fdr.DataReader(t, '2026-01-01')[['Close']]
            tmp.columns, tmp.index = [n if t not in ['BOTZ','GRID'] else ('로봇공학 및 인공지능 글로벌엑스(BOTZ)' if t=='BOTZ' else '나스닥 스마트 그리드 인프라(GRID)')], pd.to_datetime(tmp.index).normalize().tz_localize(None)
            dls.append(tmp[~tmp.index.duplicated(keep='last')])
        except: pass
    if not dls: return pd.DataFrame(), pd.DataFrame()
    df = pd.concat(dls, axis=1).ffill().bfill()
    dr = df.copy().reset_index().rename(columns={'index':'일자'})
    for c in df.columns: df[c] = (df[c] / df[c].iloc[0]) * 100 if df[c].iloc[0] != 0 else 0
    df = df.reset_index().rename(columns={'index':'일자'})
    df['일자'], dr['일자'] = df['일자'].dt.strftime('%Y-%m-%d'), dr['일자'].dt.strftime('%Y-%m-%d')
    return df, dr

@st.cache_data(ttl=600) 
def get_news_data():
    nd = {"KR": [], "US": []}
    for k, u in [("KR", "hl=ko&gl=KR&ceid=KR:ko"), ("US", "hl=en-US&gl=US&ceid=US:en")]:
        try:
            root = ET.fromstring(requests.get(f"https://news.google.com/rss/headlines/section/topic/BUSINESS?{u}", timeout=3, verify=False).content)
            nd[k] = [{"title": i.find('title').text, "link": i.find('link').text} for i in root.findall('.//item')[:10]]
        except: nd[k] = [{"title": "뉴스 로드 실패", "link": "#"}]
    return nd
news_data = get_news_data()

# ---------------------------------------------------------
# 🌟 [차트 & UI 헬퍼 모듈] (중복 코드 150줄 압축 + 에러 완벽 수정)
# ---------------------------------------------------------
def get_ytd(df, c):
    # 🌟 버그 수정: 클라우드 환경에서 df가 비어있거나 컬럼(c)이 없을 때 발생하는 KeyError 완벽 차단
    if df is None or df.empty or c not in df.columns: 
        return ""
    s = df[c].dropna()
    return f"<code>(YTD {(s.iloc[-1]/s.iloc[0]-1)*100:+.1f}%)</code>" if len(s)>0 and s.iloc[0]!=0 else ""

def render_title(n, t, y): st.markdown(f"<div style='white-space:nowrap; overflow:hidden; text-overflow:ellipsis; margin-bottom:2px;' title='{n}'><b>{n}</b> <code>{t}</code> {y}</div>" if t else f"<div style='white-space:nowrap; overflow:hidden; text-overflow:ellipsis; margin-bottom:2px;' title='{n}'><b>{n}</b> {y}</div>", unsafe_allow_html=True)

def mdd_txt(v):
    p = v * 100
    return f":{['green','orange','red','violet','blue'][min(4, max(0, int(-p//10)))]}[MDD {p:.1f}%]"

def draw_mini_chart(df, col):
    if df is None or df.empty or col not in df.columns: return st.markdown(f"*{col} 데이터 없음*")
    d = df[['일자', col]].dropna()
    mn, mx = d[col].min(), d[col].max()
    pad = (mx-mn)*0.1 or (mn*0.1 if mn!=0 else 1)
    d['y_min'] = mn - pad
    base = alt.Chart(d).encode(x=alt.X('일자:T', title=None, axis=alt.Axis(grid=True, gridColor='#666', gridOpacity=0.5, gridDash=[4,4], format='%m/%d', tickCount=5)), y=alt.Y(f'{col}:Q', title=None, scale=alt.Scale(domain=[mn-pad, mx+pad], zero=False), axis=alt.Axis(grid=True, gridColor='#666', gridOpacity=0.5, gridDash=[4,4], format='.2f' if '년물' in col else '~s', tickCount=4)), tooltip=[alt.Tooltip('일자:T', format='%Y-%m-%d'), alt.Tooltip(f'{col}:Q', format=',.2f')])
    st.altair_chart(alt.layer(base.mark_area(opacity=0.15).encode(y2='y_min:Q'), base.mark_line(size=2)).properties(height=180), width="stretch")

def render_chart_grid(items, df, ld):
    for i in range(0, len(items), 4):
        cols = st.columns(4)
        for j, (title, tag, col) in enumerate(items[i:i+4]):
            with cols[j]:
                render_title(title, tag or f"({ld.get(col, '-')})", get_ytd(df, col))
                draw_mini_chart(df, col)

def draw_pie_chart(df, sch):
    if df is None or df.empty or '현재금액' not in df.columns: return st.markdown("*데이터 없음*")
    d = df[df['현재금액'] > 0].copy()
    if d.empty: return st.markdown("*데이터 없음*")
    d['p_num'] = (d['현재금액'] / d['현재금액'].sum() * 100).round(1)
    d['비중'] = d['p_num'].astype(str) + '%'
    base = alt.Chart(d).encode(theta=alt.Theta("현재금액:Q", stack=True), color=alt.Color("분류:N", legend=alt.Legend(title=None, orient="bottom", columns=3), scale=alt.Scale(scheme=sch)), tooltip=['분류', alt.Tooltip('현재금액:Q', format=',.0f'), '비중'])
    st.altair_chart(alt.layer(base.mark_arc(innerRadius=40, outerRadius=100, stroke="#fff", strokeWidth=1), base.mark_text(radius=70, size=13, fontWeight='bold', fill='white').encode(text=alt.condition(alt.datum.p_num >= 4.0, '비중:N', alt.value('')))).properties(height=320), width="stretch")

# ---------------------------------------------------------
# UI 공통 헤더
# ---------------------------------------------------------
kr10, kr30, vix = latest_data.get('한국10년물', 0), latest_data.get('한국30년물', 0), latest_data.get('VIX', 0)
vix_s = "데이터 없음" if vix==0 else f"{vix:,.2f}"

with st.expander(f"ℹ️ 시스템 알림 및 데이터 안내 (🔄 최근 갱신: {sync_time} 기준)"):
    if kr10 == 0: st.markdown("<div style='background-color:rgba(255,82,82,0.1); border-left:4px solid #FF5252; padding:10px; margin-bottom:10px;'><b style='color:#FF5252;'>⚠️ 한국 국고채 데이터 차단됨 (클라우드 IP 방화벽 이슈)</b><br>로컬 구동 파일(VBS)로 실행 시 정상 작동합니다.</div>", unsafe_allow_html=True)
    st.info(f"🔔 **[국고채 금리]** 🇰🇷 10년물: **{kr10:.3f}% ({changes.get('한국10년물','')})** | 🇰🇷 30년물: **{kr30:.3f}% ({changes.get('한국30년물','')})**")
    st.warning("⚠️ 주말(토/일) 아시아 증시 데이터 지연 송출 및 타 사이트(Investing) 장외 데이터와의 차이 안내")

# ---------------------------------------------------------
# 🌟 7개 탭 (Tabs)
# ---------------------------------------------------------
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(["📊 종합 마켓 뷰", "📈 상세 차트 분석", "🏭 미국 섹터별 흐름", "🇰🇷 국내 섹터별 흐름", "📰 실시간 경제 뉴스", "🔒 내 보유종목", "💼 자산 및 현금흐름"])

with tab1:
    st.subheader("💡 시장 기상도 및 전략")
    wc, cc = st.columns([2, 1])
    with wc:
        v, md = latest_data.get('VIX', 20), latest_data.get('S&P500 MDD', 0)*100
        if v >= 30 or md <= -20: 
            st.error("**현재 시장 기상도:** ⛈️ 심각한 약세장 (공포/패닉)")
            st.markdown("<div class='etf-box'>🛡️ <b>[전략] 방어 집중:</b> BIL, TLT, KODEX CD금리액티브 | <b>테마:</b> 방산(ITA), 금(GDX)</div>", unsafe_allow_html=True)
        elif v >= 20 or md <= -10: 
            st.warning("**현재 시장 기상도:** 🌧️ 주의/조정장 (방어 필요)")
            st.markdown("<div class='etf-box'>☂️ <b>[전략] 보수적 접근:</b> GLD, XLV, ACE 골드선물 | <b>테마:</b> 유틸리티(XLU), 필수소비재(XLP)</div>", unsafe_allow_html=True)
        elif v < 15 and md >= -3: 
            st.success("**현재 시장 기상도:** ☀️ 안정적 강세장 (Risk On)")
            st.markdown("<div class='etf-box'>🚀 <b>[전략] 공격 투자:</b> QQQ, TIGER 미국나스닥100 | <b>테마:</b> AI/로봇(BOTZ), 비트코인(IBIT)</div>", unsafe_allow_html=True)
        else: 
            st.info("**현재 시장 기상도:** ⛅ 보통/눈치보기 장세 (Neutral)")
            st.markdown("<div class='etf-box'>⚖️ <b>[전략] 코어 유지:</b> SPY, SCHD, TIGER 배당다우존스 | <b>테마:</b> 인프라(PAVE), 고배당(JEPQ)</div>", unsafe_allow_html=True)

    with cc:
        today = pd.Timestamp.now(tz='Asia/Seoul').normalize()
        ws = today - pd.Timedelta(days=today.weekday())
        tw, nw = [], []
        for d, e in MACRO_EVENTS.items():
            ev = pd.to_datetime(d).tz_localize('Asia/Seoul')
            s = f"- {ev.strftime('%m/%d')} (['월','화','수','목','금','토','일'][ev.weekday()]): {e}"
            if ws <= ev <= ws + pd.Timedelta(days=6): tw.append(s)
            elif ws + pd.Timedelta(days=7) <= ev <= ws + pd.Timedelta(days=13): nw.append(s)
        
        st.info(f"📅 **다가오는 주요 매크로 일정**\n\n**[이번 주 일정]**\n{chr(10).join(tw) if tw else '- 주요 일정 없음'}\n\n**[다음 주 일정]**\n{chr(10).join(nw) if nw else '- 주요 일정 없음'}")

    st.subheader("📊 16개 핵심 지표 메트릭")
    m_data = [
        ("S&P 500", "S&P500", ",.2f", ""), ("NASDAQ", "나스닥", ",.2f", ""), ("필라델피아 반도체", "필라델피아 반도체", ",.2f", ""), ("VIX 지수 (공포)", "VIX", ",.2f", ""),
        ("KOSPI", "코스피", ",.2f", ""), ("KOSDAQ", "코스닥", ",.2f", ""), ("Nikkei 225", "니케이", ",.2f", ""), ("CSI 300", "CSI300", ",.2f", ""),
        ("원/달러 환율", "환율($/원)", ",.2f", " 원"), ("엔/원 환율 (100엔)", "엔/원 환율", ",.2f", " 원"), ("WTI유", "WTI유", ",.2f", " $"), ("금 (Gold)", "금", ",.2f", " $"),
        ("미국 10년물", "미국10년물", ".3f", " %"), ("미국 30년물", "미국30년물", ".3f", " %"), ("한국 10년물", "한국10년물", ".3f", " %"), ("한국 30년물", "한국30년물", ".3f", " %")
    ]
    for i in range(0, 16, 4):
        cols = st.columns(4)
        for j, (n, c, f, sfx) in enumerate(m_data[i:i+4]):
            val = latest_data.get(c, 0)
            v_str = "데이터 없음" if val==0 else f"{val:{f}}{sfx}"
            cols[j].metric(f"{n} [{last_dates.get(c,'-')}]\n{mdd_txt(latest_data.get(c+' MDD',0)) if 'MDD' not in c and '년물' not in c else ''}", v_str, changes.get(c, ''))

with tab2:
    st.subheader("📈 시장 지표 상세 분석")
    render_chart_grid([("S&P 500", None, "S&P500"), ("나스닥", None, "나스닥"), ("필라델피아 반도체", None, "필라델피아 반도체"), ("VIX 지수", None, "VIX"), ("코스피", None, "코스피"), ("코스닥", None, "코스닥"), ("니케이 225", None, "니케이"), ("CSI 300", None, "CSI300"), ("원/달러 환율", None, "환율($/원)"), ("엔/원 환율", None, "엔/원 환율"), ("WTI유", None, "WTI유"), ("금 (Gold)", None, "금"), ("미국 10년물", None, "미국10년물"), ("미국 30년물", None, "미국30년물"), ("한국 10년물", None, "한국10년물"), ("한국 30년물", None, "한국30년물")], df_market, last_dates)

with tab3:
    st.subheader("🏭 미국 11대 대표 섹터 흐름")
    render_chart_grid([("기술", "Apple", "기술(XLK)"), ("금융", "Berkshire", "금융(XLF)"), ("헬스케어", "Eli Lilly", "헬스케어(XLV)"), ("자유소비재", "Amazon", "자유소비재(XLY)"), ("커뮤니케이션", "Meta", "커뮤니케이션(XLC)"), ("산업재", "Caterpillar", "산업재(XLI)"), ("필수소비재", "P&G", "필수소비재(XLP)"), ("에너지", "ExxonMobil", "에너지(XLE)"), ("유틸리티", "NextEra", "유틸리티(XLU)"), ("소재", "Linde", "소재(XLB)"), ("부동산", "Prologis", "부동산(XLRE)")], df_market, last_dates)

with tab4:
    st.subheader("🇰🇷 국내 12대 대표 테마 흐름")
    render_chart_grid([("반도체", "SK하이닉스", "K-반도체"), ("2차전지", "LG엔솔", "K-2차전지"), ("자동차", "현대차", "K-자동차"), ("인터넷/SW", "NAVER", "K-인터넷"), ("바이오/헬스", "삼바", "K-헬스케어"), ("은행/금융", "KB금융", "K-은행"), ("기계/조선", "HD현대중", "K-기계조선"), ("방위산업", "한화에어로", "K-방산"), ("미디어/엔터", "하이브", "K-미디어엔터"), ("철강/소재", "POSCO", "K-철강"), ("화학", "LG화학", "K-화학"), ("건설", "현대건설", "K-건설")], df_market, last_dates)

with tab5:
    st.markdown("#### 📰 실시간 주요 경제 헤드라인")
    c1, c2 = st.columns(2)
    with c1: 
        st.markdown("##### 🇰🇷 국내 경제 (Top 10)")
        for n in news_data["KR"]: st.markdown(f"🔹 <a class='news-link' href='{n['link']}' target='_blank'>{n['title']}</a>", unsafe_allow_html=True)
    with c2: 
        st.markdown("##### 🌎 글로벌 경제 (Top 10)")
        for n in news_data["US"]: st.markdown(f"🔹 <a class='news-link' href='{n['link']}' target='_blank'>{n['title']}</a>", unsafe_allow_html=True)

with tab6:
    st.subheader("🔒 개인 포트폴리오 (Private)")
    if render_auth_and_upload("t6"):
        st.markdown("##### 💰 총 자산 현황 요약")
        cols = st.columns(4)
        cols[0].metric("총 자산", t6_metrics.get("총자산", "₩ 0"), t6_metrics.get("평가손익", ""))
        cols[1].metric("총 매수금액", t6_metrics.get("총매수금액", "₩ 0"), "")
        cols[2].metric("실현 손익", t6_metrics.get("실현손익", "₩ 0"), "")
        cols[3].metric("계좌 현금 비중", t6_metrics.get("현금비중", "0.0%"), t6_metrics.get("현금액", "₩ 0"), delta_color="off")
        
        st.markdown("##### 🌍 포트폴리오 노출 통계")
        c1, c2, c3 = st.columns(3)
        with c1: st.markdown("**📊 자산군별**"); draw_pie_chart(df_asset, 'category10')
        with c2: st.markdown("**📌 지역그룹별**"); draw_pie_chart(df_region, 'category10')
        with c3: st.markdown("**📌 베이스국가별**"); draw_pie_chart(df_base, 'category10')

        st.divider()
        st.markdown("##### 🔍 개별 보유종목 실제 가격 추이")
        df_p_h, df_p_r = get_portfolio_history()
        
        if not df_holdings.empty and not df_p_h.empty:
            acts = [n for n in df_holdings['종목명'].unique() if n in df_p_h.columns]
            for i in range(0, len(acts), 4):
                mc = st.columns(4)
                for j, hn in enumerate(acts[i:i+4]):
                    with mc[j]:
                        ytd = df_p_h[hn].dropna().iloc[-1] - 100 if not df_p_h[hn].dropna().empty else 0
                        hr = df_holdings[df_holdings['종목명']==hn].iloc[0]
                        bp, cp = hr.get('매수단가_num',0), hr.get('현재가_num',0)
                        
                        dp = df_p_r[['일자', hn]].copy()
                        lv = dp[hn].dropna().iloc[-1] if not dp[hn].dropna().empty else 0
                        if lv > 0 and cp > 0 and (cp/lv)>500: dp[hn] *= (cp/lv)
                        
                        render_title(hn, "", f"<code>(YTD {ytd:+.1f}%)</code>")
                        draw_holding_mini_chart_raw(dp, hn, buy_line_y=bp if bp>0 else None, y_format=',.0f' if lv>1000 else ',.2f')
        
        st.divider()
        st.markdown("##### 🧾 계좌별 상세 보유 종목 현황")
        cc = {"종목명": st.column_config.TextColumn("종목명", width=250), "보유수량": st.column_config.TextColumn("수량", alignment="right"), "매수단가": st.column_config.TextColumn("매수단가", alignment="right"), "현재가": st.column_config.TextColumn("현재가", alignment="right"), "현재가치": st.column_config.TextColumn("현재가치", alignment="right"), "평가손익": st.column_config.TextColumn("손익", alignment="right"), "수익률(%)": st.column_config.TextColumn("수익률", alignment="right")}
        if not df_holdings.empty:
            for acc in df_holdings["계좌 구분"].unique():
                d = df_holdings[df_holdings["계좌 구분"] == acc].drop(columns=["계좌 구분", "매수단가_num", "현재가_num"], errors='ignore')
                sm = account_summaries.get(acc, {"buy":"","total":"","profit":"","ret":"","color":"black","cash_amt":"","cash_weight":"","realized":""})
                st.markdown(f"**🏦 {acc}** | 총매수: {sm['buy']} | 평가: {sm['total']} | 손익: :{sm['color']}[**{sm['profit']} ({sm['ret']})**] | 실현: **{sm['realized']}** | 현금: **{sm['cash_weight']}** ({sm['cash_amt']})")
                
                def clr(v): return 'color: #FF5252; font-weight: bold;' if '+' in str(v) else ('color: #4C82FF; font-weight: bold;' if '-' in str(v) else '')
                s_df = d.style.map(clr, subset=[c for c in ['평가손익','수익률(%)'] if c in d.columns]) if hasattr(d.style, 'map') else d
                st.dataframe(s_df, width="stretch", hide_index=True, column_config=cc, height=len(d)*36+43)

with tab7:
    st.subheader("💼 종합 자산 및 현금흐름 (Private)")
    if render_auth_and_upload("t7"):
        st.markdown("##### 💎 총 자산 및 여유 현금 요약")
        cols = st.columns(4)
        cols[0].metric("총 순자산", t7_metrics.get("총순자산", "₩ 0"), t7_metrics.get("총순자산_원", ""), delta_color="off")
        cols[1].metric("부동산 순자산", t7_metrics.get("부동산", "₩ 0"), t7_metrics.get("부동산비중", ""), delta_color="off")
        cols[2].metric("금융 순자산", t7_metrics.get("금융", "₩ 0"), t7_metrics.get("금융비중", ""), delta_color="off")
        cols[3].metric("월 여유금", t7_metrics.get("여유금", "₩ 0"), t7_metrics.get("여유금비중", ""), delta_color="normal")
        
        c1, c2 = st.columns([1, 1])
        cca = {"금액": st.column_config.TextColumn("금액", alignment="right"), "비고": st.column_config.TextColumn("비고", width=250)}
        with c1:
            st.markdown("#### 1. 자산 현황")
            draw_pie_chart(df_t_pie, 'category10'); st.dataframe(df_t_table, width="stretch", hide_index=True, column_config=cca, height=len(df_t_table)*36+43)
            draw_pie_chart(df_f_pie, 'set2'); st.dataframe(df_f_table, width="stretch", hide_index=True, column_config=cca, height=len(df_f_table)*36+43)
        with c2:
            st.markdown("#### 2. 월간 현금흐름")
            if not df_bar.empty:
                st.altair_chart(alt.Chart(df_bar).mark_bar(size=40).encode(x=alt.X('항목:N', title=None, axis=alt.Axis(labelAngle=0)), y=alt.Y('금액:Q', title=None), color=alt.Color('항목:N', legend=None)).properties(height=280), width="stretch")
            st.dataframe(df_c_table, width="stretch", hide_index=True, column_config=cca, height=len(df_c_table)*36+43)
            st.markdown("##### 🏦 월평균 고정지출 그룹")
            st.dataframe(df_fixed, width="stretch", hide_index=True, column_config={"금액": st.column_config.TextColumn("금액", alignment="right")}, height=len(df_fixed)*36+43)
