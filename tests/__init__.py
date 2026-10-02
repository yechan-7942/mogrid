import os

# provider 모듈들이 import 시점에 load_dotenv()로 개발자의 .env를 읽어 들이므로, 동작을
# 바꾸는 사용자 설정이 거기 있으면 테스트 결과가 실행하는 사람마다 달라진다. load_dotenv는
# 이미 있는 변수를 덮어쓰지 않으니, 그보다 먼저(이 패키지가 가장 먼저 import된다) 빈 값으로
# 고정해 둔다 — 빈 값은 "설정 안 함"과 같게 동작한다. 필요한 테스트는 patch.dict로 직접 켠다.
for _var in ("MOGRID_AUTO_APPROVE", "MOGRID_AUTO_APPROVE_COMMANDS", "MOGRID_MAX_STEPS"):
    os.environ[_var] = ""
