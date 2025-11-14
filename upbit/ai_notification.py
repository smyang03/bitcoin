#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI 분석 및 알림 모듈
"""

import requests
import asyncio
import queue
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from config import TradingConfig
from logging_manager import TradingLogger


class ClaudeInterface:
    """Claude AI 인터페이스"""
    
    def __init__(self, logger: TradingLogger):
        self.logger = logger
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
            
            self.logger.log_claude_analysis(analysis)
            
            return analysis
            
        except Exception as e:
            self.logger.log_error('claude_interface', e)
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
        self.logger.log_critical('claude_interface', f"긴급 개입: {reason} -> {action}")
        
        return intervention


class TelegramNotifier:
    """텔레그램 알림 클래스"""
    
    def __init__(self, logger: TradingLogger, bot_token: str = None, chat_id: str = None):
        self.logger = logger
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}" if bot_token else None
        self.last_notification_time = {}
        self.notification_cooldown = 300  # 5분 쿨다운
    
    def set_credentials(self, bot_token: str, chat_id: str):
        """텔레그램 인증 정보 설정"""
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        self.logger.log_info('telegram', "텔레그램 인증 정보 설정 완료")
    
    async def send_message(self, message: str, parse_mode: str = 'Markdown') -> bool:
        """텔레그램 메시지 전송"""
        if not self.base_url or not self.chat_id:
            self.logger.log_warning('telegram', "텔레그램 설정이 없습니다.")
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
                self.logger.log_info('telegram', "메시지 전송 완료")
                return True
            else:
                self.logger.log_error('telegram', 
                                    Exception(f"메시지 전송 실패: {response.status_code}"))
                return False
                
        except Exception as e:
            self.logger.log_error('telegram', e)
            return False
    
    def send_message_sync(self, message: str) -> bool:
        """동기식 메시지 전송"""
        return asyncio.run(self.send_message(message))
    
    def send_trade_notification(self, trade_result, additional_info: str = "") -> bool:
        """거래 알림 전송"""
        # 쿨다운 체크
        if not self._check_cooldown('trade'):
            return False
        
        try:
            # TradeResult 객체 검증
            if not hasattr(trade_result, 'side') or not hasattr(trade_result, 'symbol'):
                self.logger.log_warning('telegram', "잘못된 trade_result 객체")
                return False
            
            side_emoji = "💰" if trade_result.side == 'buy' else "📈" if getattr(trade_result, 'profit', 0) > 0 else "📉"
            side_text = "매수" if trade_result.side == 'buy' else "매도"
            
            message = f"{side_emoji} {side_text} 완료\n"
            message += f"🔸 {trade_result.symbol}\n"
            message += f"💵 {getattr(trade_result, 'amount', 0):,.0f}원\n"
            
            if trade_result.side == 'sell' and hasattr(trade_result, 'profit'):
                profit = getattr(trade_result, 'profit', 0)
                profit_rate = getattr(trade_result, 'profit_rate', 0)
                message += f"💰 손익: {profit:+,.0f}원 ({profit_rate:+.2%})\n"
            
            if hasattr(trade_result, 'strategy'):
                message += f"📊 전략: {trade_result.strategy}\n"
            
            if additional_info:
                message += f"ℹ️ {additional_info}\n"
            
            message += f"⏰ {getattr(trade_result, 'timestamp', datetime.now()).strftime('%H:%M:%S')}"
            
            return self.send_message_sync(message)
            
        except Exception as e:
            self.logger.log_error('telegram', e)
            return False
    
    def send_claude_notification(self, analysis: Dict) -> bool:
        """Claude 분석 알림 전송"""
        if not self._check_cooldown('claude'):
            return False
        
        confidence_emoji = "🔥" if analysis['confidence'] > 0.8 else "⚖️" if analysis['confidence'] > 0.6 else "🤔"
        recommendation_emoji = "📈" if analysis['recommendation'] == 'BUY' else "📉" if analysis['recommendation'] == 'SELL' else "⏸️"
        
        message = f"🤖 Claude 분석 {confidence_emoji}\n"
        message += f"{recommendation_emoji} 추천: {analysis['recommendation']}\n"
        message += f"📊 신뢰도: {analysis['confidence']:.1%}\n"
        message += f"💭 {analysis['reasoning']}\n"
        
        if analysis['suggested_actions']:
            message += f"💡 제안사항:\n"
            for action in analysis['suggested_actions'][:3]:  # 최대 3개
                message += f"  • {action}\n"
        
        message += f"⏰ {datetime.now().strftime('%H:%M:%S')}"
        
        return self.send_message_sync(message)
    
    def send_status_report(self, report: str) -> bool:
        """상태 보고서 전송"""
        if not self._check_cooldown('status', cooldown_time=1800):  # 30분 쿨다운
            return False
        
        return self.send_message_sync(report)
    
    def send_emergency_alert(self, message: str) -> bool:
        """긴급 알림 전송 (쿨다운 무시)"""
        emergency_message = f"🚨 긴급 알림 🚨\n{message}\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        return self.send_message_sync(emergency_message)
    
    def _check_cooldown(self, notification_type: str, cooldown_time: int = None) -> bool:
        """알림 쿨다운 체크"""
        if cooldown_time is None:
            cooldown_time = self.notification_cooldown
        
        current_time = datetime.now()
        last_time = self.last_notification_time.get(notification_type)
        
        if last_time is None or (current_time - last_time).total_seconds() >= cooldown_time:
            self.last_notification_time[notification_type] = current_time
            return True
        
        return False


class AlertManager:
    """종합 알림 관리 클래스"""
    
    def __init__(self, telegram: TelegramNotifier, logger: TradingLogger):
        self.telegram = telegram
        self.logger = logger
        self.alert_history = []
        self.max_alerts_per_hour = 20
    
    def send_trade_alert(self, trade_result, context: Dict = None):
        """거래 알림"""
        try:
            # TradeResult 객체인지 확인하고 처리
            if hasattr(trade_result, 'symbol'):
                additional_info = ""
                if context:
                    if 'daily_pnl' in context:
                        additional_info += f"일일손익: {context['daily_pnl']:.2%}"
                    if 'positions_count' in context:
                        additional_info += f", 포지션: {context['positions_count']}개"
                    if 'message' in context:
                        additional_info = context['message']
                
                success = self.telegram.send_trade_notification(trade_result, additional_info)
                
                if success:
                    self._add_alert_history('trade', f"거래 알림 전송: {trade_result.symbol}")
            else:
                self.logger.log_warning('alert_manager', "잘못된 trade_result 객체")
            
        except Exception as e:
            self.logger.log_error('alert_manager', e, {'type': 'trade_alert'})
    
    def send_claude_alert(self, analysis: Dict):
        """Claude 분석 알림"""
        try:
            if self._should_send_alert('claude'):
                success = self.telegram.send_claude_notification(analysis)
                
                if success:
                    self._add_alert_history('claude', f"Claude 분석: {analysis['recommendation']}")
                    
        except Exception as e:
            self.logger.log_error('alert_manager', e, {'type': 'claude_alert'})
    
    def send_emergency_alert(self, message: str, alert_type: str = 'emergency'):
        """긴급 알림"""
        try:
            success = self.telegram.send_emergency_alert(message)
            
            if success:
                self._add_alert_history(alert_type, message)
                self.logger.log_critical('alert_manager', f"긴급 알림 전송: {message}")
                
        except Exception as e:
            self.logger.log_error('alert_manager', e, {'type': 'emergency_alert'})
    
    def send_daily_report(self, report: str):
        """일일 보고서 알림"""
        try:
            success = self.telegram.send_status_report(report)
            
            if success:
                self._add_alert_history('daily_report', "일일 보고서 전송")
                
        except Exception as e:
            self.logger.log_error('alert_manager', e, {'type': 'daily_report'})
    
    def _should_send_alert(self, alert_type: str) -> bool:
        """알림 전송 여부 판단"""
        # 시간당 알림 제한 확인
        current_time = datetime.now()
        recent_alerts = [
            alert for alert in self.alert_history
            if (current_time - alert['timestamp']).total_seconds() < 3600
        ]
        
        if len(recent_alerts) >= self.max_alerts_per_hour:
            self.logger.log_warning('alert_manager', 
                                   f"시간당 알림 제한 도달: {len(recent_alerts)}개")
            return False
        
        return True
    
    def _add_alert_history(self, alert_type: str, message: str):
        """알림 기록 추가"""
        self.alert_history.append({
            'type': alert_type,
            'message': message,
            'timestamp': datetime.now()
        })
        
        # 오래된 기록 정리 (24시간 이상)
        cutoff_time = datetime.now() - timedelta(days=1)
        self.alert_history = [
            alert for alert in self.alert_history
            if alert['timestamp'] > cutoff_time
        ]
    
    def get_alert_summary(self) -> Dict:
        """알림 요약 정보"""
        current_time = datetime.now()
        
        # 최근 1시간 알림
        recent_alerts = [
            alert for alert in self.alert_history
            if (current_time - alert['timestamp']).total_seconds() < 3600
        ]
        
        # 오늘 알림
        today_alerts = [
            alert for alert in self.alert_history
            if alert['timestamp'].date() == current_time.date()
        ]
        
        alert_counts = {}
        for alert in today_alerts:
            alert_type = alert['type']
            alert_counts[alert_type] = alert_counts.get(alert_type, 0) + 1
        
        return {
            'recent_count': len(recent_alerts),
            'today_count': len(today_alerts),
            'remaining_hourly': max(0, self.max_alerts_per_hour - len(recent_alerts)),
            'type_breakdown': alert_counts,
            'last_alert': self.alert_history[-1] if self.alert_history else None
        }