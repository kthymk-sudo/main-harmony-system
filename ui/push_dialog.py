# ui/push_dialog.py
import streamlit as st
import pandas as pd
from ai_engine.gemini_api import generate_ai_push_copy
from utils.formatters import convert_raw_df_to_excel
from utils.data_cleaner import fill_zero_id

@st.dialog("🎯 앱 푸시 발송용 타겟 명단 추출 및 AI 카피", width="large")
def open_push_extractor_dialog(current_filtered_df):
    st.info("💡 사이드바에서 필터링된 시청자 명단(R고객번호)을 '캠페인 업로드 양식'에 맞춰 즉시 추출하고, 맞춤형 앱 푸시 문구를 AI로 생성합니다.")
    
    # 1. 엑셀 다운로드용 명단 추출 (단일 컬럼)
    target_ids = current_filtered_df['R고객번호'].dropna().unique().tolist()
    if not target_ids:
        st.warning("⚠️ 현재 필터링된 데이터에 일치하는 R고객번호가 없습니다.")
        return
        
    with st.spinner("명단을 추출하여 엑셀 파일을 준비 중입니다..."):
        matched_df = pd.DataFrame({'R-고객번호': target_ids})
        matched_df['R-고객번호'] = fill_zero_id(matched_df['R-고객번호'])
        
    # 2. 화면 미리보기용 명단 가공 (상세 정보 포함 및 인덱스 1부터 시작)
    preview_cols = ['R고객번호', '이웃고객명', '성별', '나이', '시청자SO']
    # 혹시 누락된 컬럼이 있을 경우를 대비한 안전망 (존재하는 컬럼만 선택)
    available_cols = [col for col in preview_cols if col in current_filtered_df.columns]
    
    # 중복 고객 제거 후 상세 데이터만 남기기
    view_counts = current_filtered_df['R고객번호'].value_counts()
    preview_df = current_filtered_df.drop_duplicates(subset=['R고객번호'], keep='last')[available_cols]
    preview_df['시청이력_수'] = preview_df['R고객번호'].map(view_counts)

    # 인덱스(순번)를 깔끔하게 리셋하고 1부터 시작하도록 설정
    preview_df = preview_df.reset_index(drop=True)
    preview_df.index = preview_df.index + 1
        
    st.success(f"✅ 총 **{len(target_ids):,}명**의 필터링된 시청자 명단이 캠페인 업로드 양식으로 추출되었습니다!")
    
    btn_col1, btn_col2 = st.columns(2)
    with btn_col1:
        st.download_button(
            label="📥 캠페인 업로드 양식 엑셀 다운로드", 
            data=convert_raw_df_to_excel(matched_df), 
            file_name="campaign_upload_target.xlsx", 
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="push_download_btn",
            use_container_width=True
        )
    with btn_col2:
        if st.button("✨ Gemini AI 맞춤형 카피 생성", use_container_width=True):
            with st.spinner("Google Gemini가 타겟 데이터를 분석하여 최적의 푸시 카피를 작성 중입니다..."):
                ai_result = generate_ai_push_copy(current_filtered_df)
            st.session_state['ai_copy_result'] = ai_result
    
    if 'ai_copy_result' in st.session_state:
        st.markdown("#### 🤖 AI 추천 맞춤형 카피라이팅")
        st.info(st.session_state['ai_copy_result'])
        
    st.markdown("---")
    st.markdown("##### 🔍 추출된 타겟 명단 미리보기 (상세 정보)")
    # 미리보기는 새로 만든 preview_df를 보여주도록 변경
    st.dataframe(preview_df.head(100), use_container_width=True)