#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
수정된 메인 파일 - main() 함수 정의 문제 해결
"""

import sys
import traceback
import time
from datetime import datetime

# 모듈 임포트
try:
    from config import TradingConfig
    print("config 모듈 로드 성공")
except Exception as e:
    print(f"config 모듈 로드 실패: {e}")
    sys.exit(1)

def get_user_config() -> TradingConfig:
    """사용자 설정 입력"""
    print("=== 거래 설정 (Enter로 기본값 사용) ===")
    
    config = TradingConfig()
    
    try:
        # 초기 투자 금액
        initial_amount = input(f"초기 투자 금액 (기본: {config.initial_amount:,.0f}원): ").strip()
        if initial_amount:
            config.initial_amount = float(initial_amount)
        
        # 일일 최대 수익률
        max_profit = input(f"일일 최대 수익률 (기본: {config.max_daily_profit:.1%}): ").strip()
        if max_profit:
            config.max_daily_profit = float(max_profit) / 100
        
        # 일일 최대 손실률  
        max_loss = input(f"일일 최대 손실률 (기본: {config.max_daily_loss:.1%}): ").strip()
        if max_loss:
            config.max_daily_loss = float(max_loss) / 100
        
        print(f"\n설정 완료:")
        print(f"- 초기 금액: {config.initial_amount:,.0f}원")
        print(f"- 일일 한도: 수익 {config.max_daily_profit:.1%}, 손실 {config.max_daily_loss:.1%}")
        
        return config
        
    except ValueError as e:
        print(f"입력 오류: {e}")
        print("기본 설정을 사용합니다.")
        return config
    except KeyboardInterrupt:
        print("\n프로그램을 종료합니다.")
        sys.exit(0)

def main():
    """메인 실행 함수"""
    
    print("=== 업비트 자동매매 시스템 ===")
    
    try:
        # 1. 사용자 설정 입력
        config = get_user_config()
        
        # 2. 거래 봇 임포트 및 생성
        print("봇 모듈 로딩 중...")
        from trading_bot import TradingBot
        bot = TradingBot(config)
        print("봇 생성 완료")
        
        # 3. API 상태 확인 및 패치 적용
        print("API 상태 확인 중...")
        test_balance = bot.upbit.get_balances()
        if isinstance(test_balance, dict) and 'error' in test_balance:
            error_name = test_balance['error'].get('name', '')
            if error_name == 'no_authorization_ip':
                print("IP 인증 문제 발견 - 가상 모드로 전환")
                from virtual_trading import patch_bot_for_virtual_mode
                patch_bot_for_virtual_mode(bot, config.initial_amount)
                print("가상 모드 활성화 완료")
            else:
                print(f"API 오류: {test_balance['error']}")
        else:
            print("API 연결 정상")
        
        # 안전 패치 적용
        try:
            from emergency_fix import apply_complete_patches
            apply_complete_patches(bot)
            print("안전 패치 적용 완료")
        except Exception as patch_e:
            print(f"패치 적용 중 오류: {patch_e}")
        
        # 4. 웹 서버 시작
        print("웹 서버 시작 중...")
        from web_server import WebServer
        web_server = WebServer(bot)
        
        print("\n시스템 준비 완료!")
        print("웹 대시보드: http://localhost:5000")
        print("Ctrl+C로 종료\n")
        
        web_server.run(host='0.0.0.0', port=5000, debug=False)
        return True
        
    except KeyboardInterrupt:
        print("\n프로그램 종료")
        return True
    except Exception as e:
        print(f"오류 발생: {e}")
        traceback.print_exc()
        return False
    
    finally:
        try:
            if 'bot' in locals() and hasattr(bot, 'is_running') and bot.is_running:
                bot.stop()
        except:
            pass
        print("정리 완료")

def minimal_test():
    """최소한의 기능 테스트"""
    print("=== 최소 기능 테스트 모드 ===")
    
    try:
        # 설정 테스트
        config = TradingConfig()
        print(f"설정 테스트 성공: {config.target_coins}")
        
        # API 키 테스트
        from config import APIConfig
        api_config = APIConfig()
        access_key, secret_key = api_config.get_upbit_keys()
        print(f"API 키 로드 성공: {access_key[:10]}...")
        
        # pyupbit 테스트
        import pyupbit
        upbit = pyupbit.Upbit(access=access_key, secret=secret_key)
        balances = upbit.get_balances()
        print(f"업비트 API 연결 테스트 완료")
        
        return True
        
    except Exception as e:
        print(f"최소 테스트 실패: {e}")
        traceback.print_exc()
        return False

# 프로그램 진입점
if __name__ == "__main__":
    # 명령행 인수 체크
    if len(sys.argv) > 1:
        if sys.argv[1] == "--test":
            success = minimal_test()
            sys.exit(0 if success else 1)
        elif sys.argv[1] == "--help":
            print("""
사용법:
  python main_simple_fixed.py         # 정상 실행 (설정 입력)
  python main_simple_fixed.py --test  # 최소 기능 테스트
  python main_simple_fixed.py --help  # 도움말
            """)
            sys.exit(0)
    
    # 정상 실행
    success = main()
    sys.exit(0 if success else 1)