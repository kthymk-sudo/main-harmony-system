# main.py
import streamlit as st
from config import init_session_state
from ui.upload_panel import render_upload_panel
from ui.analysis_panel import render_analysis_panel
from ui.almind_panel import render_almind_panel

# ==========================================
# ⚙️ 1. 시스템 초기 설정 
# ==========================================
st.set_page_config(page_title="하모니 투트랙 분석 시스템", page_icon="🏢", layout="wide")
init_session_state()

# ==========================================
# 🖥️ 2. 메인 UI 화면 조립 및 실행 (상단 메뉴 바 배치)
# ==========================================
st.title("🏢 하모니팀 통합 시스템")

# [핵심 변경] 업무 자동화 탭 전환 창을 사이트 최상단에 가로형으로 배치
current_tab = st.radio(
    "📂 작업 메뉴 선택",
    ("📊 실적 DB 분석 시스템", "🌳 AI 알마인드 요약 보드"),
    horizontal=True,
    label_visibility="collapsed" # 디자인을 위해 불필요한 라벨은 숨김
)

st.divider()

# --- 분기 1: 실적 DB 분석 시스템 ---
if current_tab == "📊 실적 DB 분석 시스템":
    # 상단: 데이터베이스 로딩 및 신규 엑셀 누적
    render_upload_panel()
    
    # 하단: 데이터가 로드된 경우에만 분석 대시보드 렌더링
    if st.session_state.get('loaded'):
        render_analysis_panel()

# --- 분기 2: AI 알마인드 요약 보드 ---
elif current_tab == "🌳 AI 알마인드 요약 보드":
    render_almind_panel()