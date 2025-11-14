#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
디버깅 및 오류 수정 모듈
"""

import traceback
import sys
from typing import Any, Dict, Optional

def safe_dict_access(data: Any, key: str, default: Any = None) -> Any:
    """안전한 딕셔너리 접근"""
    try:
        if isinstance(data, dict):
            return data.get(key, default)
        elif isinstance(data, str):
            print(f"WARNING: 문자열을 딕셔너리로 접근 시도: {data[:100]}...")
            return default
        else:
            print(f"WARNING: 예상하지 못한 데이터 타입: {type(data)}")
            return default
    except Exception as e:
        print(f"ERROR in safe_dict_access: {e}")
        return default

def debug_data_structure(data: Any, name: str = "data", max_depth: int = 2) -> str:
    """데이터 구조 디버깅"""
    try:
        if max_depth <= 0:
            return f"{name}: {type(data)} (깊이 제한)"
        
        if isinstance(data, dict):
            items = []
            for k, v in list(data.items())[:5]:  # 처음 5개만
                items.append(f"  {k}: {debug_data_structure(v, f'{name}[{k}]', max_depth-1)}")
            return f"{name}: dict({len(data)} items)\n" + "\n".join(items)
        
        elif isinstance(data, list):
            if len(data) > 0:
                first_item = debug_data_structure(data[0], f"{name}[0]", max_depth-1)
                return f"{name}: list({len(data)} items) - {first_item}"
            else:
                return f"{name}: list(empty)"
        
        elif isinstance(data, str):
            return f"{name}: str('{data[:50]}...' if len > 50 else '{data}')"
        
        else:
            return f"{name}: {type(data)}({str(data)[:50]}...)"
    
    except Exception as e:
        return f"{name}: ERROR - {str(e)}"

def safe_execute(func, *args, **kwargs):
    """안전한 함수 실행"""
    try:
        return func(*args, **kwargs)
    except Exception as e:
        print(f"ERROR in {func.__name__}: {str(e)}")
        print(f"Full traceback: {traceback.format_exc()}")
        return None

# 전역 디버그 모드
DEBUG_MODE = True

def debug_print(message: str, data: Any = None):
    """디버그 출력"""
    if DEBUG_MODE:
        print(f"DEBUG: {message}")
        if data is not None:
            print(f"DEBUG DATA: {debug_data_structure(data)}")

# trading_bot.py에서 사용할 패치 함수들
def patch_trading_bot():
    """TradingBot 클래스의 문제 있는 메서드들을 패치"""
    
    def safe_get_status(self) -> Dict:
        """안전한 상태 조회"""
        try:
            debug_print("get_status 시작")
            
            # 기본 상태
            status = {
                'is_running': False,
                'is_paused': False,
                'daily_pnl': 0.0,
                'daily_trades': 0,
                'total_balance': 0.0,
                'positions': 0,
                'position_details': {},
                'last_update': '',
                'config': {},
                'alert_summary': {}
            }
            
            # 안전하게 각 값 설정
            try:
                status['is_running'] = getattr(self, 'is_running', False)
                status['is_paused'] = getattr(self, 'is_paused', False)
            except Exception as e:
                debug_print(f"상태 플래그 오류: {e}")
            
            try:
                if hasattr(self, 'risk_manager'):
                    status['daily_pnl'] = getattr(self.risk_manager, 'daily_pnl', 0.0)
                    status['daily_trades'] = getattr(self.risk_manager, 'daily_trades', 0)
                    
                    if hasattr(self.risk_manager, 'positions'):
                        positions = self.risk_manager.positions
                        if isinstance(positions, dict):
                            status['positions'] = len(positions)
                            status['position_details'] = dict(positions)
                        else:
                            debug_print(f"포지션이 딕셔너리가 아님: {type(positions)}")
            except Exception as e:
                debug_print(f"리스크 매니저 오류: {e}")
            
            try:
                if hasattr(self, 'get_total_balance'):
                    status['total_balance'] = self.get_total_balance()
            except Exception as e:
                debug_print(f"잔고 조회 오류: {e}")
                if hasattr(self, 'config'):
                    status['total_balance'] = getattr(self.config, 'initial_amount', 1000000)
            
            try:
                from datetime import datetime
                status['last_update'] = datetime.now().isoformat()
            except Exception as e:
                debug_print(f"시간 설정 오류: {e}")
            
            try:
                if hasattr(self, 'config'):
                    from dataclasses import asdict
                    status['config'] = asdict(self.config)
            except Exception as e:
                debug_print(f"설정 변환 오류: {e}")
            
            try:
                if hasattr(self, 'alert_manager'):
                    status['alert_summary'] = self.alert_manager.get_alert_summary()
            except Exception as e:
                debug_print(f"알림 요약 오류: {e}")
            
            debug_print("get_status 완료", status)
            return status
            
        except Exception as e:
            debug_print(f"get_status 전체 오류: {e}")
            return {
                'is_running': False,
                'is_paused': False,
                'daily_pnl': 0.0,
                'daily_trades': 0,
                'total_balance': 1000000.0,
                'positions': 0,
                'position_details': {},
                'last_update': '',
                'config': {},
                'alert_summary': {}
            }
    
    return safe_get_status

# 사용법: main.py에서 import하여 사용
# from debug_fixes import patch_trading_bot, debug_print
# 
# # TradingBot 생성 후
# bot = TradingBot(config)
# bot.get_status = patch_trading_bot().__get__(bot, TradingBot)  # 메서드 바인딩