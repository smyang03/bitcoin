#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
거래 로그 및 성과 확인 스크립트
"""

import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import os

def check_log_files():
    """로그 파일 존재 확인"""
    files = ['trading_bot.log', 'trading_bot.db', 'improved_trading.db']
    print("=== 로그 파일 확인 ===")
    
    for file in files:
        if os.path.exists(file):
            size = os.path.getsize(file)
            print(f"✓ {file} ({size} bytes)")
        else:
            print(f"✗ {file} (없음)")
    print()

def show_recent_trades(db_path='trading_bot.db', days=7):
    """최근 거래 내역 표시"""
    try:
        conn = sqlite3.connect(db_path)
        
        # trades_v2 테이블 먼저 확인
        # 테이블 존재 확인 후 적절한 쿼리 사용
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'trade%'")
        tables = [row[0] for row in cursor.fetchall()]

        if 'trades_v2' in tables:
            query = """
            SELECT timestamp, symbol, side, amount, price, 
                COALESCE(profit_amount, 0) as profit_amount,
                COALESCE(profit_rate, 0) as profit_rate, 
                strategy
            FROM trades_v2 
            WHERE timestamp >= datetime('now', '-{} days')
            ORDER BY timestamp DESC
            """.format(days)
        elif 'trades' in tables:
            query = """
            SELECT timestamp, symbol, side, amount, price,
                COALESCE(profit, 0) as profit_amount,
                COALESCE(profit_rate, 0) as profit_rate,
                strategy  
            FROM trades
            WHERE timestamp >= datetime('now', '-{} days')
            ORDER BY timestamp DESC
            """.format(days)
        else:
            print("거래 테이블을 찾을 수 없습니다.")
            return
                
        df = pd.read_sql_query(query, conn)
        
        if df.empty:
            # 기존 trades 테이블 확인
            query = """
            SELECT timestamp, symbol, side, amount, price, profit, profit_rate, strategy
            FROM trades 
            WHERE timestamp >= datetime('now', '-{} days')
            ORDER BY timestamp DESC
            """.format(days)
            df = pd.read_sql_query(query, conn)
        
        if not df.empty:
            print(f"=== 최근 {days}일 거래 내역 ===")
            print(df.to_string(index=False))
        else:
            print(f"최근 {days}일간 거래 내역이 없습니다.")
        
        conn.close()
        
    except Exception as e:
        print(f"거래 내역 조회 오류: {e}")

def show_portfolio_changes(db_path='trading_bot.db', days=7):
    """포트폴리오 변화 표시"""
    try:
        conn = sqlite3.connect(db_path)
        
        query = """
        SELECT date, total_value, daily_return, cumulative_return, trades_count
        FROM portfolio_snapshots 
        WHERE date >= date('now', '-{} days')
        ORDER BY date DESC
        """.format(days)
        
        df = pd.read_sql_query(query, conn)
        
        if not df.empty:
            print(f"\n=== 최근 {days}일 포트폴리오 변화 ===")
            print(df.to_string(index=False))
        else:
            print("포트폴리오 스냅샷 데이터가 없습니다.")
        
        conn.close()
        
    except Exception as e:
        print(f"포트폴리오 조회 오류: {e}")

def show_performance_summary(db_path='trading_bot.db'):
    """성과 요약 표시"""
    try:
        conn = sqlite3.connect(db_path)
        
        # 전체 거래 통계
        query = """
        SELECT 
            COUNT(*) as total_trades,
            SUM(CASE WHEN side = 'sell' AND profit_amount > 0 THEN 1 ELSE 0 END) as win_trades,
            SUM(CASE WHEN side = 'sell' THEN 1 ELSE 0 END) as sell_trades,
            SUM(CASE WHEN side = 'sell' THEN profit_amount ELSE 0 END) as total_profit,
            SUM(CASE WHEN side = 'buy' THEN amount ELSE 0 END) as total_invested
        FROM trades_v2
        """
        
        result = conn.execute(query).fetchone()
        
        if result and result[0] > 0:
            total_trades, win_trades, sell_trades, total_profit, total_invested = result
            win_rate = (win_trades / sell_trades * 100) if sell_trades > 0 else 0
            roi = (total_profit / total_invested * 100) if total_invested > 0 else 0
            
            print("\n=== 전체 성과 요약 ===")
            print(f"총 거래 횟수: {total_trades}회")
            print(f"매도 거래: {sell_trades}회")
            print(f"승률: {win_rate:.1f}%")
            print(f"총 수익: {total_profit:+,.0f}원")
            print(f"총 투자: {total_invested:,.0f}원")
            print(f"수익률: {roi:+.2f}%")
        else:
            print("거래 데이터가 없습니다.")
        
        conn.close()
        
    except Exception as e:
        print(f"성과 요약 조회 오류: {e}")

def show_system_logs(lines=20):
    """시스템 로그 표시"""
    try:
        if os.path.exists('trading_bot.log'):
            print(f"\n=== 최근 시스템 로그 ({lines}줄) ===")
            with open('trading_bot.log', 'r', encoding='utf-8') as f:
                all_lines = f.readlines()
                recent_lines = all_lines[-lines:]
                for line in recent_lines:
                    print(line.strip())
        else:
            print("시스템 로그 파일이 없습니다.")
    except Exception as e:
        print(f"로그 파일 읽기 오류: {e}")

def main():
    print("거래 봇 로그 분석기")
    print("=" * 50)
    
    # 1. 파일 존재 확인
    check_log_files()
    
    # 2. 최근 거래 내역
    show_recent_trades(days=7)
    
    # 3. 포트폴리오 변화
    show_portfolio_changes(days=7)
    
    # 4. 성과 요약
    show_performance_summary()
    
    # 5. 시스템 로그
    show_system_logs(lines=30)
    
    print("\n분석 완료!")

if __name__ == "__main__":
    main()