# config.py
import os
import sys
import streamlit as st
from dotenv import load_dotenv

# .env 파일 활성화
load_dotenv()

# 환경변수에서 API 키 불러오기
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# ---------------------------------------------------------
# [핵심 방어막] 데이터베이스 강제 경로 고정 로직
# ---------------------------------------------------------
# 실행 환경(.exe 실행 여부)에 따라 기준 디렉토리 동적 결정
if getattr(sys, 'frozen', False):
    # .exe 단독 실행 파일로 구동 중일 때: .exe 파일이 있는 바로 그 폴더
    base_dir = os.path.dirname(sys.executable)
else:
    # VS Code에서 파이썬 코드로 직접 실행 중일 때: 현재 config.py가 있는 폴더
    base_dir = os.path.dirname(os.path.abspath(__file__))

# 데이터베이스 위치를 언제나 프로그램 메인 루트 폴더로 강제 고정
DB_PATH = os.path.join(base_dir, 'harmony_data.db')
# ---------------------------------------------------------

def init_session_state():
    """Streamlit 세션 상태 초기화"""
    if 'custom_dashboards' not in st.session_state:
        st.session_state.custom_dashboards = []
    if 'persist' not in st.session_state:
        st.session_state.persist = {'db1': {}, 'db2': {}}