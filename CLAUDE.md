# Mogrid

## 프로젝트 목적
무료 LLM API(Groq, Gemini)를 여러 개 묶어서, CLI 환경에서 파일을
읽고 쓰며 계속 작업을 이어가는 에이전트 도구. 하나의 provider가
실패하면 다음 provider로 자동 전환되는 폴백 라우터가 핵심.

## 현재 단계
MVP 1단계 진행 중 — router/groq_client.py 완성이 목표.
아직 폴백 로직, tool use, 에이전틱 루프는 구현 안 됨.

## 폴더 구조
- router/    : provider별 API 클라이언트 + 폴백 로직
- agent_loop/: 요청-응답-tool실행 루프
- tools/     : 모델이 호출할 수 있는 함수들 (read_file, write_file 등)

## 규칙
- API 키는 항상 .env에서 읽고, 하드코딩 금지
- 각 provider 클라이언트는 같은 인터페이스(call_모델명(prompt) -> str)를 따를 것
- 에러 처리는 항상 명시적으로, silent fail 금지

## 다음 단계
1. groq_client.py 완성 + 콘솔 응답 확인
2. gemini_client.py 같은 구조로 추가
3. 폴백 함수 작성
