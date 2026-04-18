import streamlit as st
import google.generativeai as genai

# 1. 페이지 기본 설정
st.set_page_config(
    page_title="엄마표 주식 투자 가이드",
    page_icon="🛒",
    layout="centered"
)

# 2. 세션 상태 초기화 (분석 결과 유지용)
if "analysis_result" not in st.session_state:
    st.session_state.analysis_result = None
if "analyzed_company" not in st.session_state:
    st.session_state.analyzed_company = None

# 3. UI 헤더 구성
st.title("🛒 엄마표 주식 투자 가이드")
st.markdown("""
어렵고 복잡한 주식 이야기, **장바구니 물가 확인하듯** 쉽고 편안하게 풀어드려요!  
궁금한 회사 이름을 입력하시면 우리 집 살림살이에 비유해서 꼼꼼히 분석해 드립니다.
""")

# 4. 사이드바 - API 키 입력란 (보안 및 편의성)
with st.sidebar:
    st.header("⚙️ 설정")
    api_key = st.text_input("Gemini API 키를 입력해 주세요", type="password")
    st.markdown("[API 키 발급받기 (Google AI Studio)](https://aistudio.google.com/app/apikey)")
    st.caption("※ API 키는 저장되지 않으며 툴 실행에만 사용됩니다.")

# 5. 메인 화면 - 종목 입력
st.markdown("---")
company_name = st.text_input("🔍 궁금한 국내 주식 종목명을 입력해 주세요 (예: 삼성전자, 현대차)", placeholder="여기에 종목명을 입력하세요")

# 6. 분석 실행 버튼 및 로직
if st.button("분석 시작하기", type="primary"):
    if not api_key:
        st.error("👈 좌측 사이드바에 Gemini API 키를 먼저 입력해 주세요!")
    elif not company_name:
        st.warning("종목명을 입력해 주세요!")
    else:
        try:
            # Gemini API 설정
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-3-flash-preview', system_instruction=persona)

            # 기획하신 프롬프트를 시스템 지시어 형태로 재구성
            prompt = f"""
            당신은 50대 주식 초보자(주부)의 눈높이에 맞춰 친절하고 알기 쉽게 주식을 설명해 주는 다정한 금융 전문가입니다.
            사용자가 검색한 국내 주식 종목: '{company_name}'에 대해 아래의 지침과 구조에 맞추어 완벽한 보고서를 작성해 주세요.

            [분석 지침]
            1. "이 회사, 살림살이 튼튼한가요?" (재무 상태 분석)
               - 부채비율, 유보율 대신 '통장 잔고', '빚', '비상금' 같은 가정집 살림에 비유해서 설명하세요.
               - 주부 입장에서 이 회사가 망하지 않고 배당금이나 수익을 줄 만큼 튼실한 '부자 회사'인지 딱 잘라 말해 주세요.
            2. "요즘 바깥 경기가 이 회사에 도움 되나요?" (경제 지표 분석)
               - 금리, 환율, 유가 등 최근 경제 상황이 이 회사에게 호재인지 악재인지 아주 쉽게 설명하세요.
               - 재료비가 오르는지, 물건 팔 때 이득을 보는지 등을 일상 언어로 연결해 주세요.
            3. "이번에 성적표(실적 발표) 잘 나왔나요?" (실적 발표 요약)
               - 최근 실적을 '학교 성적표'처럼 요약해 주세요.
               - 지난번보다 점수가 올랐는지, 시장(선생님)에게 혼나고 있는지 설명하세요.
               - 가장 칭찬받을 만한 점 1개와 조심해야 할 '주의사항' 1개를 콕 집어주세요.

            [출력 형식 (반드시 아래 마크다운 구조를 지켜서 출력하세요)]
            
            ### 📌 3줄 요약
            (전체적인 상황을 가장 먼저 3줄의 글머리 기호로 요약)

            ### 🚦 현재 상태 
            (🟢 맑음/안심, 🟡 흐림/주의, 🔴 비/위험 중 현재 상태에 맞는 기호를 하나만 크게 표시하고, 그 이유를 짧게 1~2문장으로 설명)

            ### 🏠 1. 이 회사, 살림살이 튼튼한가요?
            (내용)

            ### 🌍 2. 요즘 바깥 경기가 이 회사에 도움 되나요?
            (내용)

            ### 📝 3. 이번에 성적표 잘 나왔나요?
            (내용)

            ### 💡 한 줄 조언
            (구체적인 행동 지침: 예 - "지금은 좀 더 기다려보세요", "조금씩 모아가도 좋은 시기입니다" 등)
            """

            # 로딩 스피너 표시
            with st.spinner(f"'{company_name}'의 살림살이와 성적표를 꼼꼼히 분석하고 있습니다... 돋보기 쓰는 중 🔍"):
                response = model.generate_content(prompt)

            # 안전 필터 차단 여부 확인
            if not response.parts:
                st.warning("⚠️ 해당 종목에 대한 응답이 안전 필터에 의해 차단되었습니다. 다른 종목명을 시도해 주세요.")
            else:
                # 세션 상태에 결과 저장
                st.session_state.analysis_result = response.text
                st.session_state.analyzed_company = company_name

        except Exception as e:
            st.error(f"데이터를 불러오는 중 오류가 발생했습니다: {e}")
            st.info("API 키가 정확한지, 또는 일시적인 네트워크 오류가 아닌지 확인해 주세요.")

# 7. 저장된 분석 결과 표시 (페이지 재실행 시에도 유지)
if st.session_state.analysis_result:
    st.success(f"'{st.session_state.analyzed_company}' 분석이 완료되었습니다!")
    st.markdown("---")
    st.markdown(st.session_state.analysis_result)