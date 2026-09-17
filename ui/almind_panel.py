import streamlit as st
import uuid

from utils.data_cleaner import mask_sensitive_data
from ai_engine.gemini_api import generate_almind_summary
from ui.components.tree_viewer import draw_almind_tree
from ui.components.feedback_card import render_feedback_cards
from utils.session_manager import initialize_keyword_presets, save_custom_preset, delete_preset

def add_main_topic():
    st.session_state.topics_tree.append({'id': str(uuid.uuid4())})

def remove_main_topic(m_idx):
    if len(st.session_state.topics_tree) > 1:
        st.session_state.topics_tree.pop(m_idx)

def reset_topics():
    st.session_state.topics_tree = [{'id': str(uuid.uuid4())}]

# ==========================================
# 메인 렌더링 함수
# ==========================================
def render_almind_panel():
    st.header("🌳 AI 알마인드 요약 보드")
    st.markdown("사내 텍스트를 붙여넣으시면 개인정보가 자동 마스킹된 후 안전하게 AI 분석이 진행됩니다. **DB 데이터는 통계만 참고합니다.**")
    
    if 'topics_tree' not in st.session_state:
        reset_topics()

    # 🌟 프리셋 데이터 창고 최초 가동
    initialize_keyword_presets()

    st.write("") 
    st.subheader("📝 주간 업무 내용 입력")
    
    # 🚀 [UI 콤팩트화] 텍스트 입력창 높이 최소화 및 여백 압축
    for m_idx, m_topic in enumerate(st.session_state.topics_tree):
        m_id = m_topic['id']
        
        with st.container(border=True):
            # [1층] 대주제 제목 & 삭제 버튼
            t_col1, t_col2 = st.columns([8.5, 1.5])
            with t_col1:
                st.text_input("📂 대주제 제목", key=f"m_title_{m_id}", placeholder="📂 대주제 제목을 입력하세요", label_visibility="collapsed")
            with t_col2:
                if len(st.session_state.topics_tree) > 1:
                    st.button("❌ 삭제", key=f"del_m_{m_id}", on_click=remove_main_topic, args=(m_idx,), use_container_width=True)
            
            # [2층] 대주제 본문 (🌟 높이 대폭 축소: 100 -> 68)
            st.text_area("대주제 내용", key=f"m_content_{m_id}", height=68, label_visibility="collapsed", placeholder="대주제 관련 핵심 실무를 자유롭게 서술하세요.")
            
            # [3층] 키워드 지침 & 프리셋 조종석
            st.markdown("<p style='font-size:0.85rem; font-weight:600; color:#555; margin-top: 5px; margin-bottom: 2px;'>🔑 키워드 지침 및 프리셋 관리</p>", unsafe_allow_html=True)
            
            k_col1, k_col2 = st.columns([7.5, 2.5])
            with k_col1:
                # 🌟 지침 칸 역시 불필요한 여백을 빼고 높이 타이트하게 축소 (120 -> 85)
                st.text_area("키워드 지침", key=f"m_keywords_{m_id}", height=85, 
                             placeholder="예) 홍보: 경로당 오프라인 활동 위주\n(AI가 이 지침을 기준으로 본문을 자동 분류합니다.)", 
                             label_visibility="collapsed")
            with k_col2:
                preset_options = ["-- 📥 불러오기 --"] + list(st.session_state.keyword_presets.keys())
                
                def load_preset(t_id=m_id):
                    sel = st.session_state[f"preset_sel_{t_id}"]
                    if sel != "-- 📥 불러오기 --":
                        st.session_state[f"m_keywords_{t_id}"] = st.session_state.keyword_presets[sel]
                        
                st.selectbox("불러오기", preset_options, key=f"preset_sel_{m_id}", on_change=load_preset, kwargs={"t_id": m_id}, label_visibility="collapsed")
                
                st.text_input("새 이름", placeholder="💾 새 프리셋 이름", key=f"new_preset_name_{m_id}", label_visibility="collapsed")
                
                b_col1, b_col2 = st.columns(2)
                with b_col1:
                    if st.button("저장", key=f"save_p_{m_id}", use_container_width=True):
                        name = st.session_state.get(f"new_preset_name_{m_id}", "").strip()
                        content = st.session_state.get(f"m_keywords_{m_id}", "").strip()
                        if name and content:
                            if save_custom_preset(name, content):
                                st.toast(f"'{name}' 저장 완료!", icon="✅")
                                st.rerun()
                        else:
                            st.toast("이름과 지침을 모두 채워주세요.", icon="⚠️")
                with b_col2:
                    if st.button("삭제", key=f"del_p_{m_id}", use_container_width=True):
                        sel = st.session_state[f"preset_sel_{m_id}"]
                        if sel != "-- 📥 불러오기 --":
                            delete_preset(sel)
                            st.toast(f"'{sel}' 삭제 완료!", icon="🗑️")
                            st.rerun()
                        else:
                            st.toast("삭제할 프리셋을 선택하세요.", icon="⚠️")

    # =====================================================================
    # 🌟 [절대 방어] 하단 컨트롤 및 AI 연산 로직 (분석 결과 영구 박제 가드)
    # =====================================================================
    btn_col1, btn_col2, _ = st.columns([2, 2, 6])
    with btn_col1:
        st.button("➕ 대주제 추가하기", on_click=add_main_topic, use_container_width=True)
    with btn_col2:
        st.button("🔄 전체 입력창 초기화", on_click=reset_topics, use_container_width=True)

    st.write("---")
    
    db_context_str = ""
    if st.session_state.get('loaded'):
        st.success("🟢 1번 메뉴에서 로드된 시스템 DB가 연결되었습니다. AI가 피드백 시 이 누적 데이터를 참고합니다.")
        db_content = st.session_state.get('db_content')
        db_audience = st.session_state.get('db_audience')
        stats = []
        if db_content is not None and not db_content.empty:
            total_views = db_content['조회수'].sum() if '조회수' in db_content.columns else 0
            stats.append(f"- 콘텐츠 누적 조회수: {total_views:,.0f}회")
        if db_audience is not None and not db_audience.empty:
            total_audience = db_audience['R고객번호'].nunique() if 'R고객번호' in db_audience.columns else 0
            stats.append(f"- 누적 시청자 수: {total_audience:,.0f}명")
        db_context_str = "\n".join(stats)
    else:
        st.info("🟡 현재 DB가 로드되지 않았습니다. (1번 메뉴에서 DB를 가동하면 AI가 더 정밀한 피드백을 제공합니다.)")
        
    # 🚀 AI 분석 시작 버튼 트리거
    if st.button("🚀 보안 마스킹 및 분석 시작", use_container_width=True, type="primary"):
        combined_raw_text = ""
        for m_idx, m_topic in enumerate(st.session_state.topics_tree):
            m_id = m_topic['id']
            m_title = st.session_state.get(f"m_title_{m_id}", "").strip()
            m_content = st.session_state.get(f"m_content_{m_id}", "").strip()
            m_keywords = st.session_state.get(f"m_keywords_{m_id}", "").strip()
            
            m_name = m_title if m_title else f"대주제 {m_idx+1}"
            
            if m_content or m_keywords:
                topic_str = f"[[ 대주제: {m_name} ]]\n"
                if m_keywords:
                    topic_str += f"  [주요 키워드]: {m_keywords}\n"
                if m_content:
                    indented_m_content = "\n".join([f"  {line}" for line in m_content.split("\n")])
                    topic_str += f"  [대주제 내용]\n{indented_m_content}\n"
                
                combined_raw_text += topic_str + "\n"

        if not combined_raw_text.strip():
            st.warning("분석할 텍스트를 한 칸 이상 입력해 주세요.")
            return
            
        masked_text = mask_sensitive_data(combined_raw_text)
        st.session_state['almind_masked_text_view'] = masked_text
        
        with st.spinner("거시적 구조 요약 및 미시적 피드백 생성 중..."):
            # 🌟 [핀포인트 수술] 새로 추출한 결과를 임시 변수가 아닌 세션 주소에 직접 박제합니다.
            almind_res, feedback_res = generate_almind_summary(masked_text, db_context_str)
            st.session_state['last_almind_result'] = almind_res
            st.session_state['last_feedback_result'] = feedback_res
            st.rerun()

    # =====================================================================
    # 🛡️ [결과 고정 가드] 세션에 분석 결과가 존재한다면 상단 입력 폼 조작과 무관하게 항시 렌더링
    # =====================================================================
    if 'last_almind_result' in st.session_state and 'last_feedback_result' in st.session_state:
        st.divider()
        
        # 이전 마스킹 텍스트 기록 추적 뷰어
        if 'almind_masked_text_view' in st.session_state:
            with st.expander("🔍 AI에게 전송된 텍스트 확인 (마스킹 및 키워드 구조화 완료)"):
                st.text(st.session_state['almind_masked_text_view'])
                
        st.subheader("1️⃣ 거시적 관점: 업무 마인드맵 요약")
        with st.container(border=True):
            draw_almind_tree(st.session_state['last_almind_result'])
            
        with st.expander("📋 알마인드 프로그램에 붙여넣기 (원클릭 복사)", expanded=True):
            st.caption("A박스 우측 상단의 복사 아이콘을 눌러 알마인드 중심 토픽에 Ctrl+V 하세요.")
            st.code(st.session_state['last_almind_result'], language="text")
            
        st.write("") 
        st.subheader("2️⃣ 미시적 관점: 데이터 기반 액션 플랜 (AI 인사이트)")
        render_feedback_cards(st.session_state['last_feedback_result'])