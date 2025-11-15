#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
웹 로그 시스템 검증 테스트
"""

import sys
import time
from datetime import datetime

def test_log_system():
    """로그 시스템 검증"""
    print("\n" + "="*60)
    print("📝 웹 로그 시스템 검증 테스트")
    print("="*60)

    # 1. 모듈 import 테스트
    print("\n1️⃣ 모듈 Import 검증")
    try:
        from config import TradingConfig
        from main import SimpleTradingBot
        from paper_trading_dashboard import create_enhanced_trading_dashboard
        print("✅ 모든 모듈 import 성공")
    except Exception as e:
        print(f"❌ 모듈 import 실패: {e}")
        return False

    # 2. 설정 로드 테스트
    print("\n2️⃣ 설정 로드 검증")
    try:
        config = TradingConfig.load_from_file()
        print(f"✅ 설정 로드 성공")
        print(f"   - 모드: {'모의거래' if config.paper_trading else '실거래'}")
        print(f"   - 대상 코인: {len(config.target_coins)}개")
    except Exception as e:
        print(f"❌ 설정 로드 실패: {e}")
        return False

    # 3. 봇 생성 테스트
    print("\n3️⃣ 봇 생성 검증")
    try:
        bot = SimpleTradingBot(config)
        print("✅ 봇 생성 성공")
    except Exception as e:
        print(f"❌ 봇 생성 실패: {e}")
        return False

    # 4. 웹 대시보드 생성 테스트
    print("\n4️⃣ 웹 대시보드 생성 검증")
    try:
        web_app = create_enhanced_trading_dashboard(bot)
        print("✅ 웹 대시보드 생성 성공")

        # 5. 로그 함수 존재 확인
        print("\n5️⃣ 로그 함수 검증")
        if hasattr(bot, 'add_live_log'):
            print("✅ add_live_log 함수 존재")
        else:
            print("❌ add_live_log 함수 없음")
            return False

        # 6. 로그 기록 테스트
        print("\n6️⃣ 로그 기록 테스트")
        test_messages = [
            ("테스트 로그 1: 정보 메시지", "info"),
            ("테스트 로그 2: 성공 메시지", "success"),
            ("테스트 로그 3: 경고 메시지", "warning"),
            ("테스트 로그 4: 오류 메시지", "error"),
        ]

        for message, level in test_messages:
            bot.add_live_log(message, level)
            print(f"  📝 {level:8s}: {message}")

        print("✅ 로그 기록 성공 (4개 메시지)")

        # 7. _log 메서드 테스트
        print("\n7️⃣ _log 메서드 검증")
        if hasattr(bot, '_log'):
            print("✅ _log 메서드 존재")
            bot._log("테스트: _log 메서드 호출", "info")
            print("✅ _log 메서드 호출 성공")
        else:
            print("❌ _log 메서드 없음")
            return False

    except Exception as e:
        print(f"❌ 웹 대시보드 생성 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

    # 8. API 엔드포인트 테스트 (웹 서버 미실행 상태)
    print("\n8️⃣ API 엔드포인트 정의 검증")
    try:
        # Flask app에 /api/logs 엔드포인트가 정의되어 있는지 확인
        has_logs_endpoint = False
        for rule in web_app.url_map.iter_rules():
            if '/api/logs' in str(rule):
                has_logs_endpoint = True
                print(f"✅ /api/logs 엔드포인트 발견: {rule}")
                break

        if not has_logs_endpoint:
            print("❌ /api/logs 엔드포인트 없음")
            print("   등록된 엔드포인트:")
            for rule in web_app.url_map.iter_rules():
                print(f"   - {rule}")
            return False

    except Exception as e:
        print(f"❌ 엔드포인트 검증 실패: {e}")
        return False

    # 9. 시뮬레이션: 거래 루프 로그
    print("\n9️⃣ 거래 루프 로그 시뮬레이션")
    try:
        # 거래 체크 로그
        bot._log(f"=== {datetime.now().strftime('%H:%M:%S')} 거래 체크 ===", 'info')
        bot._log("🔍 분석 대상: 8개 코인", 'info')

        # 신호 발견 로그
        bot._log("  📊 KRW-BTC: BUY 신호 (신뢰도: 75.3%)", 'info')
        bot._log("  ✅ 매수 완료: KRW-BTC", 'success')

        # 분석 요약
        bot._log("📈 분석 요약: 8개 분석, 1개 신호 발견", 'info')

        print("✅ 거래 루프 로그 시뮬레이션 완료")
    except Exception as e:
        print(f"❌ 시뮬레이션 실패: {e}")
        return False

    # 최종 결과
    print("\n" + "="*60)
    print("🎉 모든 테스트 통과!")
    print("="*60)
    print("\n📌 다음 단계:")
    print("  1. python main.py 실행")
    print("  2. 웹 브라우저에서 http://localhost:5000 접속")
    print("  3. '거래 시작' 버튼 클릭")
    print("  4. '거래 로그' 섹션에서 실시간 로그 확인")
    print("     - 3초마다 자동 업데이트")
    print("     - 거래 체크, 매수/매도, 신호 발견 등 모든 활동 표시")
    print("="*60)

    return True

if __name__ == "__main__":
    try:
        success = test_log_system()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ 테스트 실행 오류: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
