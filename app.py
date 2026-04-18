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

# 1. 페이지 설정
st.set_page_config(page_title="엄마표 주식 투자 가이드", page_icon="🛒", layout="wide")

# --- 🪄 어머니를 위한 돋보기 기능 (전체 글씨 크기 키우기) ---
st.markdown("""
<style>
    html, body, [class*="css"] { font-size: 22px !important; }
    .stMarkdown p, .stMarkdown li { font-size: 22px !important; line-height: 1.8 !important; }
    .stButton button { font-size: 22px !important; font-weight: bold !important; height: 3em !important; }
    .stTextInput input, .stSelectbox div[data-baseweb="select"] { font-size: 22px !important; }
    .stTabs [data-baseweb="tab"] { font-size: 22px !important; font-weight: bold !important; }
    [data-testid="stSidebar"] p { font-size: 20px !important; }
    .metric-card { background-color: #f0f2f6; padding: 20px; border-radius: 10px; text-align: center; }
</style>
""", unsafe_allow_html=True)

# 2. API 및 모델 설정
try:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
    # 최신 정보를 더 잘 파악하는 모델 설정
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

    # 데이터 미리 가져오기 (재무 데이터)
    stock_info = yf.Ticker(full_ticker)
    
    tab1, tab2, tab3 = st.tabs(["📋 전문 분석 리포트", "📈 주가 그래프", "📰 최신 뉴스"])

    with tab1:
        if company_name in st.session_state.analyses:
            st.markdown(st.session_state.analyses[company_name])
            if st.button("🔄 다시 분석하기"):
                del st.session_state.analyses[company_name]
                st.rerun()
        else:
            if st.button(f"🚀 {company_name} 정밀 분석 시작", type="primary"):
                with st.spinner("전문가 모드로 살림살이와 시장 동향을 파악 중입니다..."):
                    # 1. 실제 재무 데이터 추출 (최근 연간 실적)
                    try:
                        income_stmt = stock_info.income_stmt.iloc[:, :3] # 최근 3년
                        financial_summary = income_stmt.to_string()
                        current_price = stock_info.info.get('currentPrice', '데이터 없음')
                        target_low = stock_info.info.get('targetLowPrice', '데이터 없음')
                        target_mean = stock_info.info.get('targetMeanPrice', '데이터 없음')
                    except:
                        financial_summary = "재무 데이터를 직접 가져오지 못했습니다. 검색 결과를 참고합니다."
                        current_price = "확인 중"
                        target_mean = "확인 중"

                    # 2. 강화된 프롬프트
                    prompt = f"""
                    당신은 50대 주식 투자자를 위한 친절한 수석 애널리스트입니다. 
                    '{company_name}'({ticker_code})에 대해 다음 4가지 핵심 영역을 정밀 분석해 주세요.

                    [데이터 참고 정보]
                    - 현재 주가: {current_price}
                    - 최근 재무제표 요약:
                    {financial_summary}

                    [요청 사항]
                    1. **재무제표의 진실**: 제공된 수치를 바탕으로 매출과 이익이 실제로 늘고 있는지 분석하세요. '살림살이' 비유를 곁들여 "돈을 진짜로 벌고 있는 회사인가?"를 명확히 답하세요.
                    2. **큰손들의 움직임 (외국인/기관/공매도)**: 최근 이 회사를 외국인과 기관이 사고 있는지, 아니면 팔고 있는지 검색하여 알려주세요. 특히 '공매도(나중에 떨어질 걸 기대하고 미리 파는 세력)'가 많은지도 주부의 눈높이에서 "동네 소문이나 시장 분위기"에 비유해 설명하세요.
                    3. **목표 주가 비교**: 금융기관(증권사)들이 제시하는 평균 목표가({target_mean})를 언급하고, 당신(제미나이)이 판단하는 이 회사의 미래 가치를 고려한 '제미나이 목표가'를 조심스럽게 제시해 주세요.
                    4. **신호등 및 한줄평**: 🟢/🟡/🔴 기호와 함께 구체적인 투자 전략을 제시하세요.

                    [출력 형식]
                    ### 🚦 한눈에 보는 신호등
                    ### 💰 1. 수치로 보는 살림살이 (재무제표)
                    ### 👥 2. 누가 사고 있나요? (외국인/기관/공매도 동향)
                    ### 🎯 3. 얼마까지 갈까요? (목표 주가 비교)
                    ### 💡 엄마를 위한 최종 조언
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
            fig.update_layout(template="plotly_white", margin=dict(l=20, r=20, t=20, b=20),
                              font=dict(size=18), hovermode='x unified')
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