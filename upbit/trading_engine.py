#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
개선된 매매 엔진 모듈
"""

import pyupbit
import pandas as pd
import numpy as np
import time
import requests
import ta
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from decimal import Decimal, ROUND_DOWN

from config import TradingConfig, TradeResult, VirtualWallet
from logging_manager import TradingLogger


class MarketDataCollector:
    """시장 데이터 수집 클래스 (기존 유지)"""
    
    def __init__(self, access_key: str, secret_key: str, logger: TradingLogger):
        # 모의거래 모드에서는 API 키 불필요
        if access_key and secret_key:
            self.upbit = pyupbit.Upbit(access=access_key, secret=secret_key)
        else:
            self.upbit = None
        self.logger = logger
        
    def get_market_data(self, symbol: str) -> Dict:
        """종합 시장 데이터 수집 (기존 유지)"""
        try:
            # 현재 가격 정보
            current_price = pyupbit.get_current_price(symbol)
            
            # OHLCV 데이터
            df = pyupbit.get_ohlcv(symbol, interval="minute15", count=100)
            if df is None or len(df) < 50:
                return {}
            
            # 기술적 지표 계산
            indicators = self._calculate_indicators(df)
            
            # 거래량 분석
            volume_analysis = self._analyze_volume(df)
            
            # 김치 프리미엄 계산
            kimchi_premium = self._get_kimchi_premium(symbol)
            
            # 24시간 변화율
            price_24h_change = (current_price - df.iloc[-24]['close']) / df.iloc[-24]['close'] if len(df) >= 24 else 0
            
            return {
                'symbol': symbol,
                'current_price': current_price,
                'price_change_24h': price_24h_change,
                'volume_ratio': volume_analysis['volume_ratio'],
                'kimchi_premium': kimchi_premium,
                'indicators': indicators,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.log_error('market_data', e, {'symbol': symbol})
            return {}
    
    def _calculate_indicators(self, df: pd.DataFrame) -> Dict:
        """기술적 지표 계산 (기존 유지)"""
        try:
            indicators = {}
            
            # RSI
            indicators['rsi'] = ta.momentum.RSIIndicator(df['close']).rsi().iloc[-1]
            
            # MACD
            macd = ta.trend.MACD(df['close'])
            indicators['macd'] = macd.macd().iloc[-1]
            indicators['macd_signal'] = macd.macd_signal().iloc[-1]
            indicators['macd_histogram'] = macd.macd_diff().iloc[-1]
            
            # 볼린저 밴드
            bb = ta.volatility.BollingerBands(df['close'])
            bb_upper = bb.bollinger_hband().iloc[-1]
            bb_lower = bb.bollinger_lband().iloc[-1]
            current_price = df['close'].iloc[-1]
            indicators['bb_position'] = (current_price - bb_lower) / (bb_upper - bb_lower)
            
            # 이동평균
            ma20 = df['close'].rolling(20).mean().iloc[-1]
            ma50 = df['close'].rolling(50).mean().iloc[-1]
            indicators['ma_trend'] = 1 if current_price > ma20 > ma50 else -1 if current_price < ma20 < ma50 else 0
            
            # 변동성
            indicators['volatility'] = df['close'].pct_change().std()
            
            return indicators
            
        except Exception as e:
            self.logger.log_error('indicators', e)
            return {}
    
    def _analyze_volume(self, df: pd.DataFrame) -> Dict:
        """거래량 분석 (기존 유지)"""
        try:
            recent_volume = df['volume'].iloc[-5:].mean()
            avg_volume = df['volume'].iloc[-20:-5].mean()
            volume_ratio = recent_volume / avg_volume if avg_volume > 0 else 1
            
            return {
                'volume_ratio': volume_ratio,
                'recent_volume': recent_volume,
                'avg_volume': avg_volume,
                'volume_trend': 'increasing' if volume_ratio > 1.5 else 'decreasing' if volume_ratio < 0.7 else 'stable'
            }
            
        except Exception:
            return {'volume_ratio': 1, 'volume_trend': 'unknown'}
    
    def _get_kimchi_premium(self, symbol: str) -> float:
        """김치 프리미엄 계산 (기존 유지)"""
        try:
            # 업비트 가격
            upbit_price = pyupbit.get_current_price(symbol)
            if not upbit_price:
                return 0
            
            # 심볼에서 코인명 추출
            coin = symbol.split('-')[1]
            
            # 바이낸스 가격 (USD)
            binance_url = f"https://api.binance.com/api/v3/ticker/price?symbol={coin}USDT"
            response = requests.get(binance_url, timeout=5)
            
            if response.status_code == 200:
                binance_data = response.json()
                binance_price_usd = float(binance_data['price'])
                
                # USD/KRW 환율 조회
                exchange_rate = self._get_usd_krw_rate()
                binance_price_krw = binance_price_usd * exchange_rate
                
                premium = (upbit_price - binance_price_krw) / binance_price_krw * 100
                return premium
            
            return 0
            
        except Exception as e:
            self.logger.log_error('kimchi_premium', e, {'symbol': symbol})
            return 0
    
    def _get_usd_krw_rate(self) -> float:
        """USD/KRW 환율 조회 (기존 유지)"""
        try:
            response = requests.get("https://api.exchangerate-api.com/v4/latest/USD", timeout=5)
            if response.status_code == 200:
                data = response.json()
                return data['rates'].get('KRW', 1400)
            return 1400
        except:
            return 1400


class TradingStrategy:
    """거래 전략 클래스 (기존 유지 + 일일 거래 제한 추가)"""
    
    def __init__(self, config: TradingConfig, market_collector: MarketDataCollector, logger: TradingLogger):
        self.config = config
        self.market_collector = market_collector
        self.logger = logger
        
    def analyze_symbol(self, symbol: str, can_trade_today: bool = True) -> Optional[Dict]:
        """개별 심볼 분석 - 일일 거래 제한 확인 추가"""
        try:
            # 일일 거래 제한 확인
            if self.config.daily_trade_limit and not can_trade_today:
                self.logger.log_info('trading_strategy', f"{symbol} - 일일 거래 제한으로 분석 생략")
                return None
            
            market_data = self.market_collector.get_market_data(symbol)
            if not market_data or not isinstance(market_data, dict):
                self.logger.log_warning('trading_strategy', f"{symbol} - 시장 데이터 없음")
                return None
            
            # 시장 데이터 로깅
            current_price = market_data.get('current_price', 0)
            price_change_24h = market_data.get('price_change_24h', 0)
            volume_ratio = market_data.get('volume_ratio', 1)
            kimchi_premium = market_data.get('kimchi_premium', 0)
            
            self.logger.log_info('trading_strategy', 
                               f"{symbol} 시장데이터 - 가격: ₩{current_price:,.0f}, "
                               f"24h변화: {price_change_24h:+.2%}, "
                               f"거래량비: {volume_ratio:.2f}x, "
                               f"김치프리미엄: {kimchi_premium:+.2f}%")
            
            # 기술적 지표 로깅
            indicators = market_data.get('indicators', {})
            if indicators:
                rsi = indicators.get('rsi', 50)
                macd = indicators.get('macd', 0)
                macd_histogram = indicators.get('macd_histogram', 0)
                bb_position = indicators.get('bb_position', 0.5)
                ma_trend = indicators.get('ma_trend', 0)
                
                self.logger.log_info('trading_strategy',
                                   f"{symbol} 기술지표 - RSI: {rsi:.1f}, "
                                   f"MACD: {macd:.6f}, MACD히스토: {macd_histogram:.6f}, "
                                   f"볼밴위치: {bb_position:.3f}, MA추세: {ma_trend}")
            
            signals = []
            
            # 전략별 신호 생성 및 로깅
            try:
                momentum_signals = self._momentum_strategy(market_data)
                if momentum_signals:
                    for sig in momentum_signals:
                        self.logger.log_info('trading_strategy',
                                           f"{symbol} 모멘텀전략 - {sig['action']} 신호 "
                                           f"(신뢰도: {sig['confidence']:.1%}, 전략: {sig['strategy']})")
                signals.extend(momentum_signals)
                
                reversion_signals = self._mean_reversion_strategy(market_data)
                if reversion_signals:
                    for sig in reversion_signals:
                        self.logger.log_info('trading_strategy',
                                           f"{symbol} 평균회귀전략 - {sig['action']} 신호 "
                                           f"(신뢰도: {sig['confidence']:.1%}, 전략: {sig['strategy']})")
                signals.extend(reversion_signals)
                
                premium_signals = self._kimchi_premium_strategy(market_data)
                if premium_signals:
                    for sig in premium_signals:
                        self.logger.log_info('trading_strategy',
                                           f"{symbol} 김치프리미엄전략 - {sig['action']} 신호 "
                                           f"(신뢰도: {sig['confidence']:.1%}, 프리미엄: {kimchi_premium:+.2f}%)")
                signals.extend(premium_signals)
                
                volume_signals = self._volume_breakout_strategy(market_data)
                if volume_signals:
                    for sig in volume_signals:
                        self.logger.log_info('trading_strategy',
                                           f"{symbol} 거래량돌파전략 - {sig['action']} 신호 "
                                           f"(신뢰도: {sig['confidence']:.1%}, 거래량: {volume_ratio:.2f}x)")
                signals.extend(volume_signals)
                
            except Exception as e:
                self.logger.log_error('trading_strategy', e, {'symbol': symbol, 'action': 'signal_generation'})
                return None
            
            # 신호가 없는 경우의 상세한 이유 로깅 (기존 유지)
            if not signals:
                reasons = []
                
                if indicators:
                    rsi = indicators.get('rsi', 50)
                    macd_histogram = indicators.get('macd_histogram', 0)
                    ma_trend = indicators.get('ma_trend', 0)
                    
                    if not (50 < rsi < 70):
                        reasons.append(f"RSI={rsi:.1f}(50-70 범위밖)")
                    if macd_histogram <= 0:
                        reasons.append(f"MACD히스토={macd_histogram:.6f}(양수아님)")
                    if ma_trend <= 0:
                        reasons.append(f"MA추세={ma_trend}(상승아님)")
                    if volume_ratio <= 1.5:
                        reasons.append(f"거래량={volume_ratio:.2f}x(1.5x미만)")
                
                if abs(kimchi_premium) < 3.0:
                    reasons.append(f"김치프리미엄={kimchi_premium:.2f}%(3%미만)")
                
                if volume_ratio < 3.0 or abs(price_change_24h) < 0.05:
                    reasons.append(f"거래량돌파조건미달(거래량={volume_ratio:.2f}x, 가격변화={price_change_24h:.2%})")
                
                self.logger.log_info('trading_strategy', 
                                   f"{symbol} 신호없음 - 이유: {', '.join(reasons) if reasons else '조건미달'}")
                return None
            
            # 신호 종합 평가 (기존 유지)
            buy_signals = [s for s in signals if s.get('action') == 'BUY']
            sell_signals = [s for s in signals if s.get('action') == 'SELL']
            
            self.logger.log_info('trading_strategy',
                               f"{symbol} 신호집계 - BUY: {len(buy_signals)}개, SELL: {len(sell_signals)}개")
            
            if len(buy_signals) > len(sell_signals):
                action = 'BUY'
                confidence = sum(s.get('confidence', 0) for s in buy_signals) / len(buy_signals)
                strategies = [s.get('strategy', 'unknown') for s in buy_signals]
            elif len(sell_signals) > len(buy_signals):
                action = 'SELL'
                confidence = sum(s.get('confidence', 0) for s in sell_signals) / len(sell_signals)
                strategies = [s.get('strategy', 'unknown') for s in sell_signals]
            else:
                self.logger.log_info('trading_strategy', f"{symbol} - BUY/SELL 신호 동수로 무효")
                return None
            
            final_confidence = min(confidence, 0.95)
            
            self.logger.log_info('trading_strategy',
                               f"{symbol} 최종신호 - {action} (신뢰도: {final_confidence:.1%}) "
                               f"전략: {', '.join(strategies)}")
            
            return {
                'symbol': symbol,
                'action': action,
                'confidence': final_confidence,
                'price': current_price,
                'strategies': strategies,
                'market_data': market_data
            }
            
        except Exception as e:
            self.logger.log_error('trading_strategy', e, {'symbol': symbol})
            return None
    
    def _momentum_strategy(self, market_data: Dict) -> List[Dict]:
        """모멘텀 전략 (기존 유지)"""
        signals = []
        indicators = market_data.get('indicators', {})
        
        rsi = indicators.get('rsi', 50)
        macd_histogram = indicators.get('macd_histogram', 0)
        ma_trend = indicators.get('ma_trend', 0)
        volume_ratio = market_data.get('volume_ratio', 1)
        
        # 강한 상승 모멘텀
        if (rsi > 50 and rsi < 70 and 
            macd_histogram > 0 and 
            ma_trend > 0 and 
            volume_ratio > 1.5):
            
            signals.append({
                'action': 'BUY',
                'confidence': 0.8,
                'strategy': 'momentum_bullish'
            })
        
        # 강한 하락 모멘텀
        elif (rsi < 50 and rsi > 30 and 
              macd_histogram < 0 and 
              ma_trend < 0 and 
              volume_ratio > 1.2):
            
            signals.append({
                'action': 'SELL',
                'confidence': 0.7,
                'strategy': 'momentum_bearish'
            })
        
        return signals
    
    def _mean_reversion_strategy(self, market_data: Dict) -> List[Dict]:
        """평균 회귀 전략 (기존 유지)"""
        signals = []
        indicators = market_data.get('indicators', {})
        
        rsi = indicators.get('rsi', 50)
        bb_position = indicators.get('bb_position', 0.5)
        volatility = indicators.get('volatility', 0)
        
        # 과매도 상태에서 반등 기대
        if rsi < 30 and bb_position < 0.1 and volatility < 0.05:
            signals.append({
                'action': 'BUY',
                'confidence': 0.75,
                'strategy': 'mean_reversion_oversold'
            })
        
        # 과매수 상태에서 조정 기대
        elif rsi > 70 and bb_position > 0.9:
            signals.append({
                'action': 'SELL',
                'confidence': 0.7,
                'strategy': 'mean_reversion_overbought'
            })
        
        return signals
    
    def _kimchi_premium_strategy(self, market_data: Dict) -> List[Dict]:
        """김치 프리미엄 전략 (기존 유지)"""
        signals = []
        kimchi_premium = market_data.get('kimchi_premium', 0)
        
        # 높은 프리미엄 - 매수 기회
        if kimchi_premium > 3.0:
            confidence = min(0.6 + (kimchi_premium - 3) * 0.1, 0.9)
            signals.append({
                'action': 'BUY',
                'confidence': confidence,
                'strategy': 'kimchi_premium_high'
            })
        
        # 마이너스 프리미엄 - 위험 신호
        elif kimchi_premium < -1.0:
            signals.append({
                'action': 'SELL',
                'confidence': 0.6,
                'strategy': 'kimchi_premium_negative'
            })
        
        return signals
    
    def _volume_breakout_strategy(self, market_data: Dict) -> List[Dict]:
        """거래량 돌파 전략 (기존 유지)"""
        signals = []
        volume_ratio = market_data.get('volume_ratio', 1)
        price_change = market_data.get('price_change_24h', 0)
        
        # 거래량 급증 + 가격 상승
        if volume_ratio > 3.0 and price_change > 0.05:
            confidence = min(0.7 + (volume_ratio - 3) * 0.05, 0.9)
            signals.append({
                'action': 'BUY',
                'confidence': confidence,
                'strategy': 'volume_breakout_bullish'
            })
        
        # 거래량 급증 + 가격 하락 (매도 압력)
        elif volume_ratio > 2.5 and price_change < -0.03:
            signals.append({
                'action': 'SELL',
                'confidence': 0.7,
                'strategy': 'volume_breakout_bearish'
            })
        
        return signals


class RiskManager:
    """개선된 리스크 관리 클래스"""
    
    def __init__(self, config: TradingConfig, logger: TradingLogger):
        self.config = config
        self.logger = logger
        self.daily_pnl = 0.0
        self.daily_trades = 0
        self.positions = {}
        self.max_daily_trades = 100
        
        # 추가된 속성
        self.daily_invested_amount = 0.0  # 일일 투자 금액 추적
        self.daily_profit_amount = 0.0    # 일일 실현 수익 추적
        
    def check_daily_limits(self) -> Tuple[bool, str]:
        """일일 한도 확인 - 개선된 계산"""
        # 실제 투자금액 기준으로 수익률 계산
        if self.daily_invested_amount > 0:
            actual_daily_return = self.daily_profit_amount / self.daily_invested_amount
        else:
            actual_daily_return = 0.0
        
        if actual_daily_return >= self.config.max_daily_profit:
            return True, f"일일 수익 목표 달성: {actual_daily_return:.2%} (₩{self.daily_profit_amount:+,.0f})"
        elif actual_daily_return <= -self.config.max_daily_loss:
            return True, f"일일 손실 한도 도달: {actual_daily_return:.2%} (₩{self.daily_profit_amount:+,.0f})"
        elif self.daily_trades >= self.max_daily_trades:
            return True, f"일일 거래 횟수 초과: {self.daily_trades}"
        
        return False, "정상"
    
    def calculate_position_size(self, balance: float, confidence: float, symbol: str) -> float:
        """포지션 크기 계산 - 개선된 안전성"""
        try:
            # 입력값 검증 및 기본값 처리
            if balance is None or balance <= 0:
                self.logger.log_warning('risk_manager', f"잘못된 잔고: {balance}")
                return 0.0
            
            if confidence is None:
                confidence = 0.5
                
            try:
                balance = float(balance)
                confidence = float(confidence)
            except (ValueError, TypeError):
                self.logger.log_warning('risk_manager', f"숫자 변환 실패: balance={balance}, confidence={confidence}")
                return 0.0
            
            # 최소 거래 금액 확인
            max_usable_balance = min(balance, self.config.initial_amount)

            self.logger.log_info('risk_manager',
                            f"자금제한 적용 - 실제잔고: ₩{balance:,.0f}, 사용한도: ₩{max_usable_balance:,.0f}")

            # 최소 거래 금액 확인 (수정된 잔고 기준)
            if max_usable_balance < self.config.min_trade_amount:
                self.logger.log_info('risk_manager', 
                                f"사용 가능 잔고가 최소 거래 금액 미만: ₩{max_usable_balance:,.0f} < ₩{self.config.min_trade_amount:,.0f}")
                return 0.0

            # 기본 할당 비율 (보수적으로 조정)
            base_allocation = 0.2  # 20%로 조정
            
            # 신뢰도에 따른 조정 (0.5 ~ 1.0)
            confidence_multiplier = 0.5 + (confidence * 0.5)
            
            # 현재 포지션 수에 따른 조정
            try:
                if hasattr(self, 'positions') and isinstance(self.positions, dict):
                    position_count = len(self.positions)
                else:
                    position_count = 0
                    
                # 포지션이 많을수록 신규 포지션 크기 감소
                if position_count >= self.config.max_positions:
                    self.logger.log_info('risk_manager', f"최대 포지션 수 도달: {position_count}")
                    return 0.0
                elif position_count >= 2:
                    base_allocation *= 0.7  # 30% 감소
                    
            except Exception as e:
                self.logger.log_warning('risk_manager', f"포지션 수 확인 오류: {e}")
                position_count = 0
            
            # 복리 효과 적용
            if self.config.compound_interest and self.daily_profit_amount > 0:
                # 수익이 있을 때 포지션 크기 약간 증가
                compound_multiplier = 1 + min(self.daily_profit_amount / balance * 0.1, 0.05)  # 최대 5% 증가
                base_allocation *= compound_multiplier
            
            # 최종 포지션 크기 계산
            position_size = max_usable_balance * base_allocation * confidence_multiplier

            # 최대 포지션 크기 제한 (수정된 잔고 기준)
            max_position_value = max_usable_balance * self.config.max_position_size
            position_size = min(position_size, max_position_value)
                        
            # 최소 거래 금액 재확인
            if position_size < self.config.min_trade_amount:
                self.logger.log_info('risk_manager', 
                                   f"계산된 포지션 크기가 최소 거래 금액 미만: ₩{position_size:.0f}")
                return 0.0
            
            self.logger.log_info('risk_manager', 
                               f"포지션 크기 계산: ₩{position_size:,.0f} "
                               f"(잔고: ₩{balance:,.0f}, 신뢰도: {confidence:.1%}, "
                               f"포지션수: {position_count})")
            
            return position_size
            
        except Exception as e:
            self.logger.log_error('risk_manager', e, {'action': 'calculate_position_size'})
            return 0.0
    
    def calculate_fees(self, amount: float, action: str = 'buy') -> float:
        """수수료 계산 (기존 유지)"""
        if not self.config.include_fees:
            return 0
        
        return amount * self.config.upbit_fee_rate
    
    def update_pnl(self, trade_result: TradeResult):
        """손익 업데이트 - 정확한 계산"""
        if trade_result.side == 'sell' and trade_result.invested_amount > 0:
            # 매도시에만 실현 손익 반영
            self.daily_profit_amount += trade_result.profit_amount
            self.daily_invested_amount += trade_result.invested_amount
            
            # 기존 방식 호환성을 위한 비율 계산
            if self.daily_invested_amount > 0:
                self.daily_pnl = self.daily_profit_amount / self.daily_invested_amount
            
        elif trade_result.side == 'buy':
            # 매수시에는 투자 금액만 추가
            self.daily_invested_amount += trade_result.invested_amount
        
        self.daily_trades += 1
        
        self.logger.log_info('risk_manager', 
                           f"손익 업데이트 - 일일 수익: ₩{self.daily_profit_amount:+,.0f}, "
                           f"투자금액: ₩{self.daily_invested_amount:,.0f}, "
                           f"수익률: {self.daily_pnl:+.2%}, 거래: {self.daily_trades}회")
    
    def reset_daily(self):
        """일일 리셋 - 개선된 리셋"""
        self.daily_pnl = 0.0
        self.daily_trades = 0
        self.daily_invested_amount = 0.0
        self.daily_profit_amount = 0.0
        
        self.logger.log_info('risk_manager', "일일 손익 및 거래 통계 리셋")
    
    def check_stop_loss(self, symbol: str, current_price: float) -> bool:
        """손절매 확인 - 개선된 안전성 (기존 유지)"""
        try:
            # 입력값 검증
            if not symbol or current_price is None:
                return False
            
            try:
                current_price = float(current_price)
            except (ValueError, TypeError):
                self.logger.log_warning('risk_manager', f"current_price 변환 실패: {current_price}")
                return False
            
            # 포지션 존재 확인
            if not hasattr(self, 'positions') or not isinstance(self.positions, dict):
                return False
            
            if symbol not in self.positions:
                return False
            
            position = self.positions[symbol]
            if not isinstance(position, dict):
                self.logger.log_warning('risk_manager', f"포지션 데이터가 딕셔너리가 아님: {type(position)}")
                return False
            
            # 손절가 확인
            stop_loss_price = position.get('stop_loss')
            if stop_loss_price is None:
                # 손절가가 설정되지 않은 경우 진입가 기준으로 계산
                entry_price = position.get('entry_price')
                if entry_price is None:
                    self.logger.log_warning('risk_manager', f"{symbol} 진입가 정보 없음")
                    return False
                
                try:
                    entry_price = float(entry_price)
                    stop_loss_price = entry_price * (1 - self.config.stop_loss_rate)
                    # 계산된 손절가를 저장
                    self.positions[symbol]['stop_loss'] = stop_loss_price
                except (ValueError, TypeError):
                    self.logger.log_warning('risk_manager', f"진입가 변환 실패: {entry_price}")
                    return False
            else:
                try:
                    stop_loss_price = float(stop_loss_price)
                except (ValueError, TypeError):
                    self.logger.log_warning('risk_manager', f"손절가 변환 실패: {stop_loss_price}")
                    return False
            
            # 손절매 조건 확인
            if current_price <= stop_loss_price:
                loss_rate = (current_price - position.get('entry_price', current_price)) / position.get('entry_price', current_price)
                
                self.logger.log_warning('risk_manager', 
                                      f"손절매 발동: {symbol}, "
                                      f"현재가: ₩{current_price:,.0f}, "
                                      f"손절가: ₩{stop_loss_price:,.0f}, "
                                      f"손실률: {loss_rate:.2%}")
                return True
            
            return False
            
        except Exception as e:
            self.logger.log_error('risk_manager', e, {'action': 'check_stop_loss', 'symbol': symbol})
            return False


class OrderExecutor:
    """개선된 주문 실행 클래스"""
    
    def __init__(self, upbit_or_wallet, risk_manager: RiskManager, logger: TradingLogger, config: TradingConfig):
        self.upbit_or_wallet = upbit_or_wallet  # 실제 Upbit 또는 VirtualWallet
        self.risk_manager = risk_manager
        self.logger = logger
        self.config = config
        self.is_paper_trading = isinstance(upbit_or_wallet, VirtualWallet)
        
        if self.is_paper_trading:
            self.logger.log_info('order_executor', "모의거래 모드로 초기화")
        else:
            self.logger.log_info('order_executor', "실거래 모드로 초기화")
    
    def execute_buy_order(self, signal: Dict) -> Optional[TradeResult]:
        """개선된 매수 주문 실행"""
        try:
            symbol = signal.get('symbol', '')
            confidence = signal.get('confidence', 0.5)
            current_price = signal.get('price', 0)
            
            if not symbol or not current_price:
                self.logger.log_warning('order_executor', f"잘못된 신호 데이터: {signal}")
                return None
            
            # 잔고 확인
            if self.is_paper_trading:
                krw_balance = self.upbit_or_wallet.get_balance("KRW")
                portfolio_value_before = self.upbit_or_wallet.get_total_value()
            else:
                krw_balance = self.upbit_or_wallet.get_balance("KRW")
                portfolio_value_before = self._get_real_portfolio_value()
            
            if krw_balance < self.config.min_trade_amount:
                self.logger.log_warning('order_executor', f"잔고 부족: ₩{krw_balance:,.0f}")
                return None
            
            # 포지션 크기 계산
            position_size = self.risk_manager.calculate_position_size(
                krw_balance, confidence, symbol
            )
            
            if position_size < self.config.min_trade_amount:
                self.logger.log_info('order_executor', f"포지션 크기 부족: ₩{position_size:,.0f}")
                return None
            
            # 수수료 계산
            fee = self.risk_manager.calculate_fees(position_size, 'buy')
            actual_buy_amount = position_size - fee
            quantity = actual_buy_amount / current_price
            
            # 매수 주문 실행
            if self.is_paper_trading:
                result = self.upbit_or_wallet.buy_market_order(symbol, position_size)
            else:
                result = self.upbit_or_wallet.buy_market_order(symbol, position_size)
            
            if result and 'uuid' in result:
                # 거래 결과 생성 (개선된 TradeResult 사용)
                trade_result = TradeResult(
                    id=result['uuid'],
                    timestamp=datetime.now(),
                    symbol=symbol,
                    side='buy',
                    quantity=quantity,
                    price=current_price,
                    amount=position_size,
                    fee=fee,
                    invested_amount=position_size,  # 매수시 투자 금액
                    profit_amount=0.0,  # 매수시에는 0
                    profit_rate=0.0,    # 매수시에는 0
                    portfolio_value_before=portfolio_value_before,
                    portfolio_value_after=portfolio_value_before - position_size,
                    strategy=', '.join(signal.get('strategies', ['unknown'])),
                    is_paper_trade=self.is_paper_trading
                )
                
                # 포지션 추가
                # 포지션 통합 로직 추가
                if symbol in self.risk_manager.positions:
                    # 기존 포지션과 통합
                    existing = self.risk_manager.positions[symbol]
                    old_quantity = existing['quantity']
                    old_invested = existing['total_invested']
                    
                    new_total_quantity = old_quantity + quantity
                    new_total_invested = old_invested + position_size
                    new_avg_price = new_total_invested / new_total_quantity
                    
                    self.risk_manager.positions[symbol] = {
                        'avg_price': new_avg_price,
                        'quantity': new_total_quantity,
                        'total_invested': new_total_invested,
                        'entry_time': existing['entry_time'],  # 첫 매수 시간 유지
                        'last_buy_time': datetime.now(),
                        'stop_loss': new_avg_price * (1 - self.risk_manager.config.stop_loss_rate),
                        'buy_orders': existing.get('buy_orders', []) + [result['uuid']]
                    }
                    
                    self.logger.log_info('order_executor', 
                                        f"{symbol} 포지션 통합: 평균단가 ₩{new_avg_price:,.0f}, "
                                        f"총 수량 {new_total_quantity:.8f}")
                else:
                    # 신규 포지션 생성
                    self.risk_manager.positions[symbol] = {
                        'avg_price': current_price,
                        'quantity': quantity,
                        'total_invested': position_size,
                        'entry_time': datetime.now(),
                        'last_buy_time': datetime.now(),
                        'stop_loss': current_price * (1 - self.risk_manager.config.stop_loss_rate),
                        'buy_orders': [result['uuid']]
                    }
                
                # 손익 업데이트
                self.risk_manager.update_pnl(trade_result)
                
                self.logger.log_trade(trade_result, f"신뢰도: {confidence:.1%}")
                return trade_result
            
            return None
            
        except Exception as e:
            self.logger.log_error('order_executor', e, {'action': 'buy', 'symbol': symbol})
            return None
    
    def execute_sell_order(self, signal: Dict) -> Optional[TradeResult]:
        """개선된 매도 주문 실행"""
        try:
            # 입력 검증
            if not isinstance(signal, dict):
                self.logger.log_warning('order_executor', f"잘못된 신호 타입: {type(signal)}")
                return None
            
            symbol = signal.get('symbol', '')
            current_price = signal.get('price', 0)
            
            if not symbol or not current_price:
                self.logger.log_warning('order_executor', f"필수 데이터 누락 - symbol: {symbol}, price: {current_price}")
                return None
            
            # 포지션 확인
            if symbol not in self.risk_manager.positions:
                self.logger.log_info('order_executor', f"{symbol} 보유 포지션 없음")
                return None
            
            position = self.risk_manager.positions[symbol]
            
            # 코인명 추출
            try:
                currency = symbol.split('-')[1] if '-' in symbol else symbol
            except (AttributeError, IndexError):
                self.logger.log_warning('order_executor', f"심볼 파싱 실패: {symbol}")
                return None
            
            # 실제 보유량 확인
            if self.is_paper_trading:
                coin_balance = self.upbit_or_wallet.get_balance(currency)
                portfolio_value_before = self.upbit_or_wallet.get_total_value()
            else:
                coin_balance = self._get_coin_balance(currency)
                portfolio_value_before = self._get_real_portfolio_value()
            
            if coin_balance is None or coin_balance <= 0:
                self.logger.log_info('order_executor', f"{currency} 보유량 없음")
                return None
            
            # 포지션 정보
            entry_price = position.get('entry_price', current_price)
            invested_amount = position.get('invested_amount', 0)
            quantity = position.get('quantity', coin_balance)
            
            self.logger.log_info('order_executor', 
                               f"{symbol} 매도 시도: {coin_balance:.8f} {currency} "
                               f"(투자금액: ₩{invested_amount:,.0f})")
            
            # 매도 주문 실행
            try:
                if self.is_paper_trading:
                    result = self.upbit_or_wallet.sell_market_order(symbol, coin_balance)
                else:
                    result = self.upbit_or_wallet.sell_market_order(symbol, coin_balance)
                
                if not result or not isinstance(result, dict) or 'uuid' not in result:
                    self.logger.log_warning('order_executor', f"매도 주문 실패: {result}")
                    return None
                
            except Exception as e:
                self.logger.log_error('order_executor', e, {'action': 'sell_order', 'symbol': symbol})
                return None
            
            # 정확한 수익 계산
# 정확한 수익 계산 - 수정됨
            gross_amount = coin_balance * current_price
            fee = self.risk_manager.calculate_fees(gross_amount, 'sell')
            net_amount = gross_amount - fee

            # 포지션에서 실제 투자금액 가져오기 (핵심 수정)
            position = self.risk_manager.positions.get(symbol, {})
            actual_invested = position.get('total_invested', invested_amount)
            actual_quantity = position.get('quantity', coin_balance)

            # 부분 매도인 경우 비례 계산
            if coin_balance < actual_quantity:
                proportional_invested = actual_invested * (coin_balance / actual_quantity)
            else:
                proportional_invested = actual_invested

            # 수익률 계산
            profit_amount = net_amount - proportional_invested
            profit_rate = profit_amount / proportional_invested if proportional_invested > 0 else 0

            # 비현실적인 수익률 제한 (1220% 같은 오류 방지)
            if abs(profit_rate) > 10:  # 1000% 초과시 오류로 간주
                self.logger.log_warning('order_executor', 
                                    f"비현실적 수익률 감지: {profit_rate:.2%}, 재계산 필요")
                profit_rate = (current_price - position.get('avg_price', current_price)) / position.get('avg_price', current_price)
                        
            # 거래 결과 생성
            trade_result = TradeResult(
                id=result['uuid'],
                timestamp=datetime.now(),
                symbol=symbol,
                side='sell',
                quantity=coin_balance,
                price=current_price,
                amount=gross_amount,
                fee=fee,
                invested_amount=invested_amount,  # 원래 투자한 금액
                profit_amount=profit_amount,     # 절대 수익 금액
                profit_rate=profit_rate,         # 투자 대비 수익률
                portfolio_value_before=portfolio_value_before,
                portfolio_value_after=portfolio_value_before + profit_amount,
                strategy=', '.join(signal.get('strategies', ['manual_sell'])),
                is_paper_trade=self.is_paper_trading
            )
            
            # 포지션 제거
            del self.risk_manager.positions[symbol]
            
            # 손익 업데이트
            self.risk_manager.update_pnl(trade_result)
            
            self.logger.log_trade(trade_result)
            return trade_result
            
        except Exception as e:
            self.logger.log_error('order_executor', e, {'action': 'sell_order_general'})
            return None
    
    def _get_coin_balance(self, currency: str) -> float:
        """실제 코인 잔고 조회"""
        try:
            balances = self.upbit_or_wallet.get_balances()
            for balance in balances:
                if balance['currency'] == currency:
                    return float(balance['balance'])
            return 0.0
        except:
            return 0.0
    
    def _get_real_portfolio_value(self) -> float:
        """실제 포트폴리오 가치 계산"""
        try:
            total = self.upbit_or_wallet.get_balance('KRW')
            balances = self.upbit_or_wallet.get_balances()
            
            for balance in balances:
                if balance['currency'] != 'KRW' and float(balance['balance']) > 0:
                    symbol = f"KRW-{balance['currency']}"
                    current_price = pyupbit.get_current_price(symbol)
                    if current_price:
                        total += float(balance['balance']) * current_price
            
            return total
        except:
            return 0.0
    
    def emergency_sell_all(self) -> List[TradeResult]:
        """긴급 전량 매도 - 모의거래 지원"""
        results = []
        
        try:
            self.logger.log_critical('order_executor', "긴급 전량 매도 시작")
            
            if self.is_paper_trading:
                balances = self.upbit_or_wallet.get_balances()
            else:
                balances = self.upbit_or_wallet.get_balances()
            
            for balance in balances:
                if balance['currency'] != 'KRW' and float(balance['balance']) > 0:
                    symbol = f"KRW-{balance['currency']}"
                    
                    try:
                        current_price = pyupbit.get_current_price(symbol)
                        
                        if self.is_paper_trading:
                            result = self.upbit_or_wallet.sell_market_order(symbol, float(balance['balance']))
                        else:
                            result = self.upbit_or_wallet.sell_market_order(symbol, float(balance['balance']))
                        
                        if result and 'uuid' in result:
                            sell_amount = float(balance['balance']) * current_price
                            fee = self.risk_manager.calculate_fees(sell_amount, 'sell')
                            
                            # 포지션 정보 확인
                            invested_amount = 0
                            if symbol in self.risk_manager.positions:
                                invested_amount = self.risk_manager.positions[symbol].get('invested_amount', sell_amount)
                            
                            trade_result = TradeResult(
                                id=result['uuid'],
                                timestamp=datetime.now(),
                                symbol=symbol,
                                side='sell',
                                quantity=float(balance['balance']),
                                price=current_price,
                                amount=sell_amount,
                                fee=fee,
                                invested_amount=invested_amount,
                                profit_amount=sell_amount - fee - invested_amount,
                                profit_rate=((sell_amount - fee - invested_amount) / invested_amount) if invested_amount > 0 else 0,
                                strategy='emergency_sell',
                                is_paper_trade=self.is_paper_trading
                            )
                            
                            results.append(trade_result)
                            self.logger.log_trade(trade_result, "긴급 매도")
                    
                    except Exception as e:
                        self.logger.log_error('order_executor', e, 
                                            {'action': 'emergency_sell', 'symbol': symbol})
            
            # 모든 포지션 초기화
            self.risk_manager.positions.clear()
            
            self.logger.log_critical('order_executor', f"긴급 전량 매도 완료: {len(results)}건")
            
        except Exception as e:
            self.logger.log_error('order_executor', e, {'action': 'emergency_sell_all'})
        
        return results