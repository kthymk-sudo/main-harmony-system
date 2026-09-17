# utils/response_parser.py
import re

def parse_almind_response(result_text):
    """
    AI 응답 텍스트에서 알마인드 요약(트리)과 피드백(카드)을 안전하게 분리하고
    불필요한 찌꺼기 텍스트를 정제하는 전담 파서(Parser) 함수
    """
    # 🛡️ 철벽 방어: '$$' 기호를 찾아 그 앞뒤로 화면 분리
    if "$$" in result_text:
        parts = result_text.split("$$", 1)  # 첫 번째 $$를 기준으로 두 동강
        almind_part = parts[0]
        feedback_part = "$$" + parts[1]
        
        # 상단의 '[알마인드]'나 하단의 '[피드백]' 같은 불필요한 제목 찌꺼기 청소
        almind_part = re.sub(r'\[.*?알마인드.*?\]', '', almind_part)
        almind_part = re.sub(r'\[.*?피드백.*?\]', '', almind_part)
        almind_part = re.sub(r'^\s*\d+\.?\s*', '', almind_part).strip()
        
        return almind_part, feedback_part.strip()
    
    # 만약 AI가 $$ 기호조차 빼먹고 엉망으로 대답했을 경우의 최후 방어
    error_msg = "형식 분리 실패\n\nAI가 양식을 무시했습니다. '분석 시작' 버튼을 다시 한 번 눌러주세요."
    return error_msg, result_text