#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
메인 거래 봇 모듈
"""

import pyupbit
import time
import threading
import schedule
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import asdict

from config import TradingConfig, APIConfig
from logging_manager import DatabaseManager, TradingLogger, PerformanceTracker
from trading_engine import MarketDataCollector, TradingStrategy, RiskManager, OrderExecutor
from ai_notification import ClaudeInterface, TelegramNotifier, AlertManager


class TradingBot:
    """메인 거래 봇 클래스"""
    
    def __init__(self, config: TradingConfig = None):
        # 설정 초기화
        if config is None:
            config = TradingConfig.load_from_file()
        api_config = APIConfig()
        self.access_key, self.secret_key = api_config.get_upbit_keys()
        
        # 상태 변수
        self.is_running = False
        self.is_paused = False
        self.last_telegram_notification = None
        
        # 핵심 컴포넌트 초기화
        self._initialize_components()
        
        # 스레드 관련
        self.trading_thread = None
        self.claude_thread = None
        self.telegram_thread = None
        
    def _initialize_components(self):
        """핵심 컴포넌트 초기화"""
        try:
            # 데이터베이스 및 로깅
            self.db = DatabaseManager()
            self.logger = TradingLogger(self.db)
            self.performance_tracker = PerformanceTracker(self.db, self.logger)
            
            # 업비트 API
            self.upbit = pyupbit.Upbit(access=self.access_key, secret=self.secret_key)
            
            # 거래 엔진
            self.market_collector = MarketDataCollector(self.access_key, self.secret_key, self.logger)
            self.strategy = TradingStrategy(self.config, self.market_collector, self.logger)
            self.risk_manager = RiskManager(self.config, self.logger)
            self.order_executor = OrderExecutor(self.upbit, self.risk_manager, self.logger)
            
            # AI 및 알림
            self.claude = ClaudeInterface(self.logger)
            self.telegram = TelegramNotifier(self.logger)
            self.alert_manager = AlertManager(self.telegram, self.logger)
            
            self.logger.log_info('trading_bot', "모든 컴포넌트 초기화 완료")
            
        except Exception as e:
            print(f"컴포넌트 초기화 실패: {e}")
            raise
    
    def start(self) -> bool:
        """거래 시작 - 자금 안전성 검증 추가"""
        if self.is_running:
            self.logger.log_warning('trading_bot', "이미 거래가 실행 중입니다.")
            return False
        
        # API 연결 테스트
        if not self._test_api_connection():
            return False
        
        # 자금 안전성 검증 (핵심 추가)
        if not self._validate_fund_safety():
            return False
        
        self.is_running = True
        self.is_paused = False
        
        # 스레드 시작
        self._start_threads()
        
        # 스케줄 설정
        self._setup_schedules()
        
        self.logger.log_info('trading_bot', "거래 시작!")
        # 텔레그램 알림
        self.alert_manager.send_trade_alert(
            type('SystemEvent', (), {
                'symbol': 'SYSTEM',
                'side': 'start',
                'amount': 0,
                'timestamp': datetime.now(),
                'profit': 0,
                'profit_rate': 0
            })(),
            {'message': '자동매매가 시작되었습니다!'}
        )
        
        return True
    
    def stop(self) -> bool:
        """거래 중지"""
        if not self.is_running:
            return False
        
        self.is_running = False
        
        # 스레드 종료 대기
        self._stop_threads()
        
        self.logger.log_info('trading_bot', "거래 중지!")
        self.alert_manager.send_emergency_alert("자동매매가 중지되었습니다.")
        
        return True
    
    def pause_trading(self):
        """거래 일시 정지"""
        self.is_paused = True
        self.logger.log_info('trading_bot', "거래 일시 정지")
        self.alert_manager.send_emergency_alert("거래가 일시 정지되었습니다.")
    
    def resume_trading(self):
        """거래 재개"""
        self.is_paused = False
        self.logger.log_info('trading_bot', "거래 재개")
        self.alert_manager.send_emergency_alert("거래가 재개되었습니다.")
    
    def emergency_sell_all(self) -> bool:
        """긴급 전량 매도"""
        try:
            self.logger.log_critical('trading_bot', "긴급 전량 매도 시작")
            
            results = self.order_executor.emergency_sell_all()
            
            # 결과 알림
            if results:
                message = f"긴급 전량 매도 완료\n총 {len(results)}건 처리"
                for result in results:
                    message += f"\n• {result.symbol}: ₩{result.amount:,.0f}"
            else:
                message = "매도할 포지션이 없습니다."
            
            self.alert_manager.send_emergency_alert(message)
            
            return True
            
        except Exception as e:
            self.logger.log_error('trading_bot', e)
            return False
    
    def _test_api_connection(self) -> bool:
        """API 연결 테스트"""
        try:
            balances = self.upbit.get_balances()
            if not balances:
                self.logger.log_error('trading_bot', Exception("업비트 API 연결 실패"))
                return False
            
            self.logger.log_info('trading_bot', "API 연결 테스트 성공")
            return True
            
        except Exception as e:
            self.logger.log_error('trading_bot', e)
            return False
    
    def _start_threads(self):
        """스레드 시작"""
        # 메인 거래 스레드
        self.trading_thread = threading.Thread(target=self._trading_loop, daemon=True)
        self.trading_thread.start()
        
        # Claude 모니터링 스레드
        self.claude_thread = threading.Thread(target=self._claude_loop, daemon=True)
        self.claude_thread.start()
        
        # 텔레그램 알림 스레드
        self.telegram_thread = threading.Thread(target=self._telegram_loop, daemon=True)
        self.telegram_thread.start()
        
        self.logger.log_info('trading_bot', "모든 스레드 시작 완료")
    
    def _stop_threads(self):
        """스레드 종료"""
        threads = [
            (self.trading_thread, "거래"),
            (self.claude_thread, "Claude"),
            (self.telegram_thread, "텔레그램")
        ]
        
        for thread, name in threads:
            if thread and thread.is_alive():
                self.logger.log_info('trading_bot', f"{name} 스레드 종료 대기...")
                thread.join(timeout=10)
                if thread.is_alive():
                    self.logger.log_warning('trading_bot', f"{name} 스레드 강제 종료")
    
    def _setup_schedules(self):
        """스케줄 설정"""
        # 일일 리셋 (오전 9시)
        schedule.every().day.at("09:00").do(self.risk_manager.reset_daily)
        
        # 일일 성과 계산 및 저장 (오후 11시 59분)
        schedule.every().day.at("23:59").do(self._daily_performance_update)
        
        self.logger.log_info('trading_bot', "스케줄 설정 완료")
    
    def _daily_performance_update(self):
        """일일 성과 업데이트"""
        try:
            performance = self.performance_tracker.calculate_daily_performance()
            if performance:
                self.performance_tracker.save_daily_performance(performance)
                
                # 일일 보고서 생성 및 전송
                report = self.performance_tracker.generate_performance_report(1)
                self.alert_manager.send_daily_report(report)
                
        except Exception as e:
            self.logger.log_error('trading_bot', e)
    
    def _trading_loop(self):
        """메인 거래 루프"""
        self.logger.log_info('trading_bot', "거래 루프 시작")
        loop_count = 0
        
        while self.is_running:
            try:
                loop_count += 1
                self.logger.log_info('trading_bot', f"=== 거래 루프 #{loop_count} 시작 ===")
                
                # 스케줄 실행
                schedule.run_pending()
                
                # 일시 정지 확인
                if self.is_paused:
                    self.logger.log_info('trading_bot', "거래 일시정지 중 - 10초 대기")
                    time.sleep(10)
                    continue
                
                # 일일 한도 확인
                limit_reached, reason = self.risk_manager.check_daily_limits()
                if limit_reached:
                    self.logger.log_info('trading_bot', f"일일 한도 도달: {reason}")
                    self.alert_manager.send_emergency_alert(f"일일 한도 도달\n{reason}\n거래가 중지됩니다.")
                    self.stop()
                    break
                
                # 각 코인별 분석 및 거래
                self.logger.log_info('trading_bot', f"거래 신호 분석 시작 (루프 #{loop_count})")
                self._process_trading_signals()
                
                # 손절매 확인
                if self.risk_manager.positions:
                    self.logger.log_info('trading_bot', f"손절매 확인 - 활성 포지션: {len(self.risk_manager.positions)}개")
                    self._check_stop_losses()
                else:
                    self.logger.log_info('trading_bot', "활성 포지션 없음 - 손절매 확인 생략")
                
                self.logger.log_info('trading_bot', f"거래 루프 #{loop_count} 완료 - 10초 대기")
                
                # 대기
                time.sleep(10)  # 10초 간격
                
            except Exception as e:
                self.logger.log_error('trading_bot', e, {'loop_count': loop_count})
                time.sleep(60)
        
        self.logger.log_info('trading_bot', "거래 루프 종료")
    
    def _process_trading_signals(self):
        """거래 신호 처리"""
        self.logger.log_info('trading_bot', f"거래 신호 분석 시작 - 대상 코인: {len(self.config.target_coins)}개")
        
        for symbol in self.config.target_coins:
            try:
                self.logger.log_info('trading_bot', f"{symbol} 분석 중...")
                
                # 거래 신호 분석
                signal = self.strategy.analyze_symbol(symbol)
                if not signal:
                    self.logger.log_info('trading_bot', f"{symbol} - 거래 신호 없음")
                    continue
                
                self.logger.log_info('trading_bot', 
                                   f"{symbol} - {signal['action']} 신호 (신뢰도: {signal['confidence']:.1%})")
                
                # Claude 분석 확인 (매수 시에만)
                if signal['action'] == 'BUY' and self.claude.should_intervene():
                    self.logger.log_info('trading_bot', f"{symbol} - Claude 분석 요청")
                    
                    claude_analysis = self.claude.analyze_market_condition(
                        signal['market_data'], 
                        self.risk_manager.positions, 
                        self.config
                    )
                    
                    # Claude가 부정적 판단 시 거래 중지
                    if claude_analysis['recommendation'] == 'SELL':
                        self.logger.log_info('trading_bot', 
                                           f"{symbol} - Claude 분석으로 매수 신호 무시 (추천: {claude_analysis['recommendation']})")
                        continue
                    else:
                        self.logger.log_info('trading_bot', 
                                           f"{symbol} - Claude 분석 통과 (추천: {claude_analysis['recommendation']})")
                
                # 거래 실행
                self.logger.log_info('trading_bot', f"{symbol} - 거래 실행 시도")
                self._execute_signal(signal)
                
            except Exception as e:
                self.logger.log_error('trading_bot', e, {'symbol': symbol, 'action': 'process_signals'})
                continue
        
        self.logger.log_info('trading_bot', "거래 신호 분석 완료")
    
    def _execute_signal(self, signal: Dict):
        """거래 신호 실행"""
        try:
            if signal['action'] == 'BUY':
                trade_result = self.order_executor.execute_buy_order(signal)
                if trade_result:
                    context = {
                        'daily_pnl': self.risk_manager.daily_pnl,
                        'positions_count': len(self.risk_manager.positions)
                    }
                    self.alert_manager.send_trade_alert(trade_result, context)
            
            elif signal['action'] == 'SELL':
                trade_result = self.order_executor.execute_sell_order(signal)
                if trade_result:
                    context = {
                        'daily_pnl': self.risk_manager.daily_pnl,
                        'positions_count': len(self.risk_manager.positions)
                    }
                    self.alert_manager.send_trade_alert(trade_result, context)
                    
        except Exception as e:
            self.logger.log_error('trading_bot', e, {'signal': signal})
    
    def _check_stop_losses(self):
        """손절매 확인"""
        try:
            if not hasattr(self.risk_manager, 'positions') or not isinstance(self.risk_manager.positions, dict):
                return
            
            # 포지션 리스트를 복사하여 반복 중 수정 문제 방지
            positions_to_check = list(self.risk_manager.positions.keys())
            
            for symbol in positions_to_check:
                try:
                    # 포지션이 여전히 존재하는지 확인
                    if symbol not in self.risk_manager.positions:
                        continue
                    
                    current_price = pyupbit.get_current_price(symbol)
                    if not current_price:
                        continue
                    
                    if self.risk_manager.check_stop_loss(symbol, current_price):
                        # 손절매 실행
                        signal = {
                            'symbol': symbol,
                            'action': 'SELL',
                            'price': current_price,
                            'strategies': ['stop_loss']
                        }
                        
                        trade_result = self.order_executor.execute_sell_order(signal)
                        if trade_result:
                            profit = getattr(trade_result, 'profit', 0)
                            profit_rate = getattr(trade_result, 'profit_rate', 0)
                            
                            self.alert_manager.send_emergency_alert(
                                f"손절매 실행: {symbol}\n"
                                f"손실: {profit:+,.0f}원 ({profit_rate:+.2%})"
                            )
                            
                except Exception as e:
                    self.logger.log_error('trading_bot', e, {'context': 'stop_loss_check', 'symbol': symbol})
                    continue
                        
        except Exception as e:
            self.logger.log_error('trading_bot', e, {'context': 'check_stop_losses'})
    
    def _claude_loop(self):
        """Claude 모니터링 루프"""
        self.logger.log_info('trading_bot', "Claude 모니터링 시작")
        
        while self.is_running:
            try:
                time.sleep(self.config.claude_interval * 60)
                
                if not self.is_running or self.is_paused:
                    continue
                
                # 포트폴리오 분석
                market_data = self._get_portfolio_market_data()
                
                claude_analysis = self.claude.analyze_market_condition(
                    market_data, 
                    self.risk_manager.positions, 
                    self.config
                )
                
                # Claude 추천사항 알림
                if claude_analysis['confidence'] > 0.8:
                    self.alert_manager.send_claude_alert(claude_analysis)
                
                # 위험 수준이 높을 때 긴급 개입
                if claude_analysis['risk_assessment'] > 0.8:
                    self.claude.emergency_intervention("고위험 상황 감지", "REDUCE_POSITIONS")
                    self.alert_manager.send_emergency_alert(
                        f"Claude 긴급 알림\n"
                        f"고위험 상황 감지 (위험도: {claude_analysis['risk_assessment']:.1%})\n"
                        f"포지션 축소 권장"
                    )
            
            except Exception as e:
                self.logger.log_error('trading_bot', e)
        
        self.logger.log_info('trading_bot', "Claude 모니터링 종료")
    
    def _telegram_loop(self):
        """텔레그램 정기 보고 루프"""
        self.logger.log_info('trading_bot', "텔레그램 알림 시작")
        
        while self.is_running:
            try:
                time.sleep(self.config.telegram_interval * 60)
                
                if not self.is_running or self.is_paused:
                    continue
                
                # 정기 보고서 생성 및 전송
                report = self._generate_status_report()
                self.alert_manager.send_daily_report(report)
                
                self.last_telegram_notification = datetime.now()
                
            except Exception as e:
                self.logger.log_error('trading_bot', e)
        
        self.logger.log_info('trading_bot', "텔레그램 알림 종료")
    
    def _get_portfolio_market_data(self) -> Dict:
        """포트폴리오 전체 시장 데이터"""
        try:
            total_data = {
                'total_symbols': len(self.config.target_coins),
                'active_positions': len(self.risk_manager.positions),
                'avg_kimchi_premium': 0,
                'market_sentiment': 0.5,
                'total_volume_ratio': 1.0
            }
            
            # 각 코인의 데이터 수집 및 평균 계산
            valid_data = []
            for symbol in self.config.target_coins:
                try:
                    market_data = self.market_collector.get_market_data(symbol)
                    if market_data and isinstance(market_data, dict):
                        valid_data.append(market_data)
                except Exception as e:
                    self.logger.log_error('trading_bot', e, {'symbol': symbol})
                    continue
            
            if valid_data:
                try:
                    total_data['avg_kimchi_premium'] = sum(
                        d.get('kimchi_premium', 0) for d in valid_data if isinstance(d, dict)
                    ) / len(valid_data)
                    total_data['total_volume_ratio'] = sum(
                        d.get('volume_ratio', 1) for d in valid_data if isinstance(d, dict)
                    ) / len(valid_data)
                except (TypeError, ZeroDivisionError):
                    pass
            
            return total_data
            
        except Exception as e:
            self.logger.log_error('trading_bot', e)
            return {
                'total_symbols': 0,
                'active_positions': 0,
                'avg_kimchi_premium': 0,
                'market_sentiment': 0.5,
                'total_volume_ratio': 1.0
            }
    
    def _generate_status_report(self) -> str:
        """상태 보고서 생성"""
        try:
            # 안전한 잔고 조회
            try:
                total_balance = self.get_total_balance()
            except Exception as e:
                self.logger.log_error('trading_bot', e, {'context': 'generate_report_balance'})
                total_balance = self.config.initial_amount
            
            daily_pnl_amount = total_balance - self.config.initial_amount
            
            # 안전한 거래 내역 조회
            try:
                today_trades = self.db.get_daily_trades()
                win_trades = [t for t in today_trades if hasattr(t, 'profit') and t.profit > 0]
                win_rate = len(win_trades) / len(today_trades) * 100 if today_trades else 0
            except Exception as e:
                self.logger.log_error('trading_bot', e, {'context': 'generate_report_trades'})
                today_trades = []
                win_rate = 0
            
            # 안전한 포지션 정보 수집
            position_info = []
            try:
                if hasattr(self.risk_manager, 'positions') and isinstance(self.risk_manager.positions, dict):
                    for symbol, pos in self.risk_manager.positions.items():
                        try:
                            if isinstance(pos, dict) and 'entry_price' in pos:
                                current_price = pyupbit.get_current_price(symbol)
                                if current_price and pos.get('entry_price'):
                                    unrealized_pnl = (current_price - pos['entry_price']) / pos['entry_price']
                                    position_info.append(f"{symbol}: {unrealized_pnl:+.1%}")
                        except Exception as pe:
                            self.logger.log_error('trading_bot', pe, {'context': 'position_calc', 'symbol': symbol})
                            continue
            except Exception as e:
                self.logger.log_error('trading_bot', e, {'context': 'generate_report_positions'})
            
            # 안전한 손익 데이터 접근
            try:
                daily_pnl = getattr(self.risk_manager, 'daily_pnl', 0.0)
                daily_trades_count = getattr(self.risk_manager, 'daily_trades', 0)
            except Exception as e:
                self.logger.log_error('trading_bot', e, {'context': 'generate_report_pnl'})
                daily_pnl = 0.0
                daily_trades_count = 0
            
            # 안전한 포지션 수 계산
            try:
                positions_count = len(self.risk_manager.positions) if hasattr(self.risk_manager, 'positions') else 0
            except Exception:
                positions_count = 0
            
            report = f"""거래 현황 보고

총 잔고: ₩{total_balance:,.0f}
일일 손익: {daily_pnl:+.2%} (₩{daily_pnl_amount:+,.0f})
거래 횟수: {daily_trades_count}회
승률: {win_rate:.1f}%

활성 포지션 ({positions_count}개)
{chr(10).join(position_info) if position_info else '없음'}

시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
            
            return report
            
        except Exception as e:
            self.logger.log_error('trading_bot', e, {'context': 'generate_status_report'})
            return f"보고서 생성 실패: {str(e)}"
    
    def get_total_balance(self) -> float:
        """총 잔고 계산"""
        try:
            total = self.upbit.get_balance("KRW")
            
            balances = self.upbit.get_balances()
            for balance in balances:
                if balance['currency'] != 'KRW' and float(balance['balance']) > 0:
                    symbol = f"KRW-{balance['currency']}"
                    current_price = pyupbit.get_current_price(symbol)
                    if current_price:
                        coin_value = float(balance['balance']) * current_price
                        total += coin_value
            
            return total
            
        except Exception as e:
            self.logger.log_error('trading_bot', e)
            return self.config.initial_amount
    
    def get_status(self) -> Dict:
        """현재 상태 조회"""
        try:
            # 안전한 포지션 정보 수집
            position_details = {}
            try:
                if hasattr(self.risk_manager, 'positions') and isinstance(self.risk_manager.positions, dict):
                    position_details = dict(self.risk_manager.positions)
            except Exception as e:
                self.logger.log_error('trading_bot', e, {'context': 'get_status_positions'})
                position_details = {}
            
            # 안전한 잔고 조회
            try:
                total_balance = self.get_total_balance()
            except Exception as e:
                self.logger.log_error('trading_bot', e, {'context': 'get_total_balance'})
                total_balance = self.config.initial_amount
            
            # 안전한 알림 요약 조회
            try:
                alert_summary = self.alert_manager.get_alert_summary()
            except Exception as e:
                self.logger.log_error('trading_bot', e, {'context': 'get_alert_summary'})
                alert_summary = {}
            
            # 안전한 설정 변환
            try:
                config_dict = asdict(self.config)
            except Exception as e:
                self.logger.log_error('trading_bot', e, {'context': 'asdict_config'})
                config_dict = {}
            
            return {
                'is_running': getattr(self, 'is_running', False),
                'is_paused': getattr(self, 'is_paused', False),
                'daily_pnl': getattr(self.risk_manager, 'daily_pnl', 0.0),
                'daily_trades': getattr(self.risk_manager, 'daily_trades', 0),
                'total_balance': total_balance,
                'positions': len(position_details),
                'position_details': position_details,
                'last_update': datetime.now().isoformat(),
                'config': config_dict,
                'alert_summary': alert_summary
            }
            
        except Exception as e:
            self.logger.log_error('trading_bot', e, {'context': 'get_status'})
            # 기본 상태 반환
            return {
                'is_running': False,
                'is_paused': False,
                'daily_pnl': 0.0,
                'daily_trades': 0,
                'total_balance': self.config.initial_amount,
                'positions': 0,
                'position_details': {},
                'last_update': datetime.now().isoformat(),
                'config': {},
                'alert_summary': {}
            }
    
    def update_config(self, new_config: Dict) -> bool:
        """설정 업데이트"""
        try:
            for key, value in new_config.items():
                if hasattr(self.config, key):
                    setattr(self.config, key, value)
                    self.logger.log_info('trading_bot', f"설정 업데이트: {key} = {value}")
            
            return True
            
        except Exception as e:
            self.logger.log_error('trading_bot', e)
            return False
    
    def set_telegram_credentials(self, bot_token: str, chat_id: str):
        """텔레그램 인증 정보 설정"""
        self.telegram.set_credentials(bot_token, chat_id)
    
    def _validate_fund_safety(self) -> bool:
        """자금 안전성 검증"""
        try:
            # 실제 잔고 조회
            actual_balance = self.upbit.get_balance("KRW")
            configured_amount = self.config.initial_amount
            
            self.logger.log_info('trading_bot', 
                            f"자금 검증 - 실제 잔고: ₩{actual_balance:,.0f}, "
                            f"설정 금액: ₩{configured_amount:,.0f}")
            
            # 설정 금액이 실제 잔고보다 큰 경우
            if configured_amount > actual_balance:
                error_msg = (
                    f"❌ 거래 시작 불가: 설정 금액이 실제 잔고를 초과합니다.\n"
                    f"설정 금액: ₩{configured_amount:,.0f}\n"
                    f"실제 잔고: ₩{actual_balance:,.0f}\n"
                    f"부족 금액: ₩{configured_amount - actual_balance:,.0f}\n"
                    f"해결방법: config.py에서 initial_amount를 ₩{actual_balance:,.0f} 이하로 설정하세요."
                )
                
                self.logger.log_critical('trading_bot', error_msg)
                print(error_msg)
                
                # 텔레그램 긴급 알림
                if hasattr(self, 'alert_manager'):
                    self.alert_manager.send_emergency_alert(error_msg)
                
                return False
            
            # 최소 금액 검증
            if actual_balance < self.config.min_trade_amount:
                error_msg = f"❌ 잔고 부족: ₩{actual_balance:,.0f} < 최소 거래 금액 ₩{self.config.min_trade_amount:,.0f}"
                self.logger.log_critical('trading_bot', error_msg)
                print(error_msg)
                return False
            
            # 안전 경고 (잔고의 80% 이상 설정시)
            if configured_amount > actual_balance * 0.8:
                warning_msg = (
                    f"⚠️ 위험 경고: 설정 금액이 잔고의 {configured_amount/actual_balance*100:.0f}%입니다.\n"
                    f"안전을 위해 잔고의 50% 이하 사용을 권장합니다."
                )
                self.logger.log_warning('trading_bot', warning_msg)
                print(warning_msg)
            
            return True
            
        except Exception as e:
            error_msg = f"자금 검증 실패: {e}"
            self.logger.log_error('trading_bot', e, {'context': 'fund_validation'})
            print(error_msg)
            return False