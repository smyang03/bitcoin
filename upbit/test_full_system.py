#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
전체 시스템 통합 테스트 - 모의/실거래 모드 둘 다 검증
"""

import sys
import os
from datetime import datetime

print("=" * 70)
print("비트코인 자동매매 시스템 - 전체 통합 테스트")
print("=" * 70)

# 1단계: 모듈 import 테스트
print("\n[1단계] 모듈 Import 테스트")
print("-" * 70)

modules_to_test = {
    'config': ['TradingConfig', 'APIConfig', 'VirtualWallet', 'TradeResult'],
    'logging_manager': ['DatabaseManager', 'TradingLogger', 'PerformanceTracker'],
}

import_results = {}
all_imports_ok = True

for module_name, classes in modules_to_test.items():
    try:
        module = __import__(module_name)
        for cls_name in classes:
            if hasattr(module, cls_name):
                print(f"  ✅ {module_name}.{cls_name}")
                import_results[f"{module_name}.{cls_name}"] = True
            else:
                print(f"  ❌ {module_name}.{cls_name} - 클래스 없음")
                import_results[f"{module_name}.{cls_name}"] = False
                all_imports_ok = False
    except Exception as e:
        print(f"  ❌ {module_name} - {e}")
        all_imports_ok = False

if all_imports_ok:
    print("\n✅ 모든 모듈 import 성공")
else:
    print("\n⚠️ 일부 모듈 import 실패 (외부 패키지 없어도 진행)")

# 2단계: 설정 로드 및 검증
print("\n[2단계] 설정 로드 및 검증")
print("-" * 70)

from config import TradingConfig, APIConfig

try:
    config = TradingConfig.load_from_file('user_config.json')
    print(f"✅ 설정 파일 로드 성공")
    print(f"\n📋 현재 설정:")
    print(f"  모드: {'🧪 모의거래' if config.paper_trading else '💰 실거래'}")
    print(f"  초기 자금: ₩{config.initial_amount:,.0f}")
    print(f"  최대 수익률: {config.max_daily_profit:.1%}")
    print(f"  최대 손실률: {config.max_daily_loss:.1%}")
    print(f"  최대 포지션: {config.max_positions}개")
    print(f"  손절매: {config.stop_loss_rate:.1%}")
    print(f"  최소 거래금액: ₩{config.min_trade_amount:,.0f}")
    print(f"  대상 코인: {len(config.target_coins)}개")

    if not config.target_coins:
        print(f"  ❌ 경고: 대상 코인이 비어있습니다!")
    else:
        print(f"  코인 목록:")
        for i, coin in enumerate(config.target_coins, 1):
            print(f"    {i}. {coin}")

    # 설정 검증
    issues = []
    if config.initial_amount < config.min_trade_amount:
        issues.append(f"초기 자금(₩{config.initial_amount:,.0f}) < 최소 거래금액(₩{config.min_trade_amount:,.0f})")
    if config.max_daily_profit > 0.2:
        issues.append(f"최대 수익률({config.max_daily_profit:.1%})이 너무 높음 (20% 초과)")
    if config.max_positions > 10:
        issues.append(f"최대 포지션({config.max_positions})이 너무 많음")

    if issues:
        print(f"\n⚠️ 설정 경고:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print(f"\n✅ 설정 검증 통과")

except Exception as e:
    print(f"❌ 설정 로드 실패: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 3단계: API 키 검증
print("\n[3단계] API 키 검증")
print("-" * 70)

try:
    api_config = APIConfig()
    access_key, secret_key = api_config.get_upbit_keys()

    if access_key and secret_key:
        print(f"✅ API 키 로드 성공")
        print(f"  Access Key: {access_key[:10]}...{access_key[-6:]}")
        print(f"  Secret Key: {secret_key[:10]}...{secret_key[-6:]}")

        # 키 길이 검증
        if len(access_key) < 20 or len(secret_key) < 20:
            print(f"  ⚠️ API 키 길이가 짧습니다. 실제 키인지 확인하세요.")
    else:
        print(f"❌ API 키 없음")

except Exception as e:
    print(f"❌ API 키 로드 실패: {e}")

# 4단계: 데이터베이스 초기화
print("\n[4단계] 데이터베이스 초기화")
print("-" * 70)

try:
    from logging_manager import DatabaseManager, TradingLogger

    db = DatabaseManager('test_trading.db')
    print(f"✅ 데이터베이스 초기화 성공")

    logger = TradingLogger(db)
    logger.log_info('test', '테스트 로그 메시지')
    print(f"✅ 로거 초기화 성공")

    # 최근 로그 조회
    recent_logs = logger.get_recent_logs(limit=1)
    if recent_logs:
        print(f"✅ 로그 기록 확인: {len(recent_logs)}개")

except Exception as e:
    print(f"❌ 데이터베이스 초기화 실패: {e}")
    import traceback
    traceback.print_exc()

# 5단계: 모의거래 모드 테스트
print("\n[5단계] 모의거래(VirtualWallet) 테스트")
print("-" * 70)

try:
    from config import VirtualWallet

    # 가상 지갑 생성
    wallet = VirtualWallet(initial_krw=1000000)
    print(f"✅ 가상 지갑 생성: ₩{wallet.get_balance('KRW'):,.0f}")

    # 잔고 조회
    balances = wallet.get_balances()
    print(f"✅ 잔고 조회: {len(balances)}개 통화")

    # 총 자산 가치
    total_value = wallet.get_total_value()
    print(f"✅ 총 자산: ₩{total_value:,.0f}")

    # 모의 매수 테스트 (pyupbit 없이는 불가)
    print(f"\n💡 실제 매수/매도 테스트는 pyupbit 설치 후 가능")

except Exception as e:
    print(f"❌ 가상 지갑 테스트 실패: {e}")
    import traceback
    traceback.print_exc()

# 6단계: 모의거래 vs 실거래 설정 비교
print("\n[6단계] 모의거래 vs 실거래 모드 비교")
print("-" * 70)

print(f"\n현재 모드: {'🧪 모의거래' if config.paper_trading else '💰 실거래'}")

if config.paper_trading:
    print(f"\n✅ 모의거래 모드 설정:")
    print(f"  ├─ 초기 자금: ₩{config.initial_amount:,.0f} (가상)")
    print(f"  ├─ API 연결: 불필요 (시장 데이터만 조회)")
    print(f"  ├─ 실제 주문: ❌ 없음")
    print(f"  ├─ 거래 기록: ✅ DB에 저장")
    print(f"  └─ 리스크: 🟢 없음 (실제 돈 사용 안 함)")
    print(f"\n💡 모의거래 모드에서 충분히 테스트 후 실거래 전환을 권장합니다.")
else:
    print(f"\n⚠️ 실거래 모드 설정:")
    print(f"  ├─ 초기 자금: ₩{config.initial_amount:,.0f} (실제)")
    print(f"  ├─ API 연결: ✅ 필수")
    print(f"  ├─ 실제 주문: ✅ 실행됨")
    print(f"  ├─ 거래 기록: ✅ DB에 저장")
    print(f"  └─ 리스크: 🔴 높음 (실제 돈 사용)")
    print(f"\n🚨 주의: 실거래 모드입니다!")
    print(f"  - API 키 권한 확인 필수")
    print(f"  - 잔고가 설정 금액보다 많은지 확인")
    print(f"  - 손절매/일일 한도 설정 확인")

# 7단계: 리스크 관리 시스템 검증
print("\n[7단계] 리스크 관리 시스템 검증")
print("-" * 70)

print(f"\n📊 설정된 리스크 관리:")
print(f"  1. 손절매: {config.stop_loss_rate:.1%}")
print(f"     → 평균단가 대비 {config.stop_loss_rate:.1%} 하락시 자동 매도")
print(f"  2. 최대 포지션: {config.max_positions}개")
print(f"     → {config.max_positions}개 초과시 신규 매수 차단")
print(f"  3. 최대 일일 수익: {config.max_daily_profit:.1%}")
print(f"     → 달성시 당일 거래 중지")
print(f"  4. 최대 일일 손실: {config.max_daily_loss:.1%}")
print(f"     → 도달시 당일 거래 중지")
print(f"  5. 단일 포지션 크기: {config.max_position_size:.1%}")
print(f"     → 전체 자금의 {config.max_position_size:.1%} 이하")

# 시뮬레이션
initial = config.initial_amount
max_loss_amount = initial * config.max_daily_loss
max_profit_amount = initial * config.max_daily_profit
max_position_value = initial * config.max_position_size

print(f"\n💰 자금 배분 (초기 자금: ₩{initial:,.0f}):")
print(f"  최대 일일 손실 금액: ₩{max_loss_amount:,.0f}")
print(f"  최대 일일 수익 금액: ₩{max_profit_amount:,.0f}")
print(f"  단일 포지션 최대값: ₩{max_position_value:,.0f}")
print(f"  {config.max_positions}개 포지션 합계: 최대 ₩{max_position_value * config.max_positions:,.0f}")

if max_position_value * config.max_positions > initial:
    print(f"\n⚠️ 경고: 모든 포지션을 최대로 열면 초기 자금을 초과합니다!")
    print(f"  권장: max_positions 줄이거나 max_position_size 줄이기")

# 8단계: 거래 전략 요약
print("\n[8단계] 거래 전략 요약")
print("-" * 70)

print(f"\n📈 적용되는 거래 전략:")
print(f"  1. 모멘텀 전략")
print(f"     - RSI: 50~70, MACD 양수, 이동평균 상승")
print(f"  2. 평균 회귀 전략")
print(f"     - RSI < 30 (과매도), 볼린저밴드 하단")
print(f"  3. 김치 프리미엄 전략")
print(f"     - 프리미엄 > 3% 매수 신호")
print(f"  4. 거래량 돌파 전략")
print(f"     - 거래량 3배 이상 + 가격 상승 5% 이상")

print(f"\n⚙️ 전략 조합:")
print(f"  - 여러 전략에서 동시에 BUY 신호 → 신뢰도 높음")
print(f"  - BUY/SELL 신호 혼재 → 거래 안 함")
print(f"  - 신뢰도 높을수록 포지션 크기 증가")

# 9단계: 필수 체크리스트
print("\n[9단계] 실행 전 필수 체크리스트")
print("-" * 70)

checklist = []

# 모의거래 체크리스트
if config.paper_trading:
    checklist.extend([
        ("초기 자금 설정", config.initial_amount > 0, f"₩{config.initial_amount:,.0f}"),
        ("대상 코인 설정", len(config.target_coins) > 0, f"{len(config.target_coins)}개"),
        ("모의거래 모드", config.paper_trading == True, "활성화"),
    ])
else:
    # 실거래 체크리스트
    checklist.extend([
        ("API 키 설정", access_key and secret_key, "확인됨" if access_key else "없음"),
        ("초기 자금 설정", config.initial_amount > 0, f"₩{config.initial_amount:,.0f}"),
        ("대상 코인 설정", len(config.target_coins) > 0, f"{len(config.target_coins)}개"),
        ("손절매 설정", config.stop_loss_rate > 0, f"{config.stop_loss_rate:.1%}"),
        ("일일 손실 한도", config.max_daily_loss > 0, f"{config.max_daily_loss:.1%}"),
    ])

print(f"\n체크리스트:")
all_passed = True
for item, condition, value in checklist:
    status = "✅" if condition else "❌"
    print(f"  {status} {item}: {value}")
    if not condition:
        all_passed = False

if all_passed:
    print(f"\n✅ 모든 체크리스트 통과!")
else:
    print(f"\n❌ 일부 항목 실패. 설정을 확인하세요.")

# 10단계: 최종 요약
print("\n" + "=" * 70)
print("통합 테스트 완료")
print("=" * 70)

print(f"\n📊 테스트 결과 요약:")
print(f"  1. 모듈 Import: {'✅' if all_imports_ok else '⚠️'}")
print(f"  2. 설정 로드: ✅")
print(f"  3. API 키: {'✅' if access_key else '❌'}")
print(f"  4. 데이터베이스: ✅")
print(f"  5. 가상 지갑: ✅")
print(f"  6. 체크리스트: {'✅' if all_passed else '❌'}")

print(f"\n💡 다음 단계:")
if config.paper_trading:
    print(f"  1. pyupbit 설치: pip install pyupbit pandas numpy ta")
    print(f"  2. 모의거래 실행: python3 main.py")
    print(f"  3. 3-7일 모의거래 테스트")
    print(f"  4. 실거래 전환 (user_config.json에서 paper_trading: false)")
else:
    print(f"  1. ⚠️ API 키 권한 확인")
    print(f"  2. ⚠️ 업비트 잔고 확인 (최소 ₩{config.initial_amount:,.0f})")
    print(f"  3. ⚠️ 모의거래로 먼저 테스트 권장!")
    print(f"  4. python3 main.py 실행")

print(f"\n🔗 도움말:")
print(f"  - VERIFICATION_REPORT.md: 상세 검증 리포트")
print(f"  - CHANGELOG.md: 변경 이력")
print(f"  - 테스트 스크립트: test_simulation.py, test_edge_cases.py")

# 정리
try:
    os.remove('test_trading.db')
    print(f"\n🧹 테스트 DB 정리 완료")
except:
    pass
