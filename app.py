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
import email.utils # 날짜 정렬을 위해 추가

# 1. 페이지 설정
st.set_page_config(page_title="엄마표 주식 투자 가이드", page_icon="🛒", layout="wide")
# 1. 페이지 설정 (기존 코드)
st.set_page_config(page_title="엄마표 주식 투자 가이드", page_icon="🛒", layout="wide")

# --- 🪄 어머니를 위한 돋보기 기능 (전체 글씨 크기 키우기) ---
st.markdown("""
<style>
/* 본문 및 일반 텍스트 크기 */
.stMarkdown p, .stMarkdown li {
    font-size: 18px !important;
    line-height: 1.8 !important; /* 줄 간격을 넓혀서 읽기 편하게 */
}

/* 버튼 텍스트 크기 및 굵기 */
.stButton button {
    font-size: 18px !important;
    font-weight: bold !important;
}

/* 입력창 및 검색창(Selectbox) 텍스트 크기 */
.stTextInput input, .stSelectbox div[data-baseweb="select"] {
    font-size: 18px !important;
}

/* 탭(분석, 차트, 뉴스) 텍스트 크기 */
.stTabs [data-baseweb="tab"] {
    font-size: 18px !important;
    font-weight: bold !important;
}

/* 사이드바 텍스트 크기 */
[data-testid="stSidebar"] p {
    font-size: 16px !important;
}
</style>
""", unsafe_allow_html=True)
# --------------------------------------------------------

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
    df_krx = fdr.StockListing('KRX')
    df_krx['display_name'] = df_krx['Name'] + " (" + df_krx['Code'] + ")"
    return df_krx[['display_name', 'Code', 'Name', 'Market']]

stock_df = get_stock_list()

# 4. 세션 상태 초기화 (검색 기록 및 분석 결과 저장용)
if "history" not in st.session_state:
    st.session_state.history = []
if "analyses" not in st.session_state:
    st.session_state.analyses = {}

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
    st.info("💡 창을 닫기 전까지 기록이 유지되도록 만들었습니다.")

# --- 메인 화면 ---
st.title("🛒 엄마표 주식 투자 가이드")

# 자동 완성 검색창
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
    
    market = row['Market']
    suffix = ".KQ" if market == 'KOSDAQ' else ".KS"
    full_ticker = ticker_code + suffix

    if company_name not in st.session_state.history:
        st.session_state.history.append(company_name)

    # 탭 구성
    tab1, tab2, tab3 = st.tabs(["📋 엄마표 분석", "📈 주가 그래프", "📰 최신 뉴스"])

    with tab1:
        if company_name in st.session_state.analyses:
            st.markdown(st.session_state.analyses[company_name])
            if st.button("🔄 최신 내용으로 다시 분석하기"):
                del st.session_state.analyses[company_name]
                st.rerun()
        else:
            if st.button(f"{company_name} 분석 시작하기", type="primary"):
                with st.spinner("살림살이를 꼼꼼히 살피는 중..."):
                    prompt = f"'{company_name}'(종목코드: {ticker_code})에 대해 50대 주부 눈높이에서 재무상태(살림살이), 경제상황(바깥경기), 실적(성적표)을 분석해줘. 3줄요약, 신호등 표시, 한 줄 조언을 포함해줘."
                    response = model.generate_content(prompt)
                    
                    if response.parts:
                        st.session_state.analyses[company_name] = response.text
                        st.rerun()
                    else:
                        st.warning("⚠️ 해당 종목에 대한 응답이 안전 필터에 의해 차단되었습니다.")

    with tab2:
        st.subheader(f"📊 {company_name} 주가 흐름")
        period_map = {"1일": "1d", "1주": "5d", "1달": "1mo", "1년": "1y", "5년": "5y"}
        # 수정 1: index=3 을 추가하여 '1년'이 기본으로 선택되도록 설정
        selected_period = st.radio("기간 선택", list(period_map.keys()), index=3, horizontal=True)
        
        data = yf.download(full_ticker, period=period_map[selected_period])
        if not data.empty:
            close = data['Close']
            if isinstance(close, pd.DataFrame):
                close = close.iloc[:, 0]
            fig = go.Figure(data=[go.Scatter(x=data.index, y=close, line=dict(color='#FF4B4B'))])
            fig.update_layout(template="plotly_white", margin=dict(l=20, r=20, t=20, b=20))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.write("주가 정보를 불러올 수 없습니다. (신규 상장 종목이거나 일시적 오류일 수 있습니다)")

    with tab3:
        st.subheader(f"🗞️ {company_name} 소식")
        try:
            encoded_query = urllib.parse.quote(f"{company_name} 주식")
            url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ko&gl=KR&ceid=KR:ko"
            
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            response = urllib.request.urlopen(req)
            root = ET.fromstring(response.read())
            items = root.findall('.//item')
            
            if items:
                news_list = []
                # 수정 2: 날짜 형식 변환 및 정렬을 위한 리스트 생성
                for item in items:
                    title = item.find('title').text
                    link = item.find('link').text
                    pub_date_str = item.find('pubDate').text
                    
                    # 문자열 날짜를 datetime 객체로 변환
                    pub_date_obj = email.utils.parsedate_to_datetime(pub_date_str)
                    
                    news_list.append({
                        'title': title,
                        'link': link,
                        'date_obj': pub_date_obj
                    })
                
                # 최신 날짜 순(내림차순)으로 정렬
                news_list.sort(key=lambda x: x['date_obj'], reverse=True)
                
                for news in news_list[:5]: # 최신 5개 기사만 표시
                    st.write(f"🔗 [{news['title']}]({news['link']})")
                    # GMT 시간을 한국 시간(KST)으로 변환 후 깔끔하게 표시 (+9시간)
                    kst_date = news['date_obj'] + timedelta(hours=9)
                    st.caption(f"발행일: {kst_date.strftime('%Y년 %m월 %d일 %H:%M')}")
            else:
                st.write("최근 뉴스 데이터가 없습니다.")
        except Exception as e:
            st.write("뉴스 데이터를 불러오는 중 오류가 발생했습니다.")

else:
    st.write("분석할 회사를 위 검색창에서 선택해 주세요!")