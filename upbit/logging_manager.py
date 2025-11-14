#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
개선된 로깅 관리 모듈
"""

import logging
import sqlite3
import json
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import asdict

from config import TradeResult


class DatabaseManager:
    """개선된 데이터베이스 관리 클래스"""
    
    def __init__(self, db_path: str = 'trading_bot.db'):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """데이터베이스 초기화 - 새 테이블 추가"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 기존 거래 기록 테이블 (하위 호환성)
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
        
        # 새로운 개선된 거래 기록 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades_v2 (
                id TEXT PRIMARY KEY,
                timestamp TEXT,
                symbol TEXT,
                side TEXT,
                quantity REAL,
                price REAL,
                amount REAL,
                fee REAL,
                invested_amount REAL,
                profit_amount REAL,
                profit_rate REAL,
                portfolio_value_before REAL,
                portfolio_value_after REAL,
                strategy TEXT,
                claude_action BOOLEAN,
                is_paper_trade BOOLEAN
            )
        ''')
        
        # 포트폴리오 스냅샷 테이블 (일일 자산 변화 추적)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS portfolio_snapshots (
                date TEXT PRIMARY KEY,
                total_value REAL,
                krw_balance REAL,
                coin_values TEXT,
                daily_return REAL,
                cumulative_return REAL,
                trades_count INTEGER,
                is_paper_trade BOOLEAN,
                initial_amount REAL
            )
        ''')
        
        # 거래 세션 테이블 (하루 1회 제한 관리)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trading_sessions (
                date TEXT,
                symbol TEXT,
                session_count INTEGER,
                last_trade_time TEXT,
                PRIMARY KEY (date, symbol)
            )
        ''')
        
        # 일일 성과 테이블 (기존)
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
        
        # Claude 분석 기록 테이블 (기존)
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
        
        # 시스템 로그 테이블 (기존)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS system_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                level TEXT,
                module TEXT,
                message TEXT,
                extra_data TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def save_trade(self, trade: TradeResult):
        """기존 거래 기록 저장 (하위 호환성)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO trades VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            trade.id, trade.timestamp.isoformat(), trade.symbol, trade.side,
            trade.amount, trade.price, trade.fee, 
            trade.profit_amount, trade.profit_rate,  # 개선된 필드 사용
            trade.strategy, trade.claude_action
        ))
        
        conn.commit()
        conn.close()
    
    def save_trade_v2(self, trade: TradeResult):
        """개선된 거래 기록 저장"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO trades_v2 VALUES 
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            trade.id, trade.timestamp.isoformat(), trade.symbol, trade.side,
            trade.quantity, trade.price, trade.amount, trade.fee,
            trade.invested_amount, trade.profit_amount, trade.profit_rate,
            trade.portfolio_value_before, trade.portfolio_value_after,
            trade.strategy, trade.claude_action, trade.is_paper_trade
        ))
        
        conn.commit()
        conn.close()
    
    def save_portfolio_snapshot(self, snapshot: Dict):
        """포트폴리오 스냅샷 저장"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO portfolio_snapshots VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            snapshot['date'], snapshot['total_value'], snapshot['krw_balance'],
            json.dumps(snapshot['coin_values']), snapshot['daily_return'],
            snapshot['cumulative_return'], snapshot['trades_count'],
            snapshot['is_paper_trade'], snapshot.get('initial_amount', 0)
        ))
        
        conn.commit()
        conn.close()
    
    def can_trade_today(self, symbol: str) -> bool:
        """오늘 거래 가능 여부 확인"""
        today = datetime.now().strftime('%Y-%m-%d')
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT session_count FROM trading_sessions 
            WHERE date = ? AND symbol = ?
        ''', (today, symbol))
        
        result = cursor.fetchone()
        conn.close()
        
        # 하루 1회 제한
        return result is None or result[0] < 1
    
    def record_trade_session(self, symbol: str):
        """거래 세션 기록"""
        today = datetime.now().strftime('%Y-%m-%d')
        now = datetime.now().isoformat()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO trading_sessions 
            (date, symbol, session_count, last_trade_time)
            VALUES (?, ?, 1, ?)
        ''', (today, symbol, now))
        
        conn.commit()
        conn.close()
    
    def get_portfolio_history(self, days: int = 30) -> pd.DataFrame:
        """포트폴리오 이력 조회"""
        conn = sqlite3.connect(self.db_path)
        
        try:
            df = pd.read_sql_query('''
                SELECT * FROM portfolio_snapshots 
                WHERE date >= date('now', '-{} days')
                ORDER BY date
            '''.format(days), conn)
            
            return df
        except Exception as e:
            print(f"포트폴리오 이력 조회 오류: {e}")
            return pd.DataFrame()
        finally:
            conn.close()
    
    def save_claude_analysis(self, analysis: Dict):
        """Claude 분석 기록 저장 (기존 유지)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO claude_analysis (timestamp, market_data, recommendation, confidence, reasoning, executed)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            datetime.now().isoformat(),
            json.dumps(analysis.get('market_data', {})),
            analysis.get('recommendation', ''),
            analysis.get('confidence', 0.0),
            analysis.get('reasoning', ''),
            analysis.get('executed', False)
        ))
        
        conn.commit()
        conn.close()
    
    def save_system_log(self, level: str, module: str, message: str, extra_data: Dict = None):
        """시스템 로그 저장 (기존 유지)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO system_logs (timestamp, level, module, message, extra_data)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            datetime.now().isoformat(),
            level,
            module,
            message,
            json.dumps(extra_data) if extra_data else None
        ))
        
        conn.commit()
        conn.close()
    
    def get_daily_trades(self, date: str = None) -> List[TradeResult]:
        """일일 거래 기록 조회 (개선된 버전 우선 사용)"""
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 먼저 v2 테이블에서 조회
        cursor.execute('''
            SELECT * FROM trades_v2 
            WHERE date(timestamp) = ? 
            ORDER BY timestamp DESC
        ''', (date,))
        
        rows = cursor.fetchall()
        
        trades = []
        for row in rows:
            trade = TradeResult(
                id=row[0],
                timestamp=datetime.fromisoformat(row[1]),
                symbol=row[2],
                side=row[3],
                quantity=row[4],
                price=row[5],
                amount=row[6],
                fee=row[7],
                invested_amount=row[8],
                profit_amount=row[9],
                profit_rate=row[10],
                portfolio_value_before=row[11],
                portfolio_value_after=row[12],
                strategy=row[13],
                claude_action=bool(row[14]),
                is_paper_trade=bool(row[15])
            )
            trades.append(trade)
        
        # v2에 데이터가 없으면 기존 테이블에서 조회
        if not trades:
            cursor.execute('''
                SELECT * FROM trades 
                WHERE date(timestamp) = ? 
                ORDER BY timestamp DESC
            ''', (date,))
            
            rows = cursor.fetchall()
            
            for row in rows:
                trade = TradeResult(
                    id=row[0],
                    timestamp=datetime.fromisoformat(row[1]),
                    symbol=row[2],
                    side=row[3],
                    quantity=0,  # 기존 데이터에서는 수량 정보 없음
                    price=row[5],
                    amount=row[4],
                    fee=row[6],
                    invested_amount=row[4],  # amount를 invested_amount로 간주
                    profit_amount=row[7],
                    profit_rate=row[8],
                    strategy=row[9],
                    claude_action=bool(row[10])
                )
                trades.append(trade)
        
        conn.close()
        return trades
    
    def get_trading_performance(self, days: int = 7) -> Dict:
        """거래 성과 분석 (기존 호환성 유지)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # v2 테이블 우선 조회
        cursor.execute('''
            SELECT 
                COUNT(*) as total_trades,
                SUM(CASE WHEN side = 'sell' THEN profit_amount ELSE 0 END) as total_profit,
                AVG(CASE WHEN side = 'sell' AND profit_rate != 0 THEN profit_rate ELSE NULL END) as avg_profit_rate,
                COUNT(CASE WHEN side = 'sell' AND profit_amount > 0 THEN 1 END) as win_trades,
                COUNT(CASE WHEN side = 'sell' THEN 1 END) as sell_trades,
                MAX(profit_amount) as max_win,
                MIN(profit_amount) as max_loss,
                SUM(invested_amount) as total_invested
            FROM trades_v2 
            WHERE timestamp >= datetime('now', '-{} days')
        '''.format(days))
        
        row = cursor.fetchone()
        
        if row and row[0] > 0:
            sell_trades = row[4] or 1
            total_invested = row[7] or 1
            
            performance = {
                'total_trades': row[0],
                'total_profit': row[1] or 0,
                'avg_profit_rate': row[2] or 0,
                'win_rate': (row[3] / sell_trades) * 100 if sell_trades > 0 else 0,
                'max_win': row[5] or 0,
                'max_loss': row[6] or 0,
                'profit_factor': abs(row[1] / row[6]) if row[6] and row[6] < 0 else 0,
                'total_invested': total_invested,
                'roi': (row[1] / total_invested) * 100 if total_invested > 0 else 0
            }
        else:
            # v2에 데이터가 없으면 기존 테이블에서 조회
            cursor.execute('''
                SELECT 
                    COUNT(*) as total_trades,
                    SUM(profit) as total_profit,
                    AVG(profit_rate) as avg_profit_rate,
                    COUNT(CASE WHEN profit > 0 THEN 1 END) as win_trades,
                    MAX(profit) as max_win,
                    MIN(profit) as max_loss
                FROM trades 
                WHERE timestamp >= datetime('now', '-{} days')
            '''.format(days))
            
            row = cursor.fetchone()
            
            if row and row[0] > 0:
                performance = {
                    'total_trades': row[0],
                    'total_profit': row[1] or 0,
                    'avg_profit_rate': row[2] or 0,
                    'win_rate': (row[3] / row[0]) * 100 if row[0] > 0 else 0,
                    'max_win': row[4] or 0,
                    'max_loss': row[5] or 0,
                    'profit_factor': abs(row[1] / row[5]) if row[5] and row[5] < 0 else 0
                }
            else:
                performance = {}
        
        conn.close()
        return performance


class TradingLogger:
    """거래 전용 로거 (기존 유지 + 개선사항 추가)"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.logger = self._setup_logger()
    
    def _setup_logger(self):
        """로거 설정 (기존 유지)"""
        logger = logging.getLogger('trading_bot')
        logger.setLevel(logging.INFO)
        
        # 중복 핸들러 방지
        if not logger.handlers:
            # 파일 핸들러
            file_handler = logging.FileHandler('trading_bot.log', encoding='utf-8')
            file_handler.setLevel(logging.INFO)
            
            # 콘솔 핸들러
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            
            # 포맷터
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            file_handler.setFormatter(formatter)
            console_handler.setFormatter(formatter)
            
            logger.addHandler(file_handler)
            logger.addHandler(console_handler)
        
        return logger
    
    def log_trade(self, trade: TradeResult, message: str = ""):
        """개선된 거래 로깅"""
        # 두 버전 모두 저장
        self.db_manager.save_trade(trade)  # 기존 호환성
        self.db_manager.save_trade_v2(trade)  # 개선된 버전
        
        trade_type = "매수" if trade.side == 'buy' else "매도"
        mode = "모의" if trade.is_paper_trade else "실제"
        
        if trade.side == 'buy':
            log_message = f"[{mode}] {trade_type} 완료: {trade.symbol}, " \
                         f"투자금액: ₩{trade.invested_amount:,.0f}, " \
                         f"수량: {trade.quantity:.8f}"
        else:
            log_message = f"[{mode}] {trade_type} 완료: {trade.symbol}, " \
                         f"수량: {trade.quantity:.8f}, " \
                         f"수익: ₩{trade.profit_amount:+,.0f} ({trade.profit_rate:+.2%})"
        
        if message:
            log_message += f" - {message}"
        
        self.logger.info(log_message)
        
        # DB에도 로그 저장
        self.db_manager.save_system_log(
            'INFO', 'trading', log_message, 
            {'trade_data': asdict(trade)}
        )
    
    def log_error(self, module: str, error: Exception, context: Dict = None):
        """에러 로깅 (기존 유지)"""
        error_message = f"{module} 오류: {str(error)}"
        self.logger.error(error_message)
        
        self.db_manager.save_system_log(
            'ERROR', module, error_message,
            {'error_type': type(error).__name__, 'context': context}
        )
    
    def log_warning(self, module: str, message: str, context: Dict = None):
        """경고 로깅 (기존 유지)"""
        self.logger.warning(f"{module}: {message}")
        self.db_manager.save_system_log('WARNING', module, message, context)
    
    def log_info(self, module: str, message: str, context: Dict = None):
        """정보 로깅 (기존 유지)"""
        self.logger.info(f"{module}: {message}")
        self.db_manager.save_system_log('INFO', module, message, context)
    
    def log_critical(self, module: str, message: str, context: Dict = None):
        """치명적 로깅 (기존 유지)"""
        self.logger.critical(f"{module}: {message}")
        self.db_manager.save_system_log('CRITICAL', module, message, context)
    
    def log_claude_analysis(self, analysis: Dict):
        """Claude 분석 로깅 (기존 유지)"""
        self.db_manager.save_claude_analysis(analysis)
        
        message = f"Claude 분석: {analysis.get('recommendation', 'UNKNOWN')} " \
                 f"(신뢰도: {analysis.get('confidence', 0):.1%}) - " \
                 f"{analysis.get('reasoning', '')}"
        
        self.logger.info(message)
    
    def get_recent_logs(self, limit: int = 100) -> List[Dict]:
        """최근 로그 조회 (기존 유지)"""
        conn = sqlite3.connect(self.db_manager.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT timestamp, level, module, message, extra_data
            FROM system_logs 
            ORDER BY timestamp DESC 
            LIMIT ?
        ''', (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        logs = []
        for row in rows:
            logs.append({
                'timestamp': row[0],
                'level': row[1],
                'module': row[2],
                'message': row[3],
                'extra_data': json.loads(row[4]) if row[4] else None
            })
        
        return logs


class PerformanceTracker:
    """개선된 성과 추적 클래스"""
    
    def __init__(self, db_manager: DatabaseManager, logger: TradingLogger):
        self.db_manager = db_manager
        self.logger = logger
        # matplotlib 한글 폰트 설정
        plt.rcParams['font.family'] = ['DejaVu Sans', 'Malgun Gothic', 'AppleGothic']
        plt.rcParams['axes.unicode_minus'] = False
    
    def calculate_daily_performance(self, date: str = None) -> Dict:
        """일일 성과 계산 (기존 유지 + 개선)"""
        trades = self.db_manager.get_daily_trades(date)
        
        if not trades:
            return {}
        
        # 매도 거래만 수익 계산
        sell_trades = [trade for trade in trades if trade.side == 'sell']
        
        if not sell_trades:
            return {
                'date': date or datetime.now().strftime('%Y-%m-%d'),
                'total_trades': len(trades),
                'total_profit': 0,
                'total_profit_rate': 0,
                'win_rate': 0,
                'avg_profit_per_trade': 0,
                'max_win': 0,
                'max_loss': 0,
                'total_invested': sum(t.invested_amount for t in trades if t.side == 'buy')
            }
        
        # 정확한 수익 계산
        total_profit = sum(trade.profit_amount for trade in sell_trades)
        total_invested = sum(trade.invested_amount for trade in sell_trades)
        
        win_trades = [trade for trade in sell_trades if trade.profit_amount > 0]
        
        performance = {
            'date': date or datetime.now().strftime('%Y-%m-%d'),
            'total_trades': len(sell_trades),
            'total_profit': total_profit,
            'total_profit_rate': (total_profit / total_invested) * 100 if total_invested > 0 else 0,
            'win_rate': (len(win_trades) / len(sell_trades)) * 100 if sell_trades else 0,
            'avg_profit_per_trade': total_profit / len(sell_trades) if sell_trades else 0,
            'max_win': max([t.profit_amount for t in sell_trades], default=0),
            'max_loss': min([t.profit_amount for t in sell_trades], default=0),
            'total_invested': total_invested,
            'buy_trades': len([t for t in trades if t.side == 'buy']),
            'roi': (total_profit / total_invested) * 100 if total_invested > 0 else 0
        }
        
        return performance
    
    def save_daily_performance(self, performance: Dict):
        """일일 성과 저장 (기존 유지)"""
        conn = sqlite3.connect(self.db_manager.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO daily_performance 
            (date, total_profit, total_profit_rate, total_trades, win_rate, max_drawdown)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            performance['date'],
            performance['total_profit'],
            performance['total_profit_rate'],
            performance['total_trades'],
            performance['win_rate'],
            performance.get('max_drawdown', 0)
        ))
        
        conn.commit()
        conn.close()
        
        self.logger.log_info('performance', 
                           f"일일 성과 저장: 수익률 {performance['total_profit_rate']:.2%}, "
                           f"승률 {performance['win_rate']:.1f}%")
    
    def create_portfolio_chart(self, days: int = 30) -> str:
        """포트폴리오 차트 생성"""
        try:
            df = self.db_manager.get_portfolio_history(days)
            
            if df.empty:
                return "차트 생성 실패: 데이터가 없습니다."
            
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
            
            # 날짜 변환
            df['date'] = pd.to_datetime(df['date'])
            
            # 포트폴리오 가치 변화
            ax1.plot(df['date'], df['total_value'], 'b-', linewidth=2, label='포트폴리오 가치')
            if not df.empty:
                initial_value = df['initial_amount'].iloc[0] if 'initial_amount' in df.columns else df['total_value'].iloc[0]
                ax1.axhline(y=initial_value, color='r', linestyle='--', alpha=0.7, label='초기값')
            ax1.set_ylabel('포트폴리오 가치 (원)')
            ax1.set_title(f'포트폴리오 가치 변화 ({days}일)')
            ax1.legend()
            ax1.grid(True, alpha=0.3)
            ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'₩{x:,.0f}'))
            
            # 수익률 변화
            ax2.plot(df['date'], df['cumulative_return'], 'g-', linewidth=2, label='누적 수익률')
            ax2.axhline(y=0, color='k', linestyle='-', alpha=0.3)
            ax2.set_ylabel('수익률 (%)')
            ax2.set_xlabel('날짜')
            ax2.set_title('누적 수익률 변화')
            ax2.legend()
            ax2.grid(True, alpha=0.3)
            
            # x축 날짜 포맷
            for ax in [ax1, ax2]:
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
                ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, days//10)))
                plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
            
            plt.tight_layout()
            
            # 파일로 저장
            filename = f'portfolio_chart_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png'
            plt.savefig(filename, dpi=300, bbox_inches='tight')
            plt.close()
            
            return filename
            
        except Exception as e:
            self.logger.log_error('performance_tracker', e)
            return f"차트 생성 실패: {str(e)}"
    
    def generate_performance_report(self, days: int = 7) -> str:
        """개선된 성과 보고서 생성"""
        try:
            # 거래 성과 데이터
            performance_data = self.db_manager.get_trading_performance(days)
            
            # 포트폴리오 이력
            portfolio_df = self.db_manager.get_portfolio_history(days)
            
            if not performance_data and portfolio_df.empty:
                return "분석할 거래 데이터가 없습니다."
            
            # 차트 생성 시도
            chart_info = ""
            try:
                chart_file = self.create_portfolio_chart(days)
                if not chart_file.startswith("차트 생성 실패"):
                    chart_info = f"📈 차트 파일: {chart_file}"
                else:
                    chart_info = chart_file
            except:
                chart_info = "차트 생성 실패"
            
            # 포트폴리오 성과 계산
            portfolio_info = ""
            if not portfolio_df.empty:
                current_value = portfolio_df['total_value'].iloc[-1] if len(portfolio_df) > 0 else 0
                initial_value = portfolio_df['initial_amount'].iloc[0] if 'initial_amount' in portfolio_df.columns else portfolio_df['total_value'].iloc[0]
                total_return = ((current_value / initial_value) - 1) * 100 if initial_value > 0 else 0
                
                portfolio_info = f"""
🎯 포트폴리오 현황:
• 초기 자산: ₩{initial_value:,.0f}
• 현재 자산: ₩{current_value:,.0f}  
• 총 수익률: {total_return:+.2f}%
• 수익 금액: ₩{current_value - initial_value:+,.0f}
"""
            
            # 거래 성과 정보
            trading_info = ""
            if performance_data:
                trading_info = f"""
💰 거래 성과 ({days}일간):
• 총 거래 횟수: {performance_data.get('total_trades', 0)}회
• 실현 손익: ₩{performance_data.get('total_profit', 0):+,.0f}
• 평균 수익률: {performance_data.get('avg_profit_rate', 0):+.2%}
• 승률: {performance_data.get('win_rate', 0):.1f}%
• 최대 수익: ₩{performance_data.get('max_win', 0):,.0f}
• 최대 손실: ₩{performance_data.get('max_loss', 0):,.0f}
• 손익비: {performance_data.get('profit_factor', 0):.2f}
"""
                if 'roi' in performance_data:
                    trading_info += f"• 투자 대비 수익률 (ROI): {performance_data['roi']:+.2f}%\n"
            
            report = f"""
📊 거래 성과 보고서
{portfolio_info}
{trading_info}

{chart_info}

⏰ 생성 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
            
            return report.strip()
            
        except Exception as e:
            self.logger.log_error('performance_tracker', e)
            return f"보고서 생성 실패: {str(e)}"
    
    def update_portfolio_snapshot(self, total_value: float, krw_balance: float, 
                                coin_values: dict, initial_amount: float, 
                                is_paper_trade: bool = False):
        """포트폴리오 스냅샷 업데이트"""
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            
            # 수익률 계산
            cumulative_return = ((total_value / initial_amount) - 1) * 100 if initial_amount > 0 else 0
            
            # 전일 대비 수익률 계산
            yesterday_df = self.db_manager.get_portfolio_history(2)
            daily_return = 0.0
            if len(yesterday_df) > 1:
                last_value = yesterday_df['total_value'].iloc[-2]
                daily_return = ((total_value / last_value) - 1) * 100 if last_value > 0 else 0
            
            # 오늘 거래 수 계산
            today_trades = len(self.db_manager.get_daily_trades(today))
            
            snapshot = {
                'date': today,
                'total_value': total_value,
                'krw_balance': krw_balance,
                'coin_values': coin_values,
                'daily_return': daily_return,
                'cumulative_return': cumulative_return,
                'trades_count': today_trades,
                'is_paper_trade': is_paper_trade,
                'initial_amount': initial_amount
            }
            
            self.db_manager.save_portfolio_snapshot(snapshot)
            
            self.logger.log_info('performance_tracker', 
                               f"포트폴리오 스냅샷 업데이트: ₩{total_value:,.0f} ({cumulative_return:+.2f}%)")
            
        except Exception as e:
            self.logger.log_error('performance_tracker', e)