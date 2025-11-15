# 변경 이력 (Changelog)

## 2025-11-14 - 보안 및 안정성 대폭 개선

### 🔐 보안 개선
- **API 키 환경 변수 지원**: .env 파일 또는 환경 변수로 API 키 관리
  - `UPBIT_ACCESS_KEY`, `UPBIT_SECRET_KEY` 환경 변수 지원
  - Fallback: key.txt 파일 자동 로드
  - API 키 마스킹 출력 (보안 강화)
  - `.gitignore` 추가로 민감 정보 Git 커밋 방지

### 🐛 버그 수정
1. **trading_bot.py:30** - `self.config` 초기화 누락 버그 수정
   - TradingBot 클래스에서 config를 로컬 변수로만 사용하던 문제 해결
   - `self.config = config` 추가

2. **trading_engine.py:844-921** - 수익률 계산 로직 대폭 개선
   - 1220% 같은 비현실적 수익률 발생 버그 수정
   - 부분 매도 지원 추가
   - 수익률 검증 로직 추가 (300% 초과시 대안 계산)
   - 상세한 디버깅 로그 추가

3. **포지션 키 일관성 확보**
   - `entry_price` → `avg_price` 통일
   - `invested_amount` → `total_invested` 통일
   - 매수/매도/손절매 모든 로직에서 일관된 키 사용

### ⚙️ 설정 개선
- **user_config.json** 기본값 현실화
  - `target_coins`: 빈 배열 → 8개 주요 코인 설정 (BTC, ETH, XRP, ADA, SOL, AVAX, DOT, MATIC)
  - `max_daily_profit`: 50% → 5% (현실적으로 조정)
  - `max_positions`: 20 → 5 (리스크 분산)
  - `min_trade_amount`: 100,000 → 50,000원

### 📝 로깅 개선
- 매수/매도/손절매 로그 이모지 추가 (✅, 🔻)
- 포지션 통합 시 이전/이후 비교 정보 표시
- 부분 매도 vs 전량 매도 구분 표시
- 수익률 계산 상세 정보 로그

### 📦 새 파일
- `.env.example`: 환경 변수 템플릿
- `.gitignore`: Git 보안 설정
- `requirements.txt`: 의존성 패키지 목록
- `CHANGELOG.md`: 변경 이력 문서

### 🔧 기술적 개선
- python-dotenv 지원 추가
- 부동소수점 오차 고려 (1e-8)
- 포지션 부분 매도 지원
- 수익률 계산 대안 로직 (가격 변화율 기반)

---

## 향후 개선 예정
- [ ] 매매 진행 사항 실시간 대시보드
- [ ] 로깅 레벨 조정 (INFO → WARNING)
- [ ] 중복 파일 정리 및 문서화
- [ ] 백테스팅 기능
