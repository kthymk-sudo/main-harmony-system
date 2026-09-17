# ui/upload_panel.py
import streamlit as st
import pandas as pd
import io
import os
import datetime
from database.db_manager import upsert_to_db, load_from_db, process_core_databases
from utils.data_cleaner import clean_df1, clean_df2, clean_df3
from config import DB_PATH

# 🌟 [선제적 모듈화] 파일을 하나씩 안전하게 읽고 빈 파일은 걸러내는 헬퍼 함수
def safe_concat_files(file_list):
    valid_dfs = []
    for f in file_list:
        try:
            df = pd.read_excel(io.BytesIO(f.getvalue()))
            if not df.empty:
                valid_dfs.append(df)
        except Exception as e:
            st.warning(f"⚠️ '{f.name}' 파일을 읽는 중 오류가 발생하여 건너뛰었습니다. (사유: {e})")
            
    if valid_dfs:
        # ignore_index=True를 주어 기존 엑셀들의 인덱스가 꼬이지 않도록 완벽하게 합칩니다.
        return pd.concat(valid_dfs, ignore_index=True)
    return None

def render_upload_panel():
    if st.session_state.get('loaded', False) and not st.session_state.get('edit_mode', False):
        if st.button("⚙️ 분석 기간 및 DB 다시 설정하기", use_container_width=True):
            st.session_state['edit_mode'] = True
            st.rerun()
        return
    
    with st.expander("📂 데이터베이스 관리 및 분석 기간 설정", expanded=True):
        tab_load, tab_update = st.tabs(["🚀 데이터 불러오기 및 분석", "📥 신규 엑셀 누적 (단독/다중 업로드 지원)"])

        with tab_update:
            st.info("💡 업데이트하고 싶은 항목에만 엑셀 파일을 여러 개 드래그 앤 드롭하세요. 빈칸은 무시되고 올린 파일만 DB에 누적됩니다.")
            c1, c2, c3 = st.columns(3)
            f1_list = c1.file_uploader("1번: 콘텐츠 통계 (다중)", type=['xlsx'], accept_multiple_files=True)
            f2_list = c2.file_uploader("2번: 월별 시청이력 (다중)", type=['xlsx'], accept_multiple_files=True)
            f3_list = c3.file_uploader("3번: 임직원 목록 (다중)", type=['xlsx'], accept_multiple_files=True)
            
            if f1_list or f2_list or f3_list:
                if st.button("💾 업로드한 데이터만 분리 정제 및 DB 누적", use_container_width=True):
                    with st.spinner("데이터를 정제하여 DB에 안전하게 누적 중입니다... (데이터 크기에 따라 수 초 소요될 수 있습니다)"):
                        df1_clean, df2_clean, df3_clean = None, None, None
                        
                        # 🌟 [방어막 적용] 강제 concat 대신 safe_concat_files 함수로 무결성 병합 진행
                        if f1_list:
                            df1_raw = safe_concat_files(f1_list)
                            if df1_raw is not None: df1_clean = clean_df1(df1_raw)
                            
                        if f2_list:
                            df2_raw = safe_concat_files(f2_list)
                            if df2_raw is not None: df2_clean = clean_df2(df2_raw)
                            
                        if f3_list:
                            df3_raw = safe_concat_files(f3_list)
                            if df3_raw is not None: df3_clean = clean_df3(df3_raw)
                            
                        upsert_to_db(df1_clean, df2_clean, df3_clean)
                        st.success("✅ 선택하신 항목의 DB 누적이 완료되었습니다! 이제 왼쪽 탭에서 [불러오기]를 실행하세요.")

        with tab_load:
            st.markdown("#### 📅 분석 기간 독립 설정")
            date_col1, date_col2 = st.columns(2)
            with date_col1:
                with st.container(border=True):
                    use_reg_date = st.checkbox("🎬 [영상 등록일] 필터 적용", value=False)
                    rc1, rc2 = st.columns(2)
                    reg_start_date = rc1.date_input("등록일 시작", datetime.date(2023, 1, 1), disabled=not use_reg_date)
                    reg_end_date = rc2.date_input("등록일 종료", datetime.date.today(), disabled=not use_reg_date)

            with date_col2:
                with st.container(border=True):
                    use_view_date = st.checkbox("👀 [시청자 시청일] 필터 적용", value=True)
                    vc1, vc2 = st.columns(2)
                    view_start_date = vc1.date_input("시청일 시작", datetime.date(2023, 1, 1), disabled=not use_view_date)
                    view_end_date = vc2.date_input("시청일 종료", datetime.date.today(), disabled=not use_view_date)

            if st.button("🚀 누적 데이터로 분석 엔진 가동", use_container_width=True):
                if not os.path.exists(DB_PATH):
                    st.error("⚠️ 저장된 데이터베이스가 없습니다. 먼저 [신규 엑셀 누적] 탭에서 파일을 업로드해 주세요.")
                else:
                    with st.spinner("DB 창고에서 수십만 건의 데이터를 0.1초 만에 불러와 가공 중입니다..."):
                        df1_raw, df2_raw, df3_raw = load_from_db()
                        
                        if df1_raw.empty or df2_raw.empty:
                            st.error("⚠️ 필수 데이터(콘텐츠 통계 또는 시청이력)가 DB에 부족하여 분석할 수 없습니다. 신규 엑셀을 추가로 누적해주세요.")
                        else:
                            db_content, db_audience, db_employee = process_core_databases(
                                df1_raw, df2_raw, df3_raw,
                                use_reg_date, reg_start_date, reg_end_date,
                                use_view_date, view_start_date, view_end_date
                            )
                            st.session_state['db_audience'] = db_audience
                            st.session_state['db_content'] = db_content
                            st.session_state['db_employee'] = db_employee
                            st.session_state['loaded'] = True
                            st.success(f"✅ 완벽한 DB 로드 완료! (통계: {len(df1_raw):,}건 / 시청이력: {len(df2_raw):,}건 기준)")
                            
                            st.session_state['edit_mode'] = False
                            st.rerun()