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
# 🌟 [AI 코어 엔진 - 안정성 개선] 연결 재사용 + 모델 자동탐색/자동전환 +
# 429(한도초과)·5xx(서버과부하)·404(모델없음) 원인별 대응을 분리했다.
# =====================================================================
_http_session = requests.Session()

_LATEST_FLASH_ALIAS = "models/gemini-flash-latest"
_AVOID_MODEL_KEYWORDS = ("exp", "preview", "thinking", "image", "audio", "tts", "embedding", "vision", "native")
_EXHAUSTED_MODELS = set()


def _pick_best_flash_model(available_models):
    """'flash'가 들어간 모델 중 "-latest" 별칭(구글이 항상 최신 지원 버전으로 자동
    교체해주는 안전한 이름)을 최우선으로, 그다음 실험/미리보기가 아닌 안정판을
    우선으로 고른다. 이미 한도 초과로 블랙리스트된 모델은 제외한다."""
    valid_models = [m for m in available_models if m not in _EXHAUSTED_MODELS]
    flash_models = [m for m in valid_models if 'flash' in m.lower()]
    latest_alias = next((m for m in flash_models if m.lower().endswith('flash-latest')), None)
    if latest_alias:
        return latest_alias
    stable = [m for m in flash_models if not any(k in m.lower() for k in _AVOID_MODEL_KEYWORDS)]
    candidates = stable or flash_models
    return candidates[0] if candidates else None


@st.cache_data(show_spinner=False, ttl=3600)
def _discover_target_model():
    """사용 가능한 모델 목록은 자주 바뀌지 않으므로 1시간 캐시해서 재사용한다."""
    target_model = _LATEST_FLASH_ALIAS
    url_models = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_API_KEY}"
    try:
        res_models = _http_session.get(url_models, timeout=5)
        if res_models.status_code == 200:
            available_models = [
                m['name'] for m in res_models.json().get('models', [])
                if 'generateContent' in m.get('supportedGenerationMethods', [])
            ]
            picked = _pick_best_flash_model(available_models)
            if picked:
                target_model = picked
    except requests.exceptions.RequestException:
        pass
    return target_model


def _call_gemini_api(prompt, temperature=0.55):
    """Google Gemini API 호출, 예외 처리, Timeout, 재시도, 모델 자동전환을 담당하는 코어 함수."""
    if GEMINI_API_KEY == "여기에_발급받으신_GEMINI_API_KEY를_붙여넣으세요" or not GEMINI_API_KEY:
        return "⚠️ 시스템 은닉형 API 키가 설정되지 않았습니다. .env 또는 config 설정을 확인하세요."

    if not (GEMINI_API_KEY.startswith("AIza") or GEMINI_API_KEY.startswith("AQ.")):
        return "⚠️ 입력하신 API 키의 형식이 올바르지 않습니다."

    try:
        target_model = _discover_target_model()
        payload = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": temperature}}

        max_retries = 3
        max_retries_5xx = 4

        for attempt in range(max(max_retries, max_retries_5xx)):
            url_generate = f"https://generativelanguage.googleapis.com/v1beta/{target_model}:generateContent?key={GEMINI_API_KEY}"
            try:
                res_gen = _http_session.post(url_generate, headers={"Content-Type": "application/json"}, json=payload, timeout=20)

                if res_gen.status_code == 200:
                    try:
                        return res_gen.json()['candidates'][0]['content']['parts'][0]['text']
                    except (KeyError, IndexError, ValueError):
                        return "⚠️ 답변을 생성하지 못했습니다(안전 필터에 의해 차단됐을 수 있어요). 표현을 조금 바꿔 다시 시도해주세요."

                elif res_gen.status_code == 429:
                    if attempt < max_retries - 1:
                        retry_after = res_gen.headers.get("Retry-After")
                        try:
                            wait_s = float(retry_after) if retry_after else (2 ** attempt) + 1
                        except ValueError:
                            wait_s = (2 ** attempt) + 1
                        time.sleep(min(wait_s, 20))
                        continue

                    _EXHAUSTED_MODELS.add(target_model)
                    _discover_target_model.clear()
                    new_target_model = _discover_target_model()
                    if new_target_model and (new_target_model != target_model) and (new_target_model not in _EXHAUSTED_MODELS):
                        return _call_gemini_api(prompt, temperature)
                    return (
                        "⚠️ [모든 AI 모델 한도 초과] 현재 사용 가능한 모든 AI 모델의 일일 한도를 모두 소진했습니다. "
                        "내일 다시 시도하시거나, Google AI Studio에서 결제 설정을 확인해주세요."
                    )

                elif res_gen.status_code in [500, 503]:
                    if attempt < max_retries_5xx - 1:
                        time.sleep((2 ** attempt) + 1)
                        continue

                    _EXHAUSTED_MODELS.add(target_model)
                    _discover_target_model.clear()
                    new_target_model = _discover_target_model()
                    if new_target_model and (new_target_model != target_model) and (new_target_model not in _EXHAUSTED_MODELS):
                        return _call_gemini_api(prompt, temperature)
                    return f"⚠️ [서버 과부하] 구글 AI 서버가 혼잡하여 다른 모델로 우회하려 했으나 모두 실패했습니다. (상태코드: {res_gen.status_code})"

                elif res_gen.status_code == 404:
                    _discover_target_model.clear()
                    if target_model != _LATEST_FLASH_ALIAS and attempt < max_retries - 1:
                        target_model = _LATEST_FLASH_ALIAS
                        continue
                    return "⚠️ [모델 오류] 사용하려던 AI 모델을 찾을 수 없어 안전 모델로 자동 재시도했지만 실패했습니다. (구글이 해당 모델 서비스를 종료했을 가능성이 있습니다)"

                else:
                    return f"⚠️ API 요청 거부 ({res_gen.status_code}): {res_gen.text}"

            except requests.exceptions.RequestException as req_e:
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue

                _EXHAUSTED_MODELS.add(target_model)
                _discover_target_model.clear()
                new_target_model = _discover_target_model()
                if new_target_model and (new_target_model != target_model) and (new_target_model not in _EXHAUSTED_MODELS):
                    return _call_gemini_api(prompt, temperature)
                return f"⚠️ 네트워크 통신 오류(Timeout 등)가 지속되어 중지합니다: {str(req_e)}"

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