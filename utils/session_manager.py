# utils/session_manager.py
import streamlit as st
import json  # 🌟 추가 (로컬 파일 저장용)
import os    # 🌟 추가 (파일 존재 여부 확인용)

def safe_set(m_key, w_key):
    if w_key in st.session_state: 
        st.session_state.persist[m_key][w_key] = st.session_state[w_key]

def restore_state(m_key, w_key):
    if w_key in st.session_state.persist[m_key] and w_key not in st.session_state:
        st.session_state[w_key] = st.session_state.persist[m_key][w_key]

# =====================================================================
# 🌟 [선제적 모듈화] 알마인드 키워드 가이드라인 커스텀 프리셋 (영구 보존 엔진)
# =====================================================================
PRESET_FILE = "presets.json"  # exe 파일 옆에 생성될 프리셋 저장 파일명

def initialize_keyword_presets():
    """앱 최초 실행 시 로컬 파일(presets.json)에서 영구 저장된 프리셋을 불러옵니다."""
    if 'keyword_presets' not in st.session_state:
        st.session_state.keyword_presets = {}
        # 로컬 백업 파일이 존재하면 읽어서 세션에 복구
        if os.path.exists(PRESET_FILE):
            try:
                with open(PRESET_FILE, "r", encoding="utf-8") as f:
                    st.session_state.keyword_presets = json.load(f)
            except Exception as e:
                st.error(f"프리셋 파일을 불러오는 중 오류가 발생했습니다: {e}")

def save_custom_preset(name, content):
    """새로운 분류 지침을 세션에 저장하고, 즉시 로컬 파일로 영구 백업합니다."""
    if name.strip() and content.strip():
        st.session_state.keyword_presets[name.strip()] = content.strip()
        _save_to_file()  # 🌟 저장할 때마다 파일 업데이트
        return True
    return False

def delete_preset(name):
    """기존 프리셋을 세션에서 제거하고, 로컬 파일에도 삭제를 반영합니다."""
    if name in st.session_state.keyword_presets:
        del st.session_state.keyword_presets[name]
        _save_to_file()  # 🌟 삭제할 때마다 파일 업데이트
        return True
    return False

def _save_to_file():
    """(내부 자동 실행) 현재 세션의 프리셋을 로컬 JSON 파일로 덮어씁니다."""
    try:
        with open(PRESET_FILE, "w", encoding="utf-8") as f:
            # ensure_ascii=False : 한글이 깨지지 않고 온전히 저장되도록 방어
            json.dump(st.session_state.keyword_presets, f, ensure_ascii=False, indent=4)
    except Exception as e:
        st.error(f"프리셋 영구 저장 중 오류가 발생했습니다: {e}")