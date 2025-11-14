#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
업비트 자동매매 시스템 - 완전판
5% 손익 제한, Claude 개입, 텔레그램 알림 포함
"""

import pyupbit
import pandas as pd
import numpy as np
import time
import json
import requests
import asyncio
import websockets
import threading
import queue
import logging
import schedule
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from decimal import Decimal, ROUND_DOWN
import sqlite3
import hashlib
import hmac
import base64
from flask import Flask, request, jsonify, render_template_string
from flask_socketio import SocketIO, emit
import ta
import ccxt

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('trading_bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class TradingConfig:
    """거래 설정 클래스"""
    initial_amount: float = 1000000  # 최초 투자금액
    max_daily_profit: float = 0.05   # 일일 최대 수익률 (5%)
    max_daily_loss: float = 0.05     # 일일 최대 손실률 (5%)
    max_positions: int = 6           # 최대 동시 포지션
    max_position_size: float = 0.25  # 단일 포지션 최대 비중 (25%)
    stop_loss_rate: float = 0.01     # 손절매 비율 (1%)
    claude_interval: int = 30        # Claude 개입 주기 (분)
    telegram_interval: int = 30      # 텔레그램 알림 주기 (분)
    include_fees: bool = True        # 수수료 포함 여부
    upbit_fee_rate: float = 0.0005   # 업비트 수수료 (0.05%)
    target_coins: List[str] = None   # 거래 대상 코인
    
    def __post_init__(self):
        if self.target_coins is None:
            self.target_coins = ['KRW-BTC', 'KRW-ETH', 'KRW-XRP', 'KRW-ADA', 'KRW-DOGE']

@dataclass
class TradeResult:
    """거래 결과 클래스"""
    id: str
    timestamp: datetime
    symbol: str
    side: str  # 'buy' or 'sell'
    amount: float
    price: float
    fee: float
    profit: float = 0.0
    profit_rate: float = 0.0
    strategy: str = ''
    claude_action: bool = False

class DatabaseManager:
    """데이터베이스 관리 클래스"""
    
    def __init__(self, db_path: str = 'trading_bot.db'):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """데이터베이스 초기화"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 거래 기록 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id TEXT PRIMARY KEY,
                timestamp TEXT,
                symbol TEXT,
                side TEXT,
                amount REAL,
                price REAL,
                fee REAL,
                profit REAL,
                profit_rate REAL,
                strategy TEXT,
                claude_action BOOLEAN
            )
        ''')
        
        # 일일 성과 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_performance (
                date TEXT PRIMARY KEY,
                total_profit REAL,
                total_profit_rate REAL,
                total_trades INTEGER,
                win_rate REAL,
                max_drawdown REAL
            )
        ''')
        
        # Claude 분석 기록 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS claude_analysis (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                market_data TEXT,
                recommendation TEXT,
                confidence REAL,
                reasoning TEXT,
                executed BOOLEAN
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def save_trade(self, trade: TradeResult):
        """거래 기록 저장"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO trades VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            trade.id, trade.timestamp.isoformat(), trade.symbol, trade.side,
            trade.amount, trade.price, trade.fee, trade.profit, trade.profit_rate,
            trade.strategy, trade.claude_action
        ))
        
        conn.commit()
        conn.close()
    
    def get_daily_trades(self, date: str = None) -> List[TradeResult]:
        """일일 거래 기록 조회"""
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM trades 
            WHERE date(timestamp) = ? 
            ORDER BY timestamp DESC
        ''', (date,))
        
        rows = cursor.fetchall()
        conn.close()
        
        trades = []
        for row in rows:
            trade = TradeResult(
                id=row[0],
                timestamp=datetime.fromisoformat(row[1]),
                symbol=row[2],
                side=row[3],
                amount=row[4],
                price=row[5],
                fee=row[6],
                profit=row[7],
                profit_rate=row[8],
                strategy=row[9],
                claude_action=bool(row[10])
            )
            trades.append(trade)
        
        return trades

class TelegramNotifier:
    """텔레그램 알림 클래스"""
    
    def __init__(self, bot_token: str = None, chat_id: str = None):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}" if bot_token else None
    
    def set_credentials(self, bot_token: str, chat_id: str):
        """텔레그램 인증 정보 설정"""
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
    
    async def send_message(self, message: str, parse_mode: str = 'Markdown') -> bool:
        """텔레그램 메시지 전송"""
        if not self.base_url or not self.chat_id:
            logger.warning("텔레그램 설정이 없습니다.")
            return False
        
        try:
            url = f"{self.base_url}/sendMessage"
            data = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': parse_mode
            }
            
            response = requests.post(url, data=data, timeout=10)
            if response.status_code == 200:
                logger.info("텔레그램 메시지 전송 완료")
                return True
            else:
                logger.error(f"텔레그램 메시지 전송 실패: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"텔레그램 메시지 전송 오류: {e}")
            return False
    
    def send_message_sync(self, message: str) -> bool:
        """동기식 메시지 전송"""
        return asyncio.run(self.send_message(message))

class ClaudeInterface:
    """Claude AI 인터페이스 (확장된 버전)"""
    
    def __init__(self):
        self.intervention_queue = queue.Queue()
        self.analysis_history = []
        self.last_analysis_time = None
        self.analysis_interval = 30  # 분
        
    def analyze_market_condition(self, market_data: Dict, positions: Dict, config: TradingConfig) -> Dict:
        """시장 상황 종합 분석"""
        try:
            analysis = {
                'timestamp': datetime.now().isoformat(),
                'market_sentiment': self._analyze_sentiment(market_data),
                'technical_score': self._calculate_technical_score(market_data),
                'risk_assessment': self._assess_risk(positions, config),
                'recommendation': 'HOLD',
                'confidence': 0.5,
                'reasoning': '',
                'suggested_actions': [],
                'position_adjustments': {}
            }
            
            # 종합 점수 계산
            sentiment_weight = 0.3
            technical_weight = 0.4
            risk_weight = 0.3
            
            overall_score = (
                analysis['market_sentiment'] * sentiment_weight +
                analysis['technical_score'] * technical_weight +
                (1 - analysis['risk_assessment']) * risk_weight
            )
            
            # 추천 결정
            if overall_score > 0.75:
                analysis['recommendation'] = 'BUY'
                analysis['confidence'] = min(overall_score, 0.95)
                analysis['reasoning'] = '강한 매수 신호: 기술적 지표 양호, 시장 심리 긍정적'
            elif overall_score < 0.25:
                analysis['recommendation'] = 'SELL'
                analysis['confidence'] = min(1 - overall_score, 0.95)
                analysis['reasoning'] = '매도 신호: 리스크 요인 증가, 부정적 지표'
            else:
                analysis['recommendation'] = 'HOLD'
                analysis['confidence'] = 0.6
                analysis['reasoning'] = '혼재된 신호, 현재 포지션 유지 권장'
            
            # 구체적 액션 제안
            analysis['suggested_actions'] = self._generate_action_suggestions(
                overall_score, positions, market_data
            )
            
            self.analysis_history.append(analysis)
            self.last_analysis_time = datetime.now()
            
            return analysis
            
        except Exception as e:
            logger.error(f"Claude 시장 분석 오류: {e}")
            return self._default_analysis()
    
    def _analyze_sentiment(self, market_data: Dict) -> float:
        """시장 심리 분석"""
        try:
            sentiment_score = 0.5  # 기본값
            
            # 김치 프리미엄 분석
            kimchi_premium = market_data.get('kimchi_premium', 0)
            if kimchi_premium > 3:
                sentiment_score += 0.2
            elif kimchi_premium < 0:
                sentiment_score -= 0.1
            
            # 거래량 분석
            volume_ratio = market_data.get('volume_ratio', 1)
            if volume_ratio > 2:
                sentiment_score += 0.15
            elif volume_ratio < 0.5:
                sentiment_score -= 0.1
            
            # 가격 모멘텀
            price_change = market_data.get('price_change_24h', 0)
            sentiment_score += min(max(price_change / 20, -0.2), 0.2)
            
            return max(0, min(1, sentiment_score))
            
        except Exception:
            return 0.5
    
    def _calculate_technical_score(self, market_data: Dict) -> float:
        """기술적 분석 점수"""
        try:
            indicators = market_data.get('indicators', {})
            
            scores = []
            
            # RSI 점수
            rsi = indicators.get('rsi', 50)
            if 30 <= rsi <= 70:
                rsi_score = 1.0
            elif rsi < 20 or rsi > 80:
                rsi_score = 0.2
            else:
                rsi_score = 0.6
            scores.append(rsi_score)
            
            # MACD 점수
            macd_histogram = indicators.get('macd_histogram', 0)
            macd_score = 0.5 + max(min(macd_histogram * 10, 0.5), -0.5)
            scores.append(macd_score)
            
            # 볼린저 밴드 점수
            bb_position = indicators.get('bb_position', 0.5)
            bb_score = 1 - abs(bb_position - 0.5) * 2
            scores.append(bb_score)
            
            # 이동평균 점수
            ma_trend = indicators.get('ma_trend', 0)
            ma_score = 0.5 + (ma_trend * 0.3)
            scores.append(ma_score)
            
            return sum(scores) / len(scores) if scores else 0.5
            
        except Exception:
            return 0.5
    
    def _assess_risk(self, positions: Dict, config: TradingConfig) -> float:
        """위험도 평가 (0-1, 높을수록 위험)"""
        try:
            risk_factors = []
            
            # 포지션 집중도 리스크
            position_count = len(positions)
            if position_count > config.max_positions:
                risk_factors.append(0.8)
            elif position_count > config.max_positions * 0.75:
                risk_factors.append(0.5)
            else:
                risk_factors.append(0.2)
            
            # 개별 포지션 크기 리스크
            max_position_ratio = max([pos.get('ratio', 0) for pos in positions.values()]) if positions else 0
            if max_position_ratio > config.max_position_size:
                risk_factors.append(0.7)
            else:
                risk_factors.append(0.3)
            
            # 시간 리스크 (포지션 보유 시간)
            long_positions = sum(1 for pos in positions.values() 
                               if pos.get('hold_hours', 0) > 6)
            if long_positions > 2:
                risk_factors.append(0.6)
            else:
                risk_factors.append(0.2)
            
            return sum(risk_factors) / len(risk_factors)
            
        except Exception:
            return 0.5
    
    def _generate_action_suggestions(self, score: float, positions: Dict, market_data: Dict) -> List[str]:
        """구체적 액션 제안"""
        suggestions = []
        
        if score > 0.8:
            suggestions.append("강한 매수 신호: 적극적 진입 고려")
            if len(positions) < 3:
                suggestions.append("포지션 확대 가능")
        elif score > 0.6:
            suggestions.append("선별적 매수: 기술적 지표 양호한 종목 진입")
        elif score < 0.3:
            suggestions.append("위험 신호: 포지션 축소 고려")
            if len(positions) > 2:
                suggestions.append("일부 포지션 청산 권장")
        elif score < 0.4:
            suggestions.append("주의 필요: 신규 진입 자제")
        
        # 김치 프리미엄 기반 제안
        kimchi_premium = market_data.get('kimchi_premium', 0)
        if kimchi_premium > 4:
            suggestions.append("김치 프리미엄 4% 초과: 매수 기회")
        elif kimchi_premium < -1:
            suggestions.append("김치 프리미엄 마이너스: 주의 필요")
        
        return suggestions
    
    def _default_analysis(self) -> Dict:
        """기본 분석 결과"""
        return {
            'timestamp': datetime.now().isoformat(),
            'market_sentiment': 0.5,
            'technical_score': 0.5,
            'risk_assessment': 0.5,
            'recommendation': 'HOLD',
            'confidence': 0.5,
            'reasoning': '분석 오류로 인한 기본 권장사항',
            'suggested_actions': ['시스템 점검 필요'],
            'position_adjustments': {}
        }
    
    def should_intervene(self) -> bool:
        """개입 필요성 판단"""
        if self.last_analysis_time is None:
            return True
        
        elapsed = datetime.now() - self.last_analysis_time
        return elapsed.total_seconds() / 60 >= self.analysis_interval
    
    def emergency_intervention(self, reason: str, action: str) -> Dict:
        """긴급 개입"""
        intervention = {
            'type': 'EMERGENCY',
            'reason': reason,
            'action': action,
            'timestamp': datetime.now().isoformat(),
            'priority': 'HIGH'
        }
        
        self.intervention_queue.put(intervention)
        logger.critical(f"Claude 긴급 개입: {reason} -> {action}")
        
        return intervention

class MarketDataCollector:
    """시장 데이터 수집 클래스"""
    
    def __init__(self, access_key: str, secret_key: str):
        self.upbit = pyupbit.Upbit(access=access_key, secret=secret_key)
        
    def get_market_data(self, symbol: str) -> Dict:
        """종합 시장 데이터 수집"""
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
            logger.error(f"시장 데이터 수집 오류 {symbol}: {e}")
            return {}
    
    def _calculate_indicators(self, df: pd.DataFrame) -> Dict:
        """기술적 지표 계산"""
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
            logger.error(f"지표 계산 오류: {e}")
            return {}
    
    def _analyze_volume(self, df: pd.DataFrame) -> Dict:
        """거래량 분석"""
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
        """김치 프리미엄 계산"""
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
            logger.error(f"김치 프리미엄 계산 오류: {e}")
            return 0
    
    def _get_usd_krw_rate(self) -> float:
        """USD/KRW 환율 조회"""
        try:
            # 실시간 환율 API 사용 (예: exchangerate-api.com)
            response = requests.get("https://api.exchangerate-api.com/v4/latest/USD", timeout=5)
            if response.status_code == 200:
                data = response.json()
                return data['rates'].get('KRW', 1400)  # 기본값 1400
            return 1400
        except:
            return 1400  # 기본값

class AdvancedTradingStrategy:
    """고급 거래 전략 클래스"""
    
    def __init__(self, config: TradingConfig, access_key: str, secret_key: str):
        self.config = config
        self.market_collector = MarketDataCollector(access_key, secret_key)
        
    def analyze_symbol(self, symbol: str) -> Optional[Dict]:
        """개별 심볼 분석"""
        market_data = self.market_collector.get_market_data(symbol)
        if not market_data:
            return None
        
        signals = []
        
        # 전략별 신호 생성
        signals.extend(self._momentum_strategy(market_data))
        signals.extend(self._mean_reversion_strategy(market_data))
        signals.extend(self._kimchi_premium_strategy(market_data))
        signals.extend(self._volume_breakout_strategy(market_data))
        
        if not signals:
            return None
        
        # 신호 종합 평가
        buy_signals = [s for s in signals if s['action'] == 'BUY']
        sell_signals = [s for s in signals if s['action'] == 'SELL']
        
        if len(buy_signals) > len(sell_signals):
            action = 'BUY'
            confidence = sum(s['confidence'] for s in buy_signals) / len(buy_signals)
        elif len(sell_signals) > len(buy_signals):
            action = 'SELL'
            confidence = sum(s['confidence'] for s in sell_signals) / len(sell_signals)
        else:
            return None  # 혼재된 신호
        
        return {
            'symbol': symbol,
            'action': action,
            'confidence': min(confidence, 0.95),
            'price': market_data['current_price'],
            'strategies': [s['strategy'] for s in signals if s['action'] == action],
            'market_data': market_data
        }
    
    def _momentum_strategy(self, market_data: Dict) -> List[Dict]:
        """모멘텀 전략"""
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
        """평균 회귀 전략"""
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
        """김치 프리미엄 전략"""
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
        """거래량 돌파 전략"""
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
    """리스크 관리 클래스"""
    
    def __init__(self, config: TradingConfig):
        self.config = config
        self.daily_pnl = 0.0
        self.daily_trades = 0
        self.positions = {}
        self.max_daily_trades = 100
        
    def check_daily_limits(self) -> Tuple[bool, str]:
        """일일 한도 확인"""
        if self.daily_pnl >= self.config.max_daily_profit:
            return True, f"일일 수익 목표 달성: {self.daily_pnl:.2%}"
        elif self.daily_pnl <= -self.config.max_daily_loss:
            return True, f"일일 손실 한도 도달: {self.daily_pnl:.2%}"
        elif self.daily_trades >= self.max_daily_trades:
            return True, f"일일 거래 횟수 초과: {self.daily_trades}"
        
        return False, "정상"
    
    def calculate_position_size(self, balance: float, confidence: float, symbol: str) -> float:
        """포지션 크기 계산"""
        # 기본 할당 비율
        base_allocation = 0.15  # 15%
        
        # 신뢰도에 따른 조정
        confidence_multiplier = 0.5 + (confidence * 0.5)  # 0.5 ~ 1.0
        
        # 현재 포지션 수에 따른 조정
        position_count = len(self.positions)
        if position_count >= 3:
            base_allocation *= 0.8  # 20% 감소
        
        # 최종 포지션 크기 계산
        position_size = balance * base_allocation * confidence_multiplier
        
        # 최대 한도 제한
        max_position_value = balance * self.config.max_position_size
        position_size = min(position_size, max_position_value)
        
        # 최소 거래 금액 확인 (업비트 5천원 최소)
        if position_size < 5000:
            return 0
        
        return position_size
    
    def calculate_fees(self, amount: float, action: str = 'buy') -> float:
        """수수료 계산"""
        if not self.config.include_fees:
            return 0
        
        return amount * self.config.upbit_fee_rate
    
    def update_pnl(self, trade_result: TradeResult):
        """손익 업데이트"""
        self.daily_pnl += trade_result.profit_rate
        self.daily_trades += 1
        
        logger.info(f"일일 누적 손익: {self.daily_pnl:.2%}, 거래 횟수: {self.daily_trades}")
    
    def reset_daily(self):
        """일일 리셋"""
        self.daily_pnl = 0.0
        self.daily_trades = 0
        logger.info("일일 손익 및 거래 횟수 리셋")

class UpbitTradingBot:
    """메인 거래 봇 클래스"""
    
    def __init__(self, access_key: str, secret_key: str, config: TradingConfig = None):

        ACCESS_KEY = "DqHAiYdOQmoxjYJgp8MhP720ITetfqNl38oep15o"
        SECRET_KEY = "C3mQRe42CoBjL1iSvTfcNial2zB5S97Kjg5hQbsV"
        self.access_key = ACCESS_KEY
        self.secret_key = SECRET_KEY
        self.config = config or TradingConfig()
        
        # 핵심 컴포넌트 초기화
        self.upbit = pyupbit.Upbit(access=ACCESS_KEY, secret=SECRET_KEY)
        print("DEBUG INSTANCE:", type(self.upbit))
        self.risk_manager = RiskManager(self.config)
        self.strategy = AdvancedTradingStrategy(config=self.config,
                                                access_key=self.access_key,
                                                secret_key=self.secret_key)
        self.claude = ClaudeInterface()
        self.telegram = TelegramNotifier()
        self.db = DatabaseManager()
        
        # 상태 변수
        self.is_running = False
        self.is_paused = False
        self.last_telegram_notification = None
        
        # 스레드 및 큐
        self.trading_thread = None
        self.telegram_thread = None
        self.claude_thread = None
        
    def start(self):
        """거래 시작"""
        if self.is_running:
            logger.warning("이미 거래가 실행 중입니다.")
            return False
        
        # API 연결 테스트
        try:
            balances = self.upbit.get_balances()
            if not balances:
                logger.error("업비트 API 연결 실패")
                return False
        except Exception as e:
            logger.error(f"업비트 API 오류: {e}")
            return False
        
        self.is_running = True
        self.is_paused = False
        
        # 메인 거래 스레드 시작
        self.trading_thread = threading.Thread(target=self._trading_loop, daemon=True)
        self.trading_thread.start()
        
        # Claude 모니터링 스레드 시작
        self.claude_thread = threading.Thread(target=self._claude_loop, daemon=True)
        self.claude_thread.start()
        
        # 텔레그램 알림 스레드 시작
        self.telegram_thread = threading.Thread(target=self._telegram_loop, daemon=True)
        self.telegram_thread.start()
        
        # 스케줄 설정
        schedule.every().day.at("09:00").do(self.risk_manager.reset_daily)
        
        logger.info("🚀 업비트 자동매매 시작!")
        self.telegram.send_message_sync("🚀 업비트 자동매매가 시작되었습니다!")
        
        return True
    
    def stop(self):
        """거래 중지"""
        if not self.is_running:
            return False
        
        self.is_running = False
        
        # 스레드 종료 대기
        if self.trading_thread and self.trading_thread.is_alive():
            self.trading_thread.join(timeout=10)
        
        logger.info("⏹️ 업비트 자동매매 중지!")
        self.telegram.send_message_sync("⏹️ 자동매매가 중지되었습니다.")
        
        return True
    
    def _trading_loop(self):
        """메인 거래 루프"""
        while self.is_running:
            try:
                # 스케줄 실행
                schedule.run_pending()
                
                # 일시 정지 확인
                if self.is_paused:
                    time.sleep(30)
                    continue
                
                # 일일 한도 확인
                limit_reached, reason = self.risk_manager.check_daily_limits()
                if limit_reached:
                    logger.info(f"일일 한도 도달: {reason}")
                    self.telegram.send_message_sync(f"🛑 일일 한도 도달\n{reason}\n거래가 중지됩니다.")
                    self.stop()
                    break
                
                # 각 코인별 분석 및 거래
                for symbol in self.config.target_coins:
                    try:
                        # 거래 신호 분석
                        signal = self.strategy.analyze_symbol(symbol)
                        if not signal:
                            continue
                        
                        # Claude 분석 확인
                        if self.claude.should_intervene():
                            claude_analysis = self.claude.analyze_market_condition(
                                signal['market_data'], 
                                self.risk_manager.positions, 
                                self.config
                            )
                            
                            # Claude가 부정적 판단 시 거래 중지
                            if (claude_analysis['recommendation'] == 'SELL' and 
                                signal['action'] == 'BUY'):
                                logger.info(f"Claude 분석으로 {symbol} 매수 신호 무시")
                                continue
                        
                        # 거래 실행
                        self._execute_trade(signal)
                        
                    except Exception as e:
                        logger.error(f"{symbol} 거래 오류: {e}")
                        continue
                
                # 대기
                time.sleep(30)  # 30초 간격
                
            except Exception as e:
                logger.error(f"거래 루프 오류: {e}")
                time.sleep(60)
    
    def _execute_trade(self, signal: Dict):
        """거래 실행"""
        try:
            symbol = signal['symbol']
            action = signal['action']
            confidence = signal['confidence']
            current_price = signal['price']
            
            # 잔고 확인
            krw_balance = self.upbit.get_balance("KRW")
            
            if action == 'BUY' and krw_balance > 5000:
                # 포지션 크기 계산
                position_size = self.risk_manager.calculate_position_size(
                    krw_balance, confidence, symbol
                )
                
                if position_size < 5000:  # 최소 거래 금액
                    return
                
                # 실제 매수 금액 (수수료 포함)
                actual_buy_amount = position_size - fee
                
                # 매수 주문 실행
                result = self.upbit.buy_market_order(symbol, actual_buy_amount)
                
                if result and 'uuid' in result:
                    # 거래 결과 기록
                    trade_result = TradeResult(
                        id=result['uuid'],
                        timestamp=datetime.now(),
                        symbol=symbol,
                        side='buy',
                        amount=actual_buy_amount,
                        price=current_price,
                        fee=fee,
                        strategy=', '.join(signal['strategies'])
                    )
                    
                    # 포지션 추가
                    self.risk_manager.positions[symbol] = {
                        'entry_price': current_price,
                        'amount': actual_buy_amount,
                        'entry_time': datetime.now(),
                        'stop_loss': current_price * (1 - self.config.stop_loss_rate),
                        'uuid': result['uuid']
                    }
                    
                    # DB 저장
                    self.db.save_trade(trade_result)
                    
                    logger.info(f"✅ 매수 완료: {symbol}, 금액: ₩{actual_buy_amount:,.0f}, 수수료: ₩{fee:.0f}")
                    
                    # 텔레그램 알림
                    msg = f"💰 매수 완료\n🔸 {symbol}\n💵 {actual_buy_amount:,.0f}원\n📊 신뢰도: {confidence:.1%}\n📈 전략: {', '.join(signal['strategies'])}"
                    self.telegram.send_message_sync(msg)
            
            elif action == 'SELL':
                # 보유 수량 확인
                coin_name = symbol.split('-')[1]
                coin_balance = self.upbit.get_balance(coin_name)
                
                if coin_balance > 0:
                    # 매도 주문 실행
                    result = self.upbit.sell_market_order(symbol, coin_balance)
                    
                    if result and 'uuid' in result and symbol in self.risk_manager.positions:
                        position = self.risk_manager.positions[symbol]
                        
                        # 수익 계산
                        entry_price = position['entry_price']
                        sell_amount = coin_balance * current_price
                        fee = self.risk_manager.calculate_fees(sell_amount, 'sell')
                        net_amount = sell_amount - fee
                        
                        profit = net_amount - position['amount']
                        profit_rate = profit / position['amount']
                        
                        # 거래 결과 기록
                        trade_result = TradeResult(
                            id=result['uuid'],
                            timestamp=datetime.now(),
                            symbol=symbol,
                            side='sell',
                            amount=net_amount,
                            price=current_price,
                            fee=fee,
                            profit=profit,
                            profit_rate=profit_rate,
                            strategy=', '.join(signal['strategies'])
                        )
                        
                        # 포지션 제거 및 손익 업데이트
                        del self.risk_manager.positions[symbol]
                        self.risk_manager.update_pnl(trade_result)
                        
                        # DB 저장
                        self.db.save_trade(trade_result)
                        
                        profit_emoji = "📈" if profit > 0 else "📉"
                        logger.info(f"✅ 매도 완료: {symbol}, 손익: {profit:+.0f}원 ({profit_rate:+.2%})")
                        
                        # 텔레그램 알림
                        msg = f"{profit_emoji} 매도 완료\n🔸 {symbol}\n💵 {net_amount:,.0f}원\n💰 손익: {profit:+,.0f}원 ({profit_rate:+.2%})\n📊 일일손익: {self.risk_manager.daily_pnl:.2%}"
                        self.telegram.send_message_sync(msg)
        
        except Exception as e:
            logger.error(f"거래 실행 오류: {e}")
    
    def _claude_loop(self):
        """Claude 모니터링 루프"""
        while self.is_running:
            try:
                time.sleep(self.config.claude_interval * 60)  # 분 단위를 초로 변환
                
                if not self.is_running or self.is_paused:
                    continue
                
                # 전체 포트폴리오 분석
                total_balance = self.get_total_balance()
                market_data = self._get_portfolio_market_data()
                
                claude_analysis = self.claude.analyze_market_condition(
                    market_data, 
                    self.risk_manager.positions, 
                    self.config
                )
                
                # Claude 추천사항 처리
                if claude_analysis['confidence'] > 0.8:
                    if claude_analysis['recommendation'] == 'SELL' and len(self.risk_manager.positions) > 0:
                        logger.warning("Claude 강력 매도 권고 - 포지션 검토 필요")
                        msg = f"🤖 Claude 강력 권고\n📉 {claude_analysis['reasoning']}\n💡 {', '.join(claude_analysis['suggested_actions'])}"
                        self.telegram.send_message_sync(msg)
                    
                    elif claude_analysis['recommendation'] == 'BUY' and len(self.risk_manager.positions) < self.config.max_positions:
                        logger.info("Claude 매수 기회 제안")
                        msg = f"🤖 Claude 매수 기회\n📈 {claude_analysis['reasoning']}\n💡 {', '.join(claude_analysis['suggested_actions'])}"
                        self.telegram.send_message_sync(msg)
                
                # 위험 수준이 높을 때 긴급 개입
                if claude_analysis['risk_assessment'] > 0.8:
                    self.claude.emergency_intervention(
                        "고위험 상황 감지", 
                        "REDUCE_POSITIONS"
                    )
                    logger.critical("Claude 긴급 개입: 고위험 상황")
                    
                    msg = f"🚨 Claude 긴급 알림\n⚠️ 고위험 상황 감지\n📊 위험도: {claude_analysis['risk_assessment']:.1%}\n🛡️ 포지션 축소 권장"
                    self.telegram.send_message_sync(msg)
            
            except Exception as e:
                logger.error(f"Claude 모니터링 오류: {e}")
    
    def _telegram_loop(self):
        """텔레그램 정기 보고 루프"""
        while self.is_running:
            try:
                time.sleep(self.config.telegram_interval * 60)
                
                if not self.is_running or self.is_paused:
                    continue
                
                # 정기 보고서 생성 및 전송
                report = self._generate_status_report()
                self.telegram.send_message_sync(report)
                
                self.last_telegram_notification = datetime.now()
            
            except Exception as e:
                logger.error(f"텔레그램 알림 오류: {e}")
    
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
                market_data = self.strategy.market_collector.get_market_data(symbol)
                if market_data:
                    valid_data.append(market_data)
            
            if valid_data:
                total_data['avg_kimchi_premium'] = sum(d.get('kimchi_premium', 0) for d in valid_data) / len(valid_data)
                total_data['total_volume_ratio'] = sum(d.get('volume_ratio', 1) for d in valid_data) / len(valid_data)
            
            return total_data
            
        except Exception as e:
            logger.error(f"포트폴리오 데이터 수집 오류: {e}")
            return {}
    
    def _generate_status_report(self) -> str:
        """상태 보고서 생성"""
        try:
            total_balance = self.get_total_balance()
            daily_pnl_amount = total_balance - self.config.initial_amount
            
            # 오늘 거래 내역
            today_trades = self.db.get_daily_trades()
            win_trades = [t for t in today_trades if t.profit > 0]
            win_rate = len(win_trades) / len(today_trades) * 100 if today_trades else 0
            
            # 활성 포지션 정보
            position_info = []
            for symbol, pos in self.risk_manager.positions.items():
                current_price = pyupbit.get_current_price(symbol)
                if current_price:
                    unrealized_pnl = (current_price - pos['entry_price']) / pos['entry_price']
                    position_info.append(f"{symbol}: {unrealized_pnl:+.1%}")
            
            report = f"""📊 자동매매 현황 보고

💰 총 잔고: ₩{total_balance:,.0f}
📈 일일 손익: {self.risk_manager.daily_pnl:+.2%} (₩{daily_pnl_amount:+,.0f})
🎯 거래 횟수: {self.risk_manager.daily_trades}회
🏆 승률: {win_rate:.1f}%

📋 활성 포지션 ({len(self.risk_manager.positions)}개)
{chr(10).join(position_info) if position_info else '없음'}

⏰ 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
            
            # 상태에 따른 이모지 추가
            if self.risk_manager.daily_pnl > 0.02:
                report = "🎉 " + report
            elif self.risk_manager.daily_pnl < -0.02:
                report = "⚠️ " + report
            else:
                report = "✅ " + report
            
            return report
            
        except Exception as e:
            logger.error(f"보고서 생성 오류: {e}")
            return "❌ 보고서 생성 실패"
    
    def get_total_balance(self) -> float:
        """총 잔고 계산 (KRW + 코인 평가액)"""
        try:
            total = self.upbit.get_balance("KRW")  # KRW 잔고
            
            # 각 코인 평가액 추가
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
            logger.error(f"잔고 계산 오류: {e}")
            return self.config.initial_amount
    
    def emergency_sell_all(self) -> bool:
        """긴급 전량 매도"""
        try:
            logger.critical("🚨 긴급 전량 매도 시작")
            
            balances = self.upbit.get_balances()
            sell_results = []
            
            for balance in balances:
                if balance['currency'] != 'KRW' and float(balance['balance']) > 0:
                    symbol = f"KRW-{balance['currency']}"
                    
                    try:
                        result = self.upbit.sell_market_order(symbol, float(balance['balance']))
                        if result:
                            sell_results.append(f"{symbol}: 매도 완료")
                            logger.info(f"긴급 매도: {symbol}")
                        else:
                            sell_results.append(f"{symbol}: 매도 실패")
                    
                    except Exception as e:
                        sell_results.append(f"{symbol}: 오류 - {str(e)}")
                        logger.error(f"긴급 매도 오류 {symbol}: {e}")
            
            # 포지션 초기화
            self.risk_manager.positions.clear()
            
            # 결과 알림
            result_msg = "🚨 긴급 전량 매도 완료\n\n" + "\n".join(sell_results)
            self.telegram.send_message_sync(result_msg)
            
            logger.critical("🚨 긴급 전량 매도 완료")
            return True
            
        except Exception as e:
            logger.error(f"긴급 매도 실행 오류: {e}")
            return False
    
    def pause_trading(self):
        """거래 일시 정지"""
        self.is_paused = True
        logger.info("⏸️ 거래 일시 정지")
        self.telegram.send_message_sync("⏸️ 거래가 일시 정지되었습니다.")
    
    def resume_trading(self):
        """거래 재개"""
        self.is_paused = False
        logger.info("▶️ 거래 재개")
        self.telegram.send_message_sync("▶️ 거래가 재개되었습니다.")
    
    def get_status(self) -> Dict:
        """현재 상태 조회"""
        return {
            'is_running': self.is_running,
            'is_paused': self.is_paused,
            'daily_pnl': self.risk_manager.daily_pnl,
            'daily_trades': self.risk_manager.daily_trades,
            'total_balance': self.get_total_balance(),
            'positions': len(self.risk_manager.positions),
            'position_details': self.risk_manager.positions,
            'last_update': datetime.now().isoformat(),
            'config': asdict(self.config)
        }
    
    def update_config(self, new_config: Dict):
        """설정 업데이트"""
        try:
            for key, value in new_config.items():
                if hasattr(self.config, key):
                    setattr(self.config, key, value)
                    logger.info(f"설정 업데이트: {key} = {value}")
            
            return True
            
        except Exception as e:
            logger.error(f"설정 업데이트 오류: {e}")
            return False

# Flask 웹 API 서버
def create_web_server(bot: UpbitTradingBot) -> Flask:
    """웹 서버 생성"""
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'your-secret-key-here'
    socketio = SocketIO(app, cors_allowed_origins="*")
    
    @app.route('/')
    def index():
        """메인 대시보드"""
        return render_template_string(open('upbit_trading_ui.html', 'r', encoding='utf-8').read())
    
    @app.route('/api/status')
    def get_status():
        """상태 조회 API"""
        return jsonify(bot.get_status())
    
    @app.route('/api/start', methods=['POST'])
    def start_trading():
        """거래 시작 API"""
        success = bot.start()
        return jsonify({'success': success})
    
    @app.route('/api/stop', methods=['POST'])
    def stop_trading():
        """거래 중지 API"""
        success = bot.stop()
        return jsonify({'success': success})
    
    @app.route('/api/pause', methods=['POST'])
    def pause_trading():
        """거래 일시정지 API"""
        bot.pause_trading()
        return jsonify({'success': True})
    
    @app.route('/api/resume', methods=['POST'])
    def resume_trading():
        """거래 재개 API"""
        bot.resume_trading()
        return jsonify({'success': True})
    
    @app.route('/api/emergency_sell', methods=['POST'])
    def emergency_sell():
        """긴급 매도 API"""
        success = bot.emergency_sell_all()
        return jsonify({'success': success})
    
    @app.route('/api/config', methods=['POST'])
    def update_config():
        """설정 업데이트 API"""
        config_data = request.get_json()
        success = bot.update_config(config_data)
        return jsonify({'success': success})
    
    @app.route('/api/telegram/set', methods=['POST'])
    def set_telegram():
        """텔레그램 설정 API"""
        data = request.get_json()
        bot.telegram.set_credentials(data.get('token'), data.get('chat_id'))
        return jsonify({'success': True})
    
    @app.route('/api/trades/today')
    def get_today_trades():
        """오늘 거래 내역 API"""
        trades = bot.db.get_daily_trades()
        return jsonify([asdict(trade) for trade in trades])
    
    @app.route('/api/claude/manual_analysis', methods=['POST'])
    def manual_claude_analysis():
        """수동 Claude 분석 API"""
        try:
            market_data = bot._get_portfolio_market_data()
            analysis = bot.claude.analyze_market_condition(
                market_data, bot.risk_manager.positions, bot.config
            )
            return jsonify(analysis)
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    # WebSocket 이벤트
    @socketio.on('connect')
    def handle_connect():
        """클라이언트 연결"""
        emit('status_update', bot.get_status())
    
    @socketio.on('request_status')
    def handle_status_request():
        """상태 요청"""
        emit('status_update', bot.get_status())
    
    # 실시간 상태 업데이트 (별도 스레드에서)
    def status_broadcaster():
        """실시간 상태 브로드캐스트"""
        while True:
            try:
                if bot.is_running:
                    socketio.emit('status_update', bot.get_status())
                time.sleep(5)  # 5초마다 업데이트
            except Exception as e:
                logger.error(f"상태 브로드캐스트 오류: {e}")
                time.sleep(10)
    
    # 백그라운드 스레드 시작
    import threading
    broadcast_thread = threading.Thread(target=status_broadcaster, daemon=True)
    broadcast_thread.start()
    
    return app

def main():
    """메인 실행 함수"""
    print("=== 업비트 자동매매 시스템 v2.0 ===")
    
    # 설정 입력
    access_key = input("업비트 Access Key: ").strip()
    secret_key = input("업비트 Secret Key: ").strip()
    
    if not access_key or not secret_key:
        print("❌ API 키를 입력해주세요.")
        return
    
    # 기본 설정
    config = TradingConfig()
    
    # 설정 입력 (옵션)
    try:
        initial_amount = input(f"초기 투자 금액 (기본: {config.initial_amount:,.0f}원): ").strip()
        if initial_amount:
            config.initial_amount = float(initial_amount)
        
        max_profit = input(f"일일 최대 수익률 (기본: {config.max_daily_profit:.1%}): ").strip()
        if max_profit:
            config.max_daily_profit = float(max_profit) / 100
        
        max_loss = input(f"일일 최대 손실률 (기본: {config.max_daily_loss:.1%}): ").strip()
        if max_loss:
            config.max_daily_loss = float(max_loss) / 100
        
        telegram_token = input("텔레그램 봇 토큰 (선택사항): ").strip()
        telegram_chat_id = input("텔레그램 채팅 ID (선택사항): ").strip()
        
    except ValueError as e:
        print(f"❌ 입력 오류: {e}")
        return
    
    try:
        # 거래 봇 생성
        print("DEBUG: ACCESS_KEY=", access_key)
        print("DEBUG: SECRET_KEY=", secret_key)
        bot = UpbitTradingBot(access_key, secret_key, config)
        print("DEBUG: Upbit 객체=", bot.upbit)
        # 텔레그램 설정
        if telegram_token and telegram_chat_id:
            bot.telegram.set_credentials(telegram_token, telegram_chat_id)
            print("✅ 텔레그램 알림 설정 완료")
        
        # 웹 서버 생성
        app = create_web_server(bot)
        
        print(f"""
✅ 설정 완료!
🌐 웹 대시보드: http://localhost:5000
📱 텔레그램 알림: {'설정됨' if telegram_token else '미설정'}
💰 초기 금액: ₩{config.initial_amount:,.0f}
📊 일일 한도: 수익 {config.max_daily_profit:.1%}, 손실 {config.max_daily_loss:.1%}

거래를 시작하려면 웹 대시보드에서 '거래 시작' 버튼을 클릭하세요.
""")
        
        # Flask 서버 실행
        app.run(host='0.0.0.0', port=5000, debug=False)
        
    except KeyboardInterrupt:
        print("\n프로그램 종료 중...")
        if 'bot' in locals():
            bot.stop()
    
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        logger.error(f"메인 실행 오류: {e}")

if __name__ == "__main__":
    main()