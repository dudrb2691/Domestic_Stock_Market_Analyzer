import streamlit as st
import google.generativeai as genai
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import FinanceDataReader as fdr
from datetime import datetime, timedelta
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import email.utils
import re # HTML 태그 제거용

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
                with st.spinner("전문가 모드로 가장 최근 분기 실적과 오늘의 뉴스를 분석 중입니다... 🔍"):
                    
                    # 🔥 [수정 1] 연간 실적 대신 '최근 4분기 실적' 가져오기
                    try:
                        income_stmt = stock_info.quarterly_income_stmt.iloc[:, :4] 
                        financial_summary = income_stmt.to_string()
                    except:
                        financial_summary = "최근 분기 재무 데이터를 가져오지 못했습니다."

                    # 🔥 [수정 2] 뉴스 헤드라인 뿐만 아니라 '요약 내용(Description)'까지 추출
                    latest_news_context = ""
                    try:
                        query = urllib.parse.quote(f"{company_name} 실적 OR 목표가 OR 외국인 OR 기관")
                        url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
                        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                        response = urllib.request.urlopen(req)
                        root = ET.fromstring(response.read())
                        items = root.findall('.//item')
                        
                        news_list = []
                        for item in items:
                            pub_date_obj = email.utils.parsedate_to_datetime(item.find('pubDate').text)
                            title = item.find('title').text
                            # HTML 태그를 제거하여 순수 텍스트 요약본만 가져옵니다.
                            desc_raw = item.find('description').text if item.find('description') is not None else ""
                            desc_clean = re.sub('<[^<]+>', '', desc_raw).strip()
                            
                            news_list.append({'title': title, 'desc': desc_clean, 'date_obj': pub_date_obj})
                        
                        news_list.sort(key=lambda x: x['date_obj'], reverse=True)
                        
                        for news in news_list[:15]: 
                            latest_news_context += f"- [{news['date_obj'].strftime('%Y-%m-%d')}] {news['title']}\n  요약: {news['desc'][:100]}...\n"
                    except Exception as e:
                        latest_news_context = "최신 뉴스를 검색하지 못했습니다."

                    # 🔥 [수정 3] 현재 날짜 명시 및 과거 데이터 사용 엄격 금지
                    today_date = datetime.now().strftime("%Y년 %m월 %d일")
                    
                    prompt = f"""
                    당신은 50대 주식 투자자를 위한 친절하고 극도로 보수적인 수석 애널리스트입니다. 
                    🚨 중요: 오늘은 {today_date}입니다. 과거 연도(예: 2024년, 2025년)의 데이터를 마치 미래의 예상치인 것처럼 설명하는 심각한 오류를 절대 범하지 마세요. 
                    '{company_name}'(종목코드: {ticker_code})에 대해 분석해 주세요.

                    [실시간 데이터 참고 정보 - 절대적으로 신뢰할 것!]
                    1. 최근 4분기 재무제표 요약 (가장 최근의 분기 흐름을 파악하세요): 
                    {financial_summary}
                    2. 🚨 오늘({today_date}) 기준 가장 최신 실시간 뉴스 헤드라인 및 요약 (이번 분기 실적, 수급 동향, 목표가 포함 - 이 정보를 최우선으로 반영하세요!):
                    {latest_news_context}

                    [요청 사항]
                    1. **수치로 보는 살림살이 (가장 최근 분기 기준)**: 제공된 '최근 4분기 재무제표'와 '실시간 뉴스 요약'을 바탕으로, "가장 최근 분기에 장사를 잘했는지"를 주부의 언어로 분석하세요. 절대 과거 연간 데이터를 미래 예상치로 둔갑시키지 마세요.
                    2. **누가 사고 있나요? (최신 수급 반영)**: '실시간 뉴스'에 언급된 가장 최근의 외국인/기관 매수/매도 동향을 반드시 파악하여 동네 소문이나 시장 분위기에 비유해 설명하세요.
                    3. **증권사별 최신 목표 주가 (필수!)**: 오직 위 [실시간 뉴스 헤드라인]만을 바탕으로, 가장 최근 날짜에 증권사들이 발표한 구체적인 목표가를 나열하세요.
                    4. **AI 종합 의견 (극보수적 접근 필수)**: 위 증권사들의 의견 중 '가장 낮은 수치'를 기준으로 하거나 그보다 더 보수적으로 낮춰 잡으세요. 절대로 낙관적이거나 희망적인 전망을 섞지 마세요. 주가가 떨어져도 안심할 수 있는 가장 보수적이고 안전한 최저 목표 가격대 하나만 딱 정해서 제시하세요.
                    5. **마크다운 주의사항 (필수!)**: 금액이나 비율 등 숫자의 범위를 나타낼 때 절대로 물결기호(~)를 사용하지 마세요! 화면에서 글자에 줄이 그어지는 오류가 납니다. 반드시 '에서' 또는 하이픈(-)을 사용하세요. (예: 50만원에서 60만원)

                    [출력 형식]
                    ### 🚦 한눈에 보는 신호등 (🟢안전 / 🟡주의 / 🔴위험)
                    ### 💰 1. 수치로 보는 살림살이 (최근 분기 실적 반영)
                    ### 👥 2. 최근 시장의 분위기 (최신 수급 동향)
                    ### 🎯 3. 전문가들은 얼마까지 갈 거라 보나요? (실시간 최신 목표가)
                    ### 💡 4. AI 애널리스트의 최종 조언 (초보수적 접근)
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