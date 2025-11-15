# 비트코인 자동매매 시스템 (Bitcoin Auto-Trading Bot)

업비트(Upbit) API를 활용한 암호화폐 자동매매 프로그램입니다. 모의거래와 실거래를 모두 지원하며, 다양한 기술적 분석 전략과 강력한 리스크 관리 시스템을 제공합니다.

## ✨ 주요 기능

### 📊 거래 전략
- **모멘텀 전략**: RSI, MACD, 이동평균선을 활용한 추세 추종
- **평균 회귀 전략**: 과매도/과매수 구간 감지 및 역추세 매매
- **김치 프리미엄 전략**: 한국 시장 특화 프리미엄 추적
- **거래량 돌파 전략**: 급등 거래량과 가격 돌파 동시 감지

### 🛡️ 리스크 관리
- **손절매**: 평균단가 대비 손실률 기준 자동 청산
- **일일 손익 한도**: 최대 수익/손실 달성 시 자동 거래 중지
- **포지션 관리**: 최대 보유 종목 수 제한
- **자금 배분**: 단일 포지션 크기 제한으로 분산 투자

### 🧪 모의거래 지원
- **가상 지갑**: 실제 API 없이 시뮬레이션 가능
- **완벽한 격리**: 실제 자금 영향 없음
- **동일한 로직**: 실거래와 동일한 전략 검증

### 📈 성과 추적
- **SQLite 데이터베이스**: 모든 거래 기록 저장
- **실시간 대시보드**: 웹 인터페이스로 진행 상황 모니터링
- **상세 로그**: 매수/매도/손절매 결정 과정 기록

### 🔐 보안
- **환경 변수 지원**: API 키를 .env 파일로 안전하게 관리
- **Git 보안**: .gitignore로 민감 정보 커밋 방지
- **키 마스킹**: 로그 출력 시 API 키 일부만 표시

## 🚀 빠른 시작

### 1. 환경 설정

```bash
# 의존성 패키지 설치
pip install -r requirements.txt

# API 키 설정 (둘 중 하나 선택)
# 방법 1: .env 파일 생성
cp .env.example .env
# .env 파일을 열어 실제 API 키 입력

# 방법 2: key.txt 파일 사용 (레거시)
# upbit/key.txt 파일에 Access key와 Secret key 입력
```

### 2. 거래 설정

`upbit/user_config.json` 파일을 편집하여 매매 설정을 조정합니다:

```json
{
  "initial_amount": 1000000.0,      // 초기 자금 (원)
  "max_daily_profit": 0.05,         // 최대 일일 수익률 (5%)
  "max_daily_loss": 0.03,           // 최대 일일 손실률 (3%)
  "max_positions": 5,               // 최대 보유 종목 수
  "stop_loss_rate": 0.02,           // 손절매 기준 (2%)
  "paper_trading": true,            // 모의거래 모드 (true/false)
  "target_coins": [                 // 대상 암호화폐
    "KRW-BTC", "KRW-ETH", "KRW-XRP"
  ]
}
```

#### 📌 코인 선택 옵션

**옵션 1: 특정 코인 지정** (기본)
```json
{
  "target_coins": ["KRW-BTC", "KRW-ETH", "KRW-XRP", "KRW-ADA"]
}
```

**옵션 2: 전체 코인 자동 필터링** (권장)
```json
{
  "target_coins": ["ALL"]
}
```

전체 선택 시 자동 필터링 기준:
- ✅ 가격: 10원 이상
- ✅ 일일 거래량: 10억원 이상
- ✅ 거래 가능 상태

시작 시 상세 정보가 표시됩니다:
```
📊 전체 KRW 마켓 코인 조회: 245개
✅ 필터링 후 대상 코인: 67개

✅ 거래 대상 (67개):
  1. KRW-BTC      - 정상 (가격: ₩135,000,000, 거래량: ₩4,523.5억)
  2. KRW-ETH      - 정상 (가격: ₩4,250,000, 거래량: ₩1,234.2억)
  ...

❌ 제외된 코인 (178개):
  1. KRW-XXX      - 거래량 부족 (₩2.3억)
  2. KRW-YYY      - 가격 너무 낮음 (₩5)
  ...
```

### 3. 시스템 검증

```bash
cd upbit

# 전체 시스템 통합 테스트
python3 test_full_system.py

# 핵심 로직 시뮬레이션
python3 test_simulation.py

# 엣지 케이스 검증
python3 test_edge_cases.py
```

### 4. 실행

```bash
# 모의거래 모드로 먼저 테스트 (권장)
python3 main.py

# 실거래 전환 (user_config.json에서 paper_trading: false로 변경 후)
python3 main.py
```

## 📚 문서

| 문서 | 설명 |
|------|------|
| [TRADING_GUIDE.md](TRADING_GUIDE.md) | 매매 설정 상세 가이드 (11개 파라미터 설명) |
| [VERIFICATION_REPORT.md](VERIFICATION_REPORT.md) | 시스템 검증 리포트 (16/16 테스트 통과) |
| [CHANGELOG.md](CHANGELOG.md) | 변경 이력 (2025-11-14 보안/안정성 개선) |

## 🧪 테스트

### 테스트 파일 구조

```
upbit/
├── test_full_system.py     # 전체 시스템 통합 테스트 (9단계)
├── test_simulation.py      # 핵심 로직 시뮬레이션 (5단계)
└── test_edge_cases.py      # 엣지 케이스 검증 (7가지 시나리오)
```

### 검증 항목

✅ **모듈 Import** - 모든 필수 모듈 로드
✅ **설정 검증** - user_config.json 유효성 확인
✅ **API 키 로드** - 환경 변수/파일에서 안전하게 로드
✅ **데이터베이스** - SQLite 초기화 및 로깅
✅ **가상 지갑** - 모의거래 모드 동작
✅ **수익률 계산** - 정상/부분매도/손실 케이스
✅ **포지션 관리** - 신규매수/추가매수/부분매도/전량매도
✅ **손절매 로직** - 손실률 기준 자동 청산
✅ **리스크 관리** - 일일 한도, 포지션 한도 검증

## ⚙️ 핵심 설정 파라미터

### 기본 설정

| 파라미터 | 기본값 | 설명 | 권장 범위 |
|---------|-------|------|----------|
| `initial_amount` | 1,000,000 | 초기 투자 자금 (원) | 500,000 ~ 10,000,000 |
| `paper_trading` | true | 모의거래 모드 활성화 | true (테스트 후 false) |
| `target_coins` | 8개 | 거래 대상 코인 | 3~10개 |
| `min_trade_amount` | 50,000 | 최소 거래 금액 (원) | 10,000 ~ 100,000 |

### 리스크 관리

| 파라미터 | 기본값 | 설명 | 권장 범위 |
|---------|-------|------|----------|
| `max_daily_profit` | 5% | 최대 일일 수익률 | 3~10% |
| `max_daily_loss` | 3% | 최대 일일 손실률 | 2~5% |
| `stop_loss_rate` | 2% | 손절매 기준 | 2~5% |
| `max_positions` | 5 | 최대 동시 보유 종목 | 3~10개 |
| `max_position_size` | 30% | 단일 포지션 최대 비율 | 20~50% |

### 거래 옵션

| 파라미터 | 기본값 | 설명 |
|---------|-------|------|
| `compound_interest` | true | 복리 투자 (수익금 재투자) |
| `include_fees` | true | 거래 수수료 계산 포함 |
| `upbit_fee_rate` | 0.05% | 업비트 거래 수수료 |
| `claude_interval` | 30초 | AI 분석 주기 |

## 📈 거래 전략 상세

### 1. 모멘텀 전략
```
매수 조건:
- RSI: 50~70 (상승 추세)
- MACD: 양수 (상승 모멘텀)
- 이동평균: 단기 > 장기 (골든크로스)

매도 조건:
- RSI > 70 (과매수)
- MACD < 0 (하락 전환)
```

### 2. 평균 회귀 전략
```
매수 조건:
- RSI < 30 (과매도)
- 볼린저밴드: 하단 근처

매도 조건:
- 볼린저밴드: 상단 근처
- 중심선 회귀 완료
```

### 3. 김치 프리미엄 전략
```
매수 조건:
- 프리미엄 > 3% (한국 시장 강세)

매도 조건:
- 프리미엄 < 1% (프리미엄 소멸)
```

### 4. 거래량 돌파 전략
```
매수 조건:
- 거래량: 평균 대비 3배 이상
- 가격 상승: 5% 이상
```

## 🛡️ 리스크 관리 시스템

### 손절매 메커니즘

```python
# 평균단가 대비 2% 하락 시 자동 매도
if current_price <= avg_price * (1 - stop_loss_rate):
    execute_sell_order(symbol, quantity)
```

### 일일 손익 한도

```python
# 수익 5% 또는 손실 3% 도달 시 당일 거래 중지
daily_profit_rate = (current_value - initial_value) / initial_value

if daily_profit_rate >= max_daily_profit:
    stop_trading_for_today()
elif daily_profit_rate <= -max_daily_loss:
    stop_trading_for_today()
```

### 포지션 제한

```python
# 최대 5개 종목까지만 보유
if len(positions) >= max_positions:
    skip_new_buy_signals()

# 단일 포지션은 전체 자금의 30% 이하
position_size = min(signal_amount, total_balance * max_position_size)
```

## 🎯 추천 시나리오

### 초보자 (보수적)
```json
{
  "initial_amount": 1000000,
  "max_daily_profit": 0.03,
  "max_daily_loss": 0.02,
  "max_positions": 3,
  "stop_loss_rate": 0.02,
  "paper_trading": true,
  "target_coins": ["KRW-BTC", "KRW-ETH"]
}
```
- 주요 코인 2개만 거래
- 낮은 수익률 목표 (3%)
- 엄격한 손절매 (2%)

### 중급자 (균형)
```json
{
  "initial_amount": 3000000,
  "max_daily_profit": 0.05,
  "max_daily_loss": 0.03,
  "max_positions": 5,
  "stop_loss_rate": 0.03,
  "paper_trading": false,
  "target_coins": ["KRW-BTC", "KRW-ETH", "KRW-XRP", "KRW-ADA", "KRW-SOL"]
}
```
- 중형 포트폴리오 (5종목)
- 현실적 수익률 목표 (5%)
- 균형잡힌 리스크 관리

### 고급자 (공격적)
```json
{
  "initial_amount": 10000000,
  "max_daily_profit": 0.08,
  "max_daily_loss": 0.05,
  "max_positions": 8,
  "stop_loss_rate": 0.05,
  "paper_trading": false,
  "target_coins": ["KRW-BTC", "KRW-ETH", "KRW-XRP", "KRW-ADA", "KRW-SOL", "KRW-AVAX", "KRW-DOT", "KRW-MATIC"]
}
```
- 대형 포트폴리오 (8종목)
- 높은 수익률 목표 (8%)
- 여유로운 손절매 (5%)

## 📊 성과 추적

### 데이터베이스 스키마

```sql
-- 거래 기록
CREATE TABLE trades (
    id INTEGER PRIMARY KEY,
    symbol TEXT,
    trade_type TEXT,  -- BUY/SELL
    quantity REAL,
    price REAL,
    amount REAL,
    profit_rate REAL,
    timestamp TEXT
);

-- 포지션 기록
CREATE TABLE positions (
    symbol TEXT PRIMARY KEY,
    avg_price REAL,
    quantity REAL,
    total_invested REAL,
    entry_time TEXT
);
```

### 웹 대시보드

```bash
# Flask 서버 시작 (포트 5000)
python3 main.py
```

브라우저에서 `http://localhost:5000` 접속:
- 실시간 잔고 현황
- 포지션 목록 (평균단가, 수익률)
- 최근 거래 내역
- 일일 수익률 그래프

## 🔧 문제 해결

### Q1: "API 키 로드 실패" 오류

**원인**: 환경 변수 또는 key.txt 파일에 API 키가 없음

**해결**:
```bash
# .env 파일 확인
cat .env
# 다음 형식으로 작성되어야 함:
# UPBIT_ACCESS_KEY=your_access_key_here
# UPBIT_SECRET_KEY=your_secret_key_here

# 또는 key.txt 확인
cat upbit/key.txt
# 다음 형식으로 작성되어야 함:
# Access key: your_access_key_here
# Secret key: your_secret_key_here
```

### Q2: "대상 코인이 비어있습니다" 경고

**원인**: user_config.json의 target_coins가 빈 배열

**해결**:
```json
{
  "target_coins": [
    "KRW-BTC",
    "KRW-ETH",
    "KRW-XRP"
  ]
}
```

### Q3: 수익률이 비현실적으로 높음 (300%+)

**원인**: 이미 수정됨 (2025-11-14 업데이트)

**확인**:
```bash
# 최신 버전 확인
grep "profit_rate" upbit/trading_engine.py
# 다음이 있어야 함:
# if abs(profit_rate) > 3.0:  # 300% 검증
```

### Q4: 모의거래 모드에서 거래가 안 됨

**원인**: paper_trading이 true인데 실제 API 호출 시도

**해결**:
```json
{
  "paper_trading": true  // 모의거래 모드 확인
}
```

모의거래 모드에서는 `VirtualWallet` 클래스가 자동으로 활성화되며, 실제 API는 시장 데이터 조회만 사용합니다.

### Q5: pyupbit 없이 테스트 가능한가?

**답변**: 가능합니다!

```bash
# 패키지 없이 실행 가능한 테스트
python3 test_simulation.py  # 핵심 로직만 검증
python3 test_full_system.py # 설정/DB는 검증, API는 스킵

# pyupbit 설치 후 전체 기능 사용
pip install pyupbit pandas numpy ta
python3 main.py
```

## 🚨 실거래 전 필수 체크리스트

- [ ] **3~7일 모의거래 완료**: paper_trading: true로 충분히 테스트
- [ ] **API 키 권한 확인**: 업비트에서 "자산 조회" + "주문" 권한 부여
- [ ] **실제 잔고 확인**: 업비트 계정에 설정 금액 이상 보유
- [ ] **리스크 이해**: 암호화폐는 변동성이 크며 원금 손실 가능
- [ ] **손절매 설정**: stop_loss_rate를 적절히 설정 (권장: 2~3%)
- [ ] **일일 한도 설정**: max_daily_loss로 최대 손실 제한 (권장: 3~5%)
- [ ] **알림 설정**: Telegram 봇 연동으로 중요 이벤트 수신
- [ ] **백업**: 중요 설정 파일 백업 (user_config.json, .env)

## 📦 프로젝트 구조

```
bitcoin/
├── upbit/
│   ├── main.py                 # 메인 실행 파일
│   ├── trading_bot.py          # 봇 오케스트레이션
│   ├── trading_engine.py       # 핵심 거래 로직
│   ├── config.py               # 설정 관리
│   ├── logging_manager.py      # 데이터베이스/로깅
│   ├── ai_notification.py      # AI 분석/알림
│   ├── user_config.json        # 사용자 설정
│   ├── test_full_system.py     # 통합 테스트
│   ├── test_simulation.py      # 로직 시뮬레이션
│   └── test_edge_cases.py      # 엣지 케이스 검증
├── .env                        # API 키 (생성 필요)
├── .env.example                # API 키 템플릿
├── .gitignore                  # Git 보안 설정
├── requirements.txt            # 의존성 패키지
├── TRADING_GUIDE.md            # 매매 설정 가이드
├── VERIFICATION_REPORT.md      # 검증 리포트
├── CHANGELOG.md                # 변경 이력
└── README.md                   # 이 파일
```

## 📈 검증 결과 요약

**최종 검증일**: 2025-11-14
**테스트 결과**: ✅ 16/16 통과 (100%)

| 카테고리 | 테스트 | 결과 |
|---------|-------|------|
| **모듈 Import** | 모든 필수 모듈 로드 | ✅ |
| **설정** | user_config.json 유효성 | ✅ |
| **보안** | API 키 환경 변수 로드 | ✅ |
| **데이터베이스** | SQLite 초기화 | ✅ |
| **모의거래** | VirtualWallet 동작 | ✅ |
| **수익률 계산** | 정상 케이스 (10% 수익) | ✅ |
| **수익률 계산** | 부분 매도 (20% 수익) | ✅ |
| **수익률 계산** | 손실 케이스 (-5%) | ✅ |
| **포지션 관리** | 신규 매수 | ✅ |
| **포지션 관리** | 추가 매수 (평균단가) | ✅ |
| **포지션 관리** | 부분 매도 (50%) | ✅ |
| **포지션 관리** | 전량 매도 | ✅ |
| **손절매** | 정상 범위 | ✅ |
| **손절매** | 손절매 발동 | ✅ |
| **리스크 관리** | 일일 한도 검증 | ✅ |
| **체크리스트** | 실행 전 필수 항목 | ✅ |

상세 내용은 [VERIFICATION_REPORT.md](VERIFICATION_REPORT.md)를 참고하세요.

## 🔗 외부 링크

- [업비트 API 문서](https://docs.upbit.com/)
- [pyupbit 라이브러리](https://github.com/sharebook-kr/pyupbit)
- [기술적 분석 (ta) 라이브러리](https://technical-analysis-library-in-python.readthedocs.io/)

## ⚖️ 면책 조항

이 소프트웨어는 교육 및 연구 목적으로 제공됩니다. 암호화폐 거래는 높은 리스크를 수반하며, 투자 원금의 전부 또는 일부를 잃을 수 있습니다.

- 실제 자금으로 거래하기 전에 충분히 테스트하세요
- 투자 결정에 대한 책임은 전적으로 사용자에게 있습니다
- 개발자는 이 소프트웨어 사용으로 인한 어떠한 손실에도 책임지지 않습니다
- 법적 규제를 확인하고 준수하세요

## 📄 라이선스

이 프로젝트는 개인 사용 목적으로 제공됩니다.

---

**마지막 업데이트**: 2025-11-14
**버전**: 1.0.0 (보안 및 안정성 개선)
**검증 상태**: ✅ 모든 테스트 통과 (16/16)
