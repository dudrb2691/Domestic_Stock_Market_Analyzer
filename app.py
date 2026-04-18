import streamlit as st
import google.generativeai as genai
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import FinanceDataReader as fdr
from datetime import datetime, timedelta

# 1. 페이지 설정
st.set_page_config(page_title="엄마표 주식 투자 가이드", page_icon="🛒", layout="wide")

# 2. API 및 모델 설정 (Secrets 활용)
try:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-3-flash-preview')
except KeyError:
    st.error("🔒 'GEMINI_API_KEY'가 설정되지 않았습니다.")
    st.stop()

# 3. 데이터 캐싱 - 상장사 목록 불러오기 (자동완성용)
@st.cache_data
def get_stock_list():
    # 한국 거래소 종목 리스트 (KOSPI, KOSDAQ)
    df_krx = fdr.StockListing('KRX')
    # "종목명 (티커)" 형식으로 리스트 생성
    df_krx['display_name'] = df_krx['Name'] + " (" + df_krx['Code'] + ")"
    return df_krx[['display_name', 'Code', 'Name', 'Market']]

stock_df = get_stock_list()

# 4. 세션 상태 초기화
if "history" not in st.session_state:
    st.session_state.history = []

# --- 사이드바: 즐겨찾기 및 이전 기록 ---
with st.sidebar:
    st.header("⭐ 나의 관심 목록")
    user_name = st.text_input("사용자 이름을 입력하세요 (예: 엄마)", value="엄마")
    st.caption(f"{user_name}님의 검색 기록이 이번 세션 동안 유지됩니다.")
    
    if st.session_state.history:
        st.write("🕒 최근 본 종목")
        for h_item in reversed(st.session_state.history[-5:]):
            st.markdown(f"- 🔍 {h_item}")
    st.markdown("---")
    st.info("💡 Gmail 연동은 보안 설정이 복잡하여, 현재는 창을 닫기 전까지 기록이 유지되도록 만들었습니다.")

# --- 메인 화면 ---
st.title("🛒 엄마표 주식 투자 가이드")

# 기능 2: 자동 완성 검색창
selected_display = st.selectbox(
    "🔍 궁금한 회사 이름을 입력해 보세요",
    options=[""] + stock_df['display_name'].tolist(),
    format_func=lambda x: "회사명을 선택하세요" if x == "" else x,
    help="한 글자만 입력해도 관련 회사가 모두 나옵니다."
)

if selected_display:
    # 선택된 정보 추출
    row = stock_df[stock_df['display_name'] == selected_display].iloc[0]
    ticker_code = row['Code']
    company_name = row['Name']
    # 한국 주식은 티커 뒤에 .KS(코스피) 또는 .KQ(코스닥)가 필요
    market = row['Market']
    suffix = ".KQ" if market == 'KOSDAQ' else ".KS"
    full_ticker = ticker_code + suffix

    if company_name not in st.session_state.history:
        st.session_state.history.append(company_name)

    # 탭 구성 (분석, 차트, 뉴스)
    tab1, tab2, tab3 = st.tabs(["📋 엄마표 분석", "📈 주가 그래프", "📰 최신 뉴스"])

    with tab1:
        if st.button(f"{company_name} 분석 시작하기", type="primary"):
            with st.spinner("살림살이를 꼼꼼히 살피는 중..."):
                prompt = f"'{company_name}'(종목코드: {ticker_code})에 대해 50대 주부 눈높이에서 재무상태(살림살이), 경제상황(바깥경기), 실적(성적표)을 분석해줘. 3줄요약, 신호등 표시, 한 줄 조언을 포함해줘."
                response = model.generate_content(prompt)
                if response.parts:
                    st.markdown(response.text)
                else:
                    st.warning("⚠️ 해당 종목에 대한 응답이 안전 필터에 의해 차단되었습니다.")

    with tab2:
        # 기능 1: 주가 그래프 (기간 선택)
        st.subheader(f"📊 {company_name} 주가 흐름")
        period_map = {"1일": "1d", "1주": "5d", "1달": "1mo", "1년": "1y", "5년": "5y"}
        selected_period = st.radio("기간 선택", list(period_map.keys()), horizontal=True)
        
        data = yf.download(full_ticker, period=period_map[selected_period])
        if not data.empty:
            close = data['Close']
            if isinstance(close, pd.DataFrame):
                close = close.iloc[:, 0]
            fig = go.Figure(data=[go.Scatter(x=data.index, y=close, line=dict(color='#FF4B4B'))])
            fig.update_layout(template="plotly_white", margin=dict(l=20, r=20, t=20, b=20))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.write("주가 정보를 불러올 수 없습니다. (코스닥 종목인 경우 .KQ를 확인해야 합니다)")

    with tab3:
        # 기능 3: 최신 뉴스 표시
        st.subheader(f"🗞️ {company_name} 소식")
        stock_info = yf.Ticker(full_ticker)
        try:
            news = stock_info.news
            # yfinance 버전에 따라 뉴스 구조가 다를 수 있음
            if isinstance(news, dict):
                news = news.get('news', [])
            if news:
                for item in news[:5]:
                    title = item.get('title', '제목 없음')
                    link = item.get('link', item.get('url', '#'))
                    publisher = item.get('publisher', '알 수 없음')
                    pub_time = item.get('providerPublishTime')
                    st.write(f"🔗 [{title}]({link})")
                    if pub_time:
                        st.caption(f"출처: {publisher} | 발행일: {datetime.fromtimestamp(pub_time)}")
                    else:
                        st.caption(f"출처: {publisher}")
            else:
                st.write("최근 뉴스 데이터가 없습니다.")
        except Exception:
            st.write("뉴스 데이터를 불러올 수 없습니다.")

else:
    st.write("분석할 회사를 위 검색창에서 선택해 주세요!")