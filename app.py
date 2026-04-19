import streamlit as st
import google.generativeai as genai
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import FinanceDataReader as fdr
from datetime import datetime, timedelta, timezone
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import email.utils
import re
import requests # 네이버 웹페이지 통신용
from bs4 import BeautifulSoup # 네이버 웹페이지 텍스트 추출용

# 1. 페이지 설정
st.set_page_config(page_title="엄마표 주식 투자 가이드", page_icon="🛒", layout="wide")

# --- 🪄 어머니를 위한 돋보기 기능 ---
st.markdown("""
<style>
    html, body, [class*="css"] { font-size: 22px !important; }
    .stMarkdown p, .stMarkdown li { font-size: 22px !important; line-height: 1.8 !important; }
    .stButton button { font-size: 22px !important; font-weight: bold !important; height: 3em !important; }
    .stTextInput input, .stSelectbox div[data-baseweb="select"] { font-size: 22px !important; }
    .stTabs [data-baseweb="tab"] { font-size: 22px !important; font-weight: bold !important; }
    [data-testid="stSidebar"] p { font-size: 20px !important; }
</style>
""", unsafe_allow_html=True)

# 2. API 및 모델 설정
try:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-3-flash-preview')
except KeyError:
    st.error("🔒 'GEMINI_API_KEY'가 설정되지 않았습니다.")
    st.stop()

# 3. 데이터 캐싱
@st.cache_data
def get_stock_list():
    df_krx = fdr.StockListing('KRX')
    df_krx['display_name'] = df_krx['Name'] + " (" + df_krx['Code'] + ")"
    return df_krx[['display_name', 'Code', 'Name', 'Market']]

stock_df = get_stock_list()

if "history" not in st.session_state: st.session_state.history = []
if "analyses" not in st.session_state: st.session_state.analyses = {}

# --- 사이드바 ---
with st.sidebar:
    st.header("⭐ 나의 관심 목록")
    user_name = st.text_input("사용자 이름", value="엄마")
    if st.session_state.history:
        st.write("🕒 최근 본 종목")
        for h_item in reversed(st.session_state.history[-5:]):
            st.markdown(f"- 🔍 {h_item}")
    st.markdown("---")
    st.info("💡 창을 닫기 전까지 기록이 유지됩니다.")

# --- 메인 화면 ---
st.title("🛒 엄마표 주식 투자 가이드")

selected_display = st.selectbox(
    "🔍 궁금한 회사 이름을 선택해 보세요",
    options=[""] + stock_df['display_name'].tolist(),
    format_func=lambda x: "회사명을 선택하세요" if x == "" else x
)

if selected_display:
    row = stock_df[stock_df['display_name'] == selected_display].iloc[0]
    ticker_code, company_name, market = row['Code'], row['Name'], row['Market']
    suffix = ".KQ" if market == 'KOSDAQ' else ".KS"
    full_ticker = ticker_code + suffix

    if company_name not in st.session_state.history:
        st.session_state.history.append(company_name)

    stock_info = yf.Ticker(full_ticker)
    
    tab1, tab2, tab3 = st.tabs(["📋 전문 분석 리포트", "📈 주가 그래프", "📰 최신 뉴스"])

    with tab1:
        if company_name in st.session_state.analyses:
            st.markdown(st.session_state.analyses[company_name])
            if st.button("🔄 최신 내용으로 다시 분석하기"):
                del st.session_state.analyses[company_name]
                st.rerun()
        else:
            if st.button(f"🚀 {company_name} 정밀 분석 시작", type="primary"):
                with st.spinner("전문가 모드로 네이버 증권, 실시간 뉴스, 재무제표를 종합 분석 중입니다... 🔍"):
                    
                    # 1. 최근 4분기 실적 가져오기
                    try:
                        income_stmt = stock_info.quarterly_income_stmt.iloc[:, :4] 
                        financial_summary = income_stmt.to_string()
                    except:
                        financial_summary = "최근 분기 재무 데이터를 가져오지 못했습니다."

                    # 🔥 [새로 추가된 기능] 네이버 증권 실시간 크롤링 (기업 개요 및 지표)
                    naver_info = ""
                    try:
                        naver_url = f"https://finance.naver.com/item/main.naver?code={ticker_code}"
                        # 네이버 금융의 한글 깨짐을 방지하기 위해 requests 사용 및 EUC-KR 인코딩 설정
                        res = requests.get(naver_url, headers={'User-Agent': 'Mozilla/5.0'})
                        res.encoding = 'euc-kr' 
                        soup = BeautifulSoup(res.text, 'html.parser')
                        
                        summary_info = soup.select_one('.summary_info p')
                        if summary_info:
                            naver_info += f"- [네이버 증권 기업개요] {summary_info.get_text(strip=True)}\n"
                            
                        per = soup.select_one('#_per')
                        pbr = soup.select_one('#_pbr')
                        dividend = soup.select_one('#_dvr')
                        
                        naver_info += "- [실시간 투자 지표] "
                        if per: naver_info += f"PER(주가수익비율): {per.text}배 / "
                        if pbr: naver_info += f"PBR(주가순자산비율): {pbr.text}배 / "
                        if dividend: naver_info += f"배당수익률: {dividend.text}%"
                    except Exception as e:
                        naver_info = "네이버 증권 정보를 불러오지 못했습니다."

                    # 2. 구글 최신 뉴스 검색 (14일 이내 철통 방어 필터 적용)
                    latest_news_context = ""
                    try:
                        query = urllib.parse.quote(f"{company_name} (실적 OR 목표가 OR 증권사 리포트) when:3m")
                        url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
                        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                        response = urllib.request.urlopen(req)
                        root = ET.fromstring(response.read())
                        items = root.findall('.//item')
                        
                        cutoff_date = datetime.now(timezone.utc) - timedelta(days=14)
                        news_list = []
                        
                        for item in items:
                            pub_date_obj = email.utils.parsedate_to_datetime(item.find('pubDate').text)
                            if pub_date_obj >= cutoff_date:
                                title = item.find('title').text
                                desc_raw = item.find('description').text if item.find('description') is not None else ""
                                desc_clean = re.sub('<[^<]+>', '', desc_raw).strip()
                                news_list.append({'title': title, 'desc': desc_clean, 'date_obj': pub_date_obj})
                        
                        news_list.sort(key=lambda x: x['date_obj'], reverse=True)
                        
                        if not news_list:
                            latest_news_context = "최근 14일 이내에 발표된 유의미한 실적이나 목표가 뉴스가 없습니다."
                        else:
                            for news in news_list[:15]: 
                                latest_news_context += f"- [{news['date_obj'].strftime('%Y-%m-%d')}] {news['title']}\n  요약: {news['desc'][:100]}...\n"
                    except Exception as e:
                        latest_news_context = "최신 뉴스를 검색하지 못했습니다."

                    # 🔥 [수정된 프롬프트] 네이버 증권 정보와 PB 페르소나 적용
                    today_date = datetime.now().strftime("%Y년 %m월 %d일")
                    
                    prompt = f"""
                    당신은 50대 주식 투자자의 자산을 안전하게 관리해주는 '친절하고 객관적인 수석 자산관리사(PB)'입니다.
                    오늘은 {today_date}입니다. 과거의 데이터를 미래인 것처럼 말하지 마세요.

                    [실시간 데이터 (절대 규칙: 아래 제공된 정보만 사용할 것!)]
                    1. 📌 네이버 증권 최신 기업 정보 (가장 먼저 읽어보고 회사의 기본기를 파악하세요):
                    {naver_info}
                    2. 📊 최근 4분기 재무제표 요약: 
                    {financial_summary}
                    3. 🚨 오늘({today_date}) 기준 최신 뉴스 요약본:
                    {latest_news_context}

                    [요청 사항]
                    1. **어떤 회사인가요? & 살림살이**: [네이버 증권 기업개요]를 바탕으로 이 회사가 주로 무슨 일을 하는지 아주 짧게 소개한 뒤, [투자 지표(PER/PBR)]와 [최근 분기 실적/뉴스]를 엮어서 "지금 주가가 비싼 편인지, 장사는 잘하고 있는지"를 주부의 언어로 브리핑하세요.
                    2. **누가 사고 있나요?**: 위 '최신 뉴스 요약본'에 등장하는 최근 수급 동향(외국인/기관)을 설명하세요. 뉴스가 없다면 생략하세요.
                    3. **증권사별 최신 목표 주가**: 위 '최신 뉴스 요약본'에 명시된 목표가만 나열하세요. 뉴스에 목표가가 없다면 "최근 14일간 뉴스로 발표된 새로운 목표가는 없습니다"라고 정직하게 답하세요. 과거 기억으로 지어내면 안 됩니다.
                    4. **자산관리사(PB)의 균형 잡힌 조언**: 무조건 겁을 주거나 부추기지 마세요. 제공된 네이버 증권의 배당수익률이나 기업 지표, 뉴스를 종합하여 이 주식의 '호재(기회)' 1가지와 '악재(주의점)' 1가지를 공정하게 설명하고, 어머니께 추천하는 현실적인 매매 전략(분할 매수, 관망 등)을 제안하세요.
                    5. **마크다운 주의사항**: 숫자의 범위를 나타낼 때 물결기호(~)를 절대 사용하지 말고 '에서'나 하이픈(-)을 사용하세요.

                    [출력 형식]
                    ### 🚦 한눈에 보는 투자 매력도 (🟢관심 / 🟡관망 / 🔴주의)
                    ### 🏢 1. 어떤 회사이고, 살림살이는 어떤가요? (네이버 증권 지표 포함)
                    ### 👥 2. 최근 시장의 분위기
                    ### 🎯 3. 전문가들의 최신 목표가 (뉴스 출처 기반)
                    ### 💡 4. 자산관리사의 균형 잡힌 조언
                    """
                    
                    response = model.generate_content(prompt)
                    if response.parts:
                        st.session_state.analyses[company_name] = response.text
                        st.rerun()

    with tab2:
        st.subheader(f"📊 {company_name} 주가 흐름")
        period_map = {"1일": "1d", "1주": "5d", "1달": "1mo", "1년": "1y", "5년": "5y"}
        selected_period = st.radio("기간 선택", list(period_map.keys()), index=3, horizontal=True)
        
        data = yf.download(full_ticker, period=period_map[selected_period])
        if not data.empty:
            close = data['Close']
            if isinstance(close, pd.DataFrame): close = close.iloc[:, 0]
            fig = go.Figure(data=[go.Scatter(x=data.index, y=close, line=dict(color='#FF4B4B', width=3))])
            fig.update_layout(template="plotly_white", margin=dict(l=20, r=20, t=20, b=20), font=dict(size=18), hovermode='x unified')
            st.plotly_chart(fig, use_container_width=True)

    with tab3:
        st.subheader(f"🗞️ {company_name} 최신 소식")
        try:
            encoded_query = urllib.parse.quote(f"{company_name} 주식 전망")
            url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ko&gl=KR&ceid=KR:ko"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            response = urllib.request.urlopen(req)
            root = ET.fromstring(response.read())
            news_list = []
            for item in root.findall('.//item'):
                news_list.append({
                    'title': item.find('title').text,
                    'link': item.find('link').text,
                    'date': email.utils.parsedate_to_datetime(item.find('pubDate').text)
                })
            news_list.sort(key=lambda x: x['date'], reverse=True)
            for news in news_list[:7]:
                st.write(f"🔗 [{news['title']}]({news['link']})")
                kst_date = news['date'] + timedelta(hours=9)
                st.caption(f"발행일: {kst_date.strftime('%Y년 %m월 %d일 %H:%M')}")
        except: st.write("뉴스를 불러오지 못했습니다.")

else:
    st.info("💡 위 검색창에서 궁금한 종목을 선택해 주세요. (예: 삼성전자, 에코프로)")