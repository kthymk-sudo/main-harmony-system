# ai_engine/gemini_api.py
import requests
import time
import streamlit as st
from config import GEMINI_API_KEY
from prompts.push_prompt import get_push_prompt
from prompts.almind_prompt import get_almind_prompt
from prompts.analysis_prompt import get_analysis_prompt
from utils.response_parser import parse_almind_response

# =====================================================================
# 🌟 [선제적 모듈화] AI 코어 엔진: 3개 함수의 중복 로직을 하나로 통합!
# =====================================================================
def _call_gemini_api(prompt, temperature=0.55):
    """Google Gemini API 호출, 예외 처리, Timeout, 재시도를 모두 담당하는 코어 함수"""
    if GEMINI_API_KEY == "여기에_발급받으신_GEMINI_API_KEY를_붙여넣으세요" or not GEMINI_API_KEY:
        return "⚠️ 시스템 은닉형 API 키가 설정되지 않았습니다. .env 또는 config 설정을 확인하세요."
        
    if not (GEMINI_API_KEY.startswith("AIza") or GEMINI_API_KEY.startswith("AQ.")):
        return "⚠️ 입력하신 API 키의 형식이 올바르지 않습니다."

    try:
        # 1. 사용 가능한 최신 모델 동적 검색
        target_model = "models/gemini-1.5-flash"
        url_models = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_API_KEY}"
        
        # 모델 검색은 중요도가 낮으므로 에러 시 무시하고 기본 모델 사용 (timeout 5초)
        try:
            res_models = requests.get(url_models, timeout=5)
            if res_models.status_code == 200:
                available_models = [m['name'] for m in res_models.json().get('models', []) if 'generateContent' in m.get('supportedGenerationMethods', [])]
                for m in available_models:
                    if 'flash' in m.lower():
                        target_model = m
                        break
        except requests.exceptions.RequestException:
            pass # 통신 지연 시 기본 모델(1.5-flash)로 강제 진행

        # 2. 본 요청 실행 (재시도 및 Timeout 방어막 적용)
        url_generate = f"https://generativelanguage.googleapis.com/v1beta/{target_model}:generateContent?key={GEMINI_API_KEY}"
        payload = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": temperature}}
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # 🌟 [방어막] timeout=30 강제 적용으로 무한 로딩 원천 차단
                res_gen = requests.post(url_generate, headers={"Content-Type": "application/json"}, json=payload, timeout=90)
                
                if res_gen.status_code == 200:
                    return res_gen.json()['candidates'][0]['content']['parts'][0]['text']
                    
                # 429(할당량 초과) 및 500번대(서버 에러) 발생 시 지수 백오프(Exponential Backoff) 대기 후 재요청
                elif res_gen.status_code in [429, 500, 503]:
                    if attempt < max_retries - 1:
                        time.sleep((2 ** attempt) + 1)
                        continue
                    else:
                        return f"⚠️ [서버 과부하] 구글 AI 서버가 혼잡합니다. 잠시 후 [🔄 새로고침] 버튼을 눌러주세요. (상태코드: {res_gen.status_code})"
                else:
                    return f"⚠️ API 요청 거부 ({res_gen.status_code}): {res_gen.text}"
                    
            except requests.exceptions.RequestException as req_e:
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                return f"⚠️ 네트워크 통신 오류(Timeout 등): {str(req_e)}"
                
    except Exception as e:
        return f"⚠️ 시스템 통신 중 치명적 오류 발생: {str(e)}"

# =====================================================================
# 🚀 3가지 개별 서비스 함수 (코어 엔진 호출)
# =====================================================================
@st.cache_data(show_spinner=False)
def generate_ai_push_copy(filtered_df):
    try:
        top_videos = filtered_df['영상명'].value_counts().head(10).index.tolist()
        top_channels = filtered_df['채널명'].value_counts().head(5).index.tolist()
        prompt = get_push_prompt(top_videos, top_channels)
        
        # 코어 엔진 호출 (푸시 카피는 창의성이 필요하므로 온도 0.7)
        return _call_gemini_api(prompt, temperature=0.7)
    except Exception as e:
        return f"데이터 분석 중 오류 발생: {str(e)}"

@st.cache_data(show_spinner=False)
def generate_ai_pivot_briefing(data_str, title, global_stats_str=""):
    max_chars = 30000
    if len(data_str) > max_chars:
        data_str = data_str[:max_chars] + "\n\n...[데이터 용량 초과로 이하 생략됨. 상위 핵심 데이터만으로 분석을 진행합니다]..."
        
    prompt = get_analysis_prompt(title, global_stats_str, data_str)
    # 코어 엔진 호출 (분석은 팩트 기반이므로 온도 0.55)
    return _call_gemini_api(prompt, temperature=0.55)

@st.cache_data(show_spinner=False)
def generate_almind_summary(masked_text, db_context_str=""):
    max_chars = 30000
    if len(masked_text) > max_chars:
        masked_text = masked_text[:max_chars] + "\n\n...[텍스트가 너무 길어 시스템 보호를 위해 뒷부분이 생략되었습니다]..."
        
    prompt = get_almind_prompt(masked_text, db_context_str)
    
    # 코어 엔진 호출 (알마인드 요약은 구조화가 중요하므로 온도 0.4)
    result_text = _call_gemini_api(prompt, temperature=0.4)
    
    if result_text.startswith("⚠️"):
        return "API 호출 오류", result_text
        
    try:
        almind_part, feedback_part = parse_almind_response(result_text)
        return almind_part, feedback_part
    except Exception as e:
        return "파싱 오류", f"응답을 알마인드 형식으로 변환하는데 실패했습니다: {str(e)}"