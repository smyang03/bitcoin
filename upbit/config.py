#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
개선된 설정 관리 모듈
"""

from dataclasses import dataclass
from typing import List
from datetime import datetime

@dataclass
class TradingConfig:
    """거래 설정 클래스 - 개선됨"""
    initial_amount: float = 1000000      # 100만원으로 현실적 설정
    max_daily_profit: float = 0.5       # 일일 최대 수익률 (5%)
    max_daily_loss: float = 0.03         # 일일 최대 손실률 (3%) - 보수적
    max_positions: int = 5               # 최대 동시 포지션 - 리스크 분산
    max_position_size: float = 0.3       # 단일 포지션 최대 비중 (30%)
    stop_loss_rate: float = 0.02         # 손절매 비율 (2%) - 엄격하게
    
    # 새로운 설정들
    paper_trading: bool = True           # 모의거래 모드 (기본값)
    daily_trade_limit: bool = False       # 하루 1회 거래 제한
    compound_interest: bool = True       # 복리 계산 여부
    min_trade_amount: float = 50000      # 최소 거래 금액 5만원
    
    claude_interval: int = 30            # Claude 개입 주기 (분)
    telegram_interval: int = 30          # 텔레그램 알림 주기 (분)
    include_fees: bool = True            # 수수료 포함 여부
    upbit_fee_rate: float = 0.0005       # 업비트 수수료 (0.05%)
    target_coins: List[str] = None       # 거래 대상 코인
    
    def __post_init__(self):
        if self.target_coins is None:
            self.target_coins = [
            'KRW-BTC', 'KRW-ETH', 'KRW-XRP', 'KRW-ADA', 
            'KRW-DOT', 'KRW-LINK', 'KRW-AVAX', 'KRW-SOL',
            'KRW-ATOM', 'KRW-NEAR', 'KRW-SAND', 'KRW-MANA',
            'KRW-CRO', 'KRW-ALGO', 'KRW-FLOW'
]
    def update_from_dict(self, settings: dict):
        for key, value in settings.items():
            if hasattr(self, key):
                setattr(self, key, value)
                print(f"설정 업데이트: {key} = {value}")
    
    def to_dict(self) -> dict:
        """현재 설정을 딕셔너리로 반환"""
        from dataclasses import asdict
        return asdict(self)
    
    def save_to_file(self, filename: str = 'user_config.json'):
        """설정을 JSON 파일로 저장"""
        import json
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
    
    @classmethod
    def load_from_file(cls, filename: str = 'user_config.json'):
        """JSON 파일에서 설정 로드"""
        import json
        import os
        
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
                config = cls()
                config.update_from_dict(data)
                return config
        return cls()  # 파일이 없으면 기본값 반환

@dataclass
class TradeResult:
    """개선된 거래 결과 클래스"""
    id: str
    timestamp: datetime
    symbol: str
    side: str                            # 'buy' or 'sell'
    
    # 기본 거래 정보
    quantity: float                      # 매매 수량
    price: float                         # 매매 가격
    amount: float                        # 거래 금액 (수량 × 가격)
    fee: float                          # 수수료
    
    # 수익률 계산 관련 - 핵심 개선사항
    invested_amount: float = 0.0         # 실제 투자한 금액
    profit_amount: float = 0.0           # 절대 수익 금액
    profit_rate: float = 0.0             # 투자금액 대비 수익률 (정확한 계산)
    
    # 포트폴리오 추적
    portfolio_value_before: float = 0.0  # 거래 전 포트폴리오 가치
    portfolio_value_after: float = 0.0   # 거래 후 포트폴리오 가치
    
    # 메타데이터
    strategy: str = ''
    claude_action: bool = False          # 기존 호환성
    is_paper_trade: bool = False         # 모의거래 여부

class VirtualWallet:
    """가상 지갑 - 모의거래용"""
    
    def __init__(self, initial_krw: float):
        self.balances = {'KRW': initial_krw}
        self.initial_amount = initial_krw
        self.trade_history = []
        
    def get_balance(self, currency: str = 'KRW') -> float:
        """잔고 조회"""
        return self.balances.get(currency, 0.0)
    
    def get_balances(self) -> List[dict]:
        """전체 잔고 조회 (업비트 API 호환)"""
        balances = []
        for currency, balance in self.balances.items():
            balances.append({
                'currency': currency,
                'balance': str(balance),
                'locked': '0',
                'avg_buy_price': '0',
                'avg_buy_price_modified': False,
                'unit_currency': 'KRW' if currency != 'KRW' else currency
            })
        return balances
    
    def get_total_value(self) -> float:
        """총 자산 가치 계산"""
        try:
            import pyupbit
            
            total = self.balances.get('KRW', 0.0)
            
            for currency, amount in self.balances.items():
                if currency != 'KRW' and amount > 0:
                    symbol = f'KRW-{currency}'
                    try:
                        current_price = pyupbit.get_current_price(symbol)
                        if current_price:
                            total += amount * current_price
                    except:
                        # 가격 조회 실패시 무시
                        pass
            
            return total
            
        except Exception:
            return self.balances.get('KRW', 0.0)
    
    def buy_market_order(self, symbol: str, krw_amount: float) -> dict:
        """가상 매수 주문"""
        try:
            import pyupbit
            
            current_price = pyupbit.get_current_price(symbol)
            if not current_price:
                return None
            
            currency = symbol.split('-')[1]
            fee = krw_amount * 0.0005  # 0.05% 수수료
            net_amount = krw_amount - fee
            quantity = net_amount / current_price
            
            if self.balances.get('KRW', 0) >= krw_amount:
                self.balances['KRW'] = self.balances.get('KRW', 0) - krw_amount
                self.balances[currency] = self.balances.get(currency, 0) + quantity
                
                trade_record = {
                    'uuid': f"virtual_{datetime.now().timestamp()}",
                    'side': 'bid',
                    'ord_type': 'market',
                    'price': str(current_price),
                    'avg_price': str(current_price),
                    'state': 'done',
                    'market': symbol,
                    'volume': str(quantity),
                    'remaining_volume': '0',
                    'paid_fee': str(fee),
                    'locked': '0',
                    'executed_volume': str(quantity),
                    'trades_count': 1
                }
                
                self.trade_history.append(trade_record)
                return trade_record
            
            return None
            
        except Exception as e:
            print(f"가상 매수 오류: {e}")
            return None
    
    def sell_market_order(self, symbol: str, quantity: float) -> dict:
        """가상 매도 주문"""
        try:
            import pyupbit
            
            current_price = pyupbit.get_current_price(symbol)
            if not current_price:
                return None
            
            currency = symbol.split('-')[1]
            
            if self.balances.get(currency, 0) >= quantity:
                krw_amount = quantity * current_price
                fee = krw_amount * 0.0005
                net_amount = krw_amount - fee
                
                self.balances[currency] = self.balances.get(currency, 0) - quantity
                self.balances['KRW'] = self.balances.get('KRW', 0) + net_amount
                
                trade_record = {
                    'uuid': f"virtual_{datetime.now().timestamp()}",
                    'side': 'ask',
                    'ord_type': 'market',
                    'price': str(current_price),
                    'avg_price': str(current_price),
                    'state': 'done',
                    'market': symbol,
                    'volume': str(quantity),
                    'remaining_volume': '0',
                    'paid_fee': str(fee),
                    'locked': '0',
                    'executed_volume': str(quantity),
                    'trades_count': 1
                }
                
                self.trade_history.append(trade_record)
                return trade_record
            
            return None
            
        except Exception as e:
            print(f"가상 매도 오류: {e}")
            return None

# API 키 설정 (기존 유지)
class APIConfig:
    def __init__(self):
        # 실제 운영시에는 환경변수나 별도 파일에서 로드
        # 보안상 더미 키로 변경 - 실제 사용시 본인 키로 교체 필요
        self.UPBIT_ACCESS_KEY = "YOUR_UPBIT_ACCESS_KEY_HERE"
        self.UPBIT_SECRET_KEY = "YOUR_UPBIT_SECRET_KEY_HERE"
    
    def get_upbit_keys(self):
        return self.UPBIT_ACCESS_KEY, self.UPBIT_SECRET_KEY