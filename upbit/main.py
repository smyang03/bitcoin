#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
완성된 메인 거래 봇 - 복잡한 HTML UI + 백엔드 통합 버전
"""

import time
from datetime import datetime
from config import TradingConfig
from logging_manager import DatabaseManager, TradingLogger, PerformanceTracker
from trading_engine import MarketDataCollector, TradingStrategy, RiskManager, OrderExecutor

# SimpleTradingBot 클래스는 그대로 유지
class SimpleTradingBot:
    def __init__(self, config=None):
        if config is None:
            config = TradingConfig.load_from_file()
            
        self.config = config
        self.is_running = False
        self.is_paused = False  # 일시정지 상태 추가
        
        # 컴포넌트 초기화
        self.db = DatabaseManager()
        self.logger = TradingLogger(self.db)
        self.performance_tracker = PerformanceTracker(self.db, self.logger)
        
        if self.config.paper_trading:
            from config import VirtualWallet
            self.wallet = VirtualWallet(self.config.initial_amount)
            self.access_key, self.secret_key = None, None
            print(f"모의거래 모드: ₩{self.config.initial_amount:,.0f}")
        else:
            from config import APIConfig
            api_config = APIConfig()
            self.access_key, self.secret_key = api_config.get_upbit_keys()
            import pyupbit
            self.upbit = pyupbit.Upbit(access=self.access_key, secret=self.secret_key)
            self.wallet = None
            print("실거래 모드 (주의!)")
        
        # 거래 엔진
        self.market_collector = MarketDataCollector(self.access_key, self.secret_key, self.logger)
        self.strategy = TradingStrategy(self.config, self.market_collector, self.logger)
        self.risk_manager = RiskManager(self.config, self.logger)
        
        trading_interface = self.wallet if self.config.paper_trading else self.upbit
        self.order_executor = OrderExecutor(trading_interface, self.risk_manager, self.logger, self.config)
    
    def start(self):
        if not self._validate_fund_safety():
            print("거래 시작 실패: 자금 검증 오류")
            return False
        
        self.is_running = True
        self.is_paused = False
        print("거래 시작!")
        
        try:
            while self.is_running:
                if not self.is_paused:
                    self._simple_trading_loop()
                time.sleep(30)
                
        except KeyboardInterrupt:
            print("\n거래 중지")
            self.stop()
        
        return True
    
    def stop(self):
        self.is_running = False
        self.is_paused = False
        print("거래 종료")
        return True
    
    def pause_trading(self):
        """거래 일시정지/재시작"""
        self.is_paused = not self.is_paused
        status = "일시정지" if self.is_paused else "재시작"
        print(f"거래 {status}")
    
    def emergency_sell_all(self):
        """긴급 매도 (모든 포지션 정리)"""
        try:
            if hasattr(self.risk_manager, 'positions') and self.risk_manager.positions:
                sold_count = 0
                total_amount = 0
                
                for symbol in list(self.risk_manager.positions.keys()):
                    try:
                        pos = self.risk_manager.positions[symbol]
                        if self.config.paper_trading:
                            # 모의거래: 현재가로 가상 매도
                            import pyupbit
                            current_price = pyupbit.get_current_price(symbol)
                            if current_price:
                                quantity = pos.get('quantity', 0)
                                sell_amount = quantity * current_price
                                self.wallet.add_balance('KRW', sell_amount)
                                total_amount += sell_amount
                                del self.risk_manager.positions[symbol]
                                sold_count += 1
                                print(f"긴급 매도: {symbol} - ₩{sell_amount:,.0f}")
                        else:
                            # 실거래: 실제 API 매도 주문
                            # 여기서는 안전을 위해 스킵
                            print(f"실거래 긴급 매도는 수동으로 처리하세요: {symbol}")
                    
                    except Exception as e:
                        print(f"긴급 매도 오류 {symbol}: {e}")
                
                print(f"긴급 매도 완료: {sold_count}개 포지션, 총 ₩{total_amount:,.0f}")
                return True
            else:
                print("매도할 포지션이 없습니다.")
                return True
                
        except Exception as e:
            print(f"긴급 매도 실패: {e}")
            return False
    
    def _simple_trading_loop(self):
        print(f"\n=== {datetime.now().strftime('%H:%M:%S')} 거래 체크 ===")
        
        # 일일 한도 확인
        limit_reached, reason = self.risk_manager.check_daily_limits()
        if limit_reached:
            print(f"일일 한도 도달: {reason}")
            self.stop()
            return
        
        # 각 코인 분석
        for symbol in self.config.target_coins:
            try:
                if not self.db.can_trade_today(symbol) and self.config.daily_trade_limit:
                    continue
                
                signal = self.strategy.analyze_symbol(symbol, True)
                if signal:
                    print(f"{symbol}: {signal['action']} 신호 (신뢰도: {signal['confidence']:.1%})")
                    
                    if signal['action'] == 'BUY':
                        result = self.order_executor.execute_buy_order(signal)
                        if result:
                            self.db.record_trade_session(symbol)
                            print(f"매수 완료: {symbol}")
                    
                    elif signal['action'] == 'SELL' and symbol in self.risk_manager.positions:
                        result = self.order_executor.execute_sell_order(signal)
                        if result:
                            print(f"매도 완료: {symbol} (수익: {result.profit_rate:+.2%})")
                            
            except Exception as e:
                self.logger.log_error('simple_bot', e, {'symbol': symbol})
        
        # 현재 상태 출력
        self._print_status()
    
    def _print_status(self):
        # wallet이 None이 아니고 모의거래 모드일 때만 wallet 사용
        if self.config.paper_trading and self.wallet is not None:
            total_value = self.wallet.get_total_value()
        else:
            total_value = self._get_total_balance()

        profit = total_value - self.config.initial_amount
        profit_rate = (profit / self.config.initial_amount) * 100
        positions = len(self.risk_manager.positions) if hasattr(self.risk_manager, 'positions') else 0

        print(f"자산: ₩{total_value:,.0f} | 수익: ₩{profit:+,.0f} ({profit_rate:+.2f}%) | 포지션: {positions}개")
    
    def _get_total_balance(self):
        try:
            # 모의거래 모드이고 wallet이 있는 경우
            if self.config.paper_trading and self.wallet is not None:
                return self.wallet.get_total_value()
            # 실거래 모드 또는 wallet이 없는 경우
            elif hasattr(self, 'upbit') and self.upbit is not None:
                import pyupbit
                total = self.upbit.get_balance("KRW")
                balances = self.upbit.get_balances()
                for balance in balances:
                    if balance['currency'] != 'KRW' and float(balance['balance']) > 0:
                        symbol = f"KRW-{balance['currency']}"
                        current_price = pyupbit.get_current_price(symbol)
                        if current_price:
                            total += float(balance['balance']) * current_price
                return total
            else:
                return self.config.initial_amount
        except Exception as e:
            print(f"잔고 조회 오류: {e}")
            return self.config.initial_amount
    
    def _get_coin_balances(self):
        """코인별 잔고 조회"""
        try:
            coin_balances = {}
            
            if self.config.paper_trading and hasattr(self, 'wallet'):
                # 모의거래: VirtualWallet에서 조회
                for currency, balance in self.wallet.balances.items():
                    if currency != 'KRW' and balance > 0:
                        coin_balances[currency] = float(balance)
            else:
                # 실거래: 업비트 API에서 조회
                if hasattr(self, 'upbit'):
                    balances = self.upbit.get_balances()
                    for balance in balances:
                        if balance['currency'] != 'KRW' and float(balance['balance']) > 0:
                            coin_balances[balance['currency']] = float(balance['balance'])
            
            return coin_balances
            
        except Exception as e:
            print(f"코인 잔고 조회 오류: {e}")
            return {}
        
    def _validate_fund_safety(self) -> bool:
        """자금 검증"""
        try:
            if self.config.paper_trading:
                return True  # 모의거래는 검증 생략
            
            actual_balance = self.upbit.get_balance("KRW")
            configured_amount = self.config.initial_amount
            
            print(f"자금 검증 - 실제 잔고: ₩{actual_balance:,.0f}, 설정 금액: ₩{configured_amount:,.0f}")
            
            if configured_amount > actual_balance:
                print(f"❌ 거래 불가: 설정금액 ₩{configured_amount:,.0f} > 실제잔고 ₩{actual_balance:,.0f}")
                print(f"해결방법: config.py에서 initial_amount를 ₩{actual_balance:,.0f} 이하로 설정하세요.")
                return False
            
            if actual_balance < self.config.min_trade_amount:
                print(f"❌ 잔고 부족: ₩{actual_balance:,.0f} < 최소 거래 금액 ₩{self.config.min_trade_amount:,.0f}")
                return False
            
            # 안전 경고
            if configured_amount > actual_balance * 0.8:
                print(f"⚠️ 위험 경고: 설정 금액이 잔고의 {configured_amount/actual_balance*100:.0f}%입니다.")
                print("안전을 위해 잔고의 50% 이하 사용을 권장합니다.")
            
            return True
            
        except Exception as e:
            print(f"자금 검증 실패: {e}")
            return False

# Enhanced HTML UI Dashboard (위에서 만든 코드 import)
from paper_trading_dashboard import create_enhanced_trading_dashboard

def main():
    print("=== 업비트 자동매매 시스템 (Enhanced UI) ===")
    
    # 설정 로드
    config = TradingConfig.load_from_file()
    print(f"모드: {'모의거래' if config.paper_trading else '실거래'}")
    print(f"초기자금: ₩{config.initial_amount:,.0f}")
    print(f"대상코인: {', '.join(config.target_coins)}")
    
    if not config.paper_trading:
        confirm = input("\n🚨 실거래 모드입니다! 계속하시겠습니까? (yes/no): ")
        if confirm.lower() != 'yes':
            return
    
    # 봇 생성
    bot = SimpleTradingBot(config)
    
    # Enhanced HTML UI 실행
    try:
        web_app = create_enhanced_trading_dashboard(bot)
        
        if web_app:
            print("\n🚀 Enhanced 웹 대시보드: http://localhost:5000")
            print("📱 실시간 데이터 연동, API 제어, 거래 내역 등 모든 기능 포함")
            print("⏹️ Ctrl+C로 종료")
            
            web_app.run(host='0.0.0.0', port=5000, debug=False)
        else:
            print("웹 대시보드 생성 실패")
            
    except KeyboardInterrupt:
        print("\n시스템 종료")
        bot.stop()
    except Exception as e:
        print(f"시스템 오류: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()