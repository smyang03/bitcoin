#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
완전한 업비트 자동매매 시스템 - HTML UI + 백엔드 통합 버전 (수정됨)
"""

import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from flask import Flask, jsonify, render_template_string, request
import json
import pyupbit
import time
import logging
import threading

def create_enhanced_trading_dashboard(bot):
    """복잡한 HTML UI + 실제 백엔드 로직 통합 대시보드"""
    
    app = Flask(__name__)
    
    def get_detailed_status():
        """상세한 거래 상태 조회"""
        try:
            default_status = {
                'trading_mode': 'paper_trading',
                'is_running': getattr(bot, 'is_running', False),
                'is_paused': getattr(bot, 'is_paused', False),
                'initial_amount': float(bot.config.initial_amount),
                'total_balance': 0,
                'krw_balance': 0,
                'profit_amount': 0,
                'profit_rate': 0,
                'coin_balances': {},
                'daily_profit': 0,
                'daily_invested': 0,
                'daily_trades': 0,
                'positions': [],
                'positions_count': 0,
                'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            if bot.config.paper_trading and hasattr(bot, 'wallet') and bot.wallet is not None:
                total_balance = float(bot.wallet.get_total_value() or 0)
                krw_balance = float(bot.wallet.get_balance('KRW') or 0)
                coin_balances = {k: float(v) for k, v in bot.wallet.balances.items()
                               if k != 'KRW' and v > 0}
            else:
                total_balance = float(bot._get_total_balance() or 0)
                krw_balance = float(bot.upbit.get_balance('KRW') or 0) if hasattr(bot, 'upbit') and bot.upbit is not None else 0
                coin_balances = bot._get_coin_balances() or {}
            
            initial_amount = float(bot.config.initial_amount)
            profit_amount = total_balance - initial_amount
            profit_rate = (profit_amount / initial_amount) * 100 if initial_amount > 0 else 0
            
            # 포지션 정보
            positions = []
            if hasattr(bot, 'risk_manager') and hasattr(bot.risk_manager, 'positions'):
                for symbol, pos in bot.risk_manager.positions.items():
                    try:
                        current_price = pyupbit.get_current_price(symbol)
                        if current_price and pos.get('avg_price'):
                            entry_price = float(pos['avg_price'])
                            quantity = float(pos.get('quantity', 0))
                            invested = float(pos.get('total_invested', 0))
                            current_value = quantity * current_price
                            unrealized_pnl = ((current_price - entry_price) / entry_price) * 100
                            
                            positions.append({
                                'symbol': symbol,
                                'entry_price': entry_price,
                                'current_price': float(current_price),
                                'quantity': quantity,
                                'invested_amount': invested,
                                'current_value': current_value,
                                'unrealized_pnl': unrealized_pnl,
                                'entry_time': str(pos.get('entry_time', ''))
                            })
                    except Exception as e:
                        print(f"포지션 {symbol} 처리 오류: {e}")
                        continue
            
            default_status.update({
                'total_balance': total_balance,
                'krw_balance': krw_balance,
                'profit_amount': profit_amount,
                'profit_rate': profit_rate,
                'coin_balances': coin_balances,
                'positions': positions,
                'positions_count': len(positions)
            })
            
            return default_status
            
        except Exception as e:
            print(f"상태 조회 오류: {e}")
            return default_status
    
    def get_upbit_coins():
        """업비트 코인 목록 조회 - 백업 방법 포함"""
        try:
            print("업비트 코인 목록 조회 시작...")
            
            # 방법 1: pyupbit 라이브러리 사용
            try:
                markets = pyupbit.get_tickers(fiat="KRW")
                if markets and len(markets) > 0:
                    print(f"pyupbit로 {len(markets)}개 마켓 조회 성공")
                    return process_markets_with_pyupbit(markets[:100])  # 100개로 증가
            except Exception as e:
                print(f"pyupbit 방법 실패: {e}")
            
            # 방법 2: 직접 REST API 호출
            try:
                import requests
                print("직접 API 호출 시도 중...")
                
                # 마켓 목록 조회
                market_response = requests.get("https://api.upbit.com/v1/market/all", timeout=10)
                if market_response.status_code == 200:
                    markets_data = market_response.json()
                    krw_markets = [m['market'] for m in markets_data if m['market'].startswith('KRW-')][:100]
                    print(f"직접 API로 {len(krw_markets)}개 마켓 조회 성공")
                    
                    # 현재가 조회
                    if krw_markets:
                        return process_markets_with_api(krw_markets)
                        
            except Exception as e:
                print(f"직접 API 방법 실패: {e}")
            
            # 방법 3: 하드코딩된 주요 코인 목록
            print("백업 코인 목록 사용")
            return get_fallback_coins()
            
        except Exception as e:
            print(f"모든 방법 실패: {e}")
            return get_fallback_coins()

    def process_markets_with_pyupbit(markets):
        """pyupbit으로 마켓 데이터 처리"""
        try:
            coins = []
            # 현재가만 조회 (10개씩)
            for i in range(0, len(markets), 10):
                batch = markets[i:i+10]
                try:
                    # get_current_price로 현재가 조회
                    prices = pyupbit.get_current_price(batch)
                    if not prices:
                        continue
                    
                    # 단일 코인인 경우 딕셔너리로 변환
                    if not isinstance(prices, dict):
                        if len(batch) == 1:
                            prices = {batch[0]: prices}
                        else:
                            continue
                    
                    for market, price in prices.items():
                        if price and price > 0:
                            coin_data = {
                                'market': market,
                                'korean_name': market.replace('KRW-', ''),
                                'english_name': market.replace('KRW-', ''),
                                'current_price': float(price),
                                'change_rate': 0.0,  # 변동률은 기본값
                                'acc_trade_price_24h': 1000000000,  # 거래량 기본값
                                'change': 'EVEN',
                                'rsi': 50,
                                'volume_ratio': 1,
                                'trend': 'NEUTRAL',
                                'signal': 'HOLD'
                            }
                            coins.append(coin_data)
                    
                    time.sleep(0.1)
                except Exception as e:
                    print(f"배치 처리 오류: {e}")
                    continue
            
            print(f"pyupbit로 {len(coins)}개 코인 처리 완료")
            return coins
        except Exception as e:
            print(f"pyupbit 처리 오류: {e}")
            return []

    def process_markets_with_api(markets):
        """직접 API로 마켓 데이터 처리"""
        try:
            import requests
            coins = []
            
            # 티커 정보 조회
            markets_str = ','.join(markets)
            ticker_response = requests.get(f"https://api.upbit.com/v1/ticker?markets={markets_str}", timeout=10)
            
            if ticker_response.status_code == 200:
                tickers = ticker_response.json()
                
                for ticker in tickers:
                    coin_data = {
                        'market': ticker['market'],
                        'korean_name': ticker['market'].replace('KRW-', ''),
                        'english_name': ticker['market'].replace('KRW-', ''),
                        'current_price': float(ticker.get('trade_price', 0)),
                        'change_rate': float(ticker.get('change_rate', 0)),
                        'acc_trade_price_24h': float(ticker.get('acc_trade_price_24h', 0)),
                        'change': ticker.get('change', 'EVEN'),
                        'rsi': 50,
                        'volume_ratio': 1,
                        'trend': 'NEUTRAL',
                        'signal': 'HOLD'
                    }
                    coins.append(coin_data)
                
                print(f"직접 API로 {len(coins)}개 코인 처리 완료")
                return coins
                
        except Exception as e:
            print(f"직접 API 처리 오류: {e}")
        
        return []

    def get_fallback_coins():
        """백업용 주요 코인 목록 (현재가는 임시값)"""
        major_coins = [
            'KRW-BTC', 'KRW-ETH', 'KRW-XRP', 'KRW-ADA', 'KRW-DOT',
            'KRW-LINK', 'KRW-LTC', 'KRW-BCH', 'KRW-EOS', 'KRW-TRX',
            'KRW-VET', 'KRW-THETA', 'KRW-FIL', 'KRW-AAVE', 'KRW-ATOM',
            'KRW-NEO', 'KRW-WAVES', 'KRW-QTUM', 'KRW-OMG', 'KRW-ZRX'
        ]
        
        fallback_coins = []
        for market in major_coins:
            coin_name = market.replace('KRW-', '')
            fallback_coins.append({
                'market': market,
                'korean_name': coin_name,
                'english_name': coin_name,
                'current_price': 50000,  # 임시 가격
                'change_rate': 0.0,
                'acc_trade_price_24h': 1000000000,  # 10억
                'change': 'EVEN',
                'rsi': 50,
                'volume_ratio': 1,
                'trend': 'NEUTRAL',
                'signal': 'HOLD'
            })
        
        print(f"백업 코인 목록 {len(fallback_coins)}개 반환")
        return fallback_coins
    
    def get_trading_history(days=7):
        """거래 내역 조회"""
        try:
            conn = sqlite3.connect(bot.db.db_path)
            
            query = """
            SELECT timestamp, symbol, side, amount, price, profit_amount, profit_rate, strategy
            FROM trades_v2 
            WHERE timestamp >= datetime('now', '-{} days')
            ORDER BY timestamp DESC
            LIMIT 50
            """.format(days)
            
            df = pd.read_sql_query(query, conn)
            conn.close()
            
            if not df.empty:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df['date'] = df['timestamp'].dt.strftime('%m-%d %H:%M')
                df['amount'] = df['amount'].round(0)
                df['profit_amount'] = df['profit_amount'].fillna(0).round(0)
                df['profit_rate'] = df['profit_rate'].fillna(0).round(4)
                
                return df.to_dict('records')
            
            return []
            
        except Exception as e:
            print(f"거래 내역 조회 오류: {e}")
            return []
    
    def get_recent_logs(lines=50):
        """최근 로그 조회"""
        try:
            import os
            if not os.path.exists('trading_bot.log'):
                return ["로그 파일이 없습니다."]
                
            with open('trading_bot.log', 'r', encoding='utf-8') as f:
                all_lines = f.readlines()
                recent_lines = all_lines[-lines:]
                
                important_logs = []
                for line in recent_lines:
                    if any(keyword in line for keyword in ['매수', '매도', 'ERROR', 'WARNING', '신호', '수익', '시작', '중지']):
                        important_logs.append(line.strip())
                
                return important_logs[-20:] if important_logs else ["로그가 없습니다."]
        except Exception as e:
            return [f"로그 읽기 오류: {e}"]

    # HTML 템플릿 (수정된 버전)
    html_template = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>업비트 자동매매 시스템</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            min-height: 100vh;
            color: #fff;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }

        .header {
            background: rgba(255,255,255,0.1);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 30px;
            margin-bottom: 30px;
            border: 1px solid rgba(255,255,255,0.2);
        }

        .header h1 {
            font-size: 2.5rem;
            text-align: center;
            margin-bottom: 10px;
            background: linear-gradient(45deg, #FFD700, #FFA500);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }

        .status-bar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-top: 20px;
            flex-wrap: wrap;
            gap: 10px;
        }

        .status-item {
            background: rgba(255,255,255,0.1);
            padding: 15px 20px;
            border-radius: 10px;
            text-align: center;
            flex: 1;
            min-width: 150px;
        }

        .status-value {
            font-size: 1.5rem;
            font-weight: bold;
            margin-bottom: 5px;
        }

        .status-label {
            font-size: 0.9rem;
            opacity: 0.8;
        }

        .main-content {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 30px;
            margin-bottom: 30px;
        }

        .panel {
            background: rgba(255,255,255,0.1);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 30px;
            border: 1px solid rgba(255,255,255,0.2);
        }

        .panel h2 {
            margin-bottom: 20px;
            color: #FFD700;
            font-size: 1.5rem;
        }

        .form-group {
            margin-bottom: 20px;
        }

        .form-group label {
            display: block;
            margin-bottom: 8px;
            font-weight: 500;
        }

        .form-group input, .form-group select, .form-group textarea {
            width: 100%;
            padding: 12px;
            border: 1px solid rgba(255,255,255,0.3);
            background: rgba(255,255,255,0.1);
            border-radius: 8px;
            color: #fff;
            font-size: 1rem;
        }

        .form-group input::placeholder {
            color: rgba(255,255,255,0.6);
        }

        .form-group small {
            display: block;
            margin-top: 5px;
            font-size: 0.8rem;
            color: rgba(255,255,255,0.7);
        }

        .btn {
            padding: 12px 24px;
            border: none;
            border-radius: 8px;
            font-size: 1rem;
            cursor: pointer;
            transition: all 0.3s ease;
            font-weight: 500;
            margin: 5px;
        }

        .btn-primary {
            background: linear-gradient(45deg, #007bff, #0056b3);
            color: white;
        }

        .btn-success {
            background: linear-gradient(45deg, #28a745, #1e7e34);
            color: white;
        }

        .btn-danger {
            background: linear-gradient(45deg, #dc3545, #c82333);
            color: white;
        }

        .btn-warning {
            background: linear-gradient(45deg, #ffc107, #e0a800);
            color: #212529;
        }

        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        }

        .btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            transform: none;
        }

        .chart-container {
            grid-column: span 2;
            height: 400px;
            background: rgba(255,255,255,0.1);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 30px;
            border: 1px solid rgba(255,255,255,0.2);
        }

        .trading-log {
            grid-column: span 2;
            background: rgba(255,255,255,0.1);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 30px;
            border: 1px solid rgba(255,255,255,0.2);
            max-height: 400px;
            overflow-y: auto;
        }

        .log-entry {
            background: rgba(0,0,0,0.2);
            padding: 10px;
            margin-bottom: 10px;
            border-radius: 8px;
            border-left: 4px solid #007bff;
        }

        .log-entry.success {
            border-left-color: #28a745;
        }

        .log-entry.warning {
            border-left-color: #ffc107;
        }

        .log-entry.error {
            border-left-color: #dc3545;
        }

        .controls {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            margin-top: 20px;
        }

        .profit-positive {
            color: #00ff00;
        }

        .profit-negative {
            color: #ff4444;
        }

        .coin-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
        }

        .coin-table th, .coin-table td {
            padding: 8px;
            border: 1px solid rgba(255,255,255,0.2);
            text-align: left;
        }

        .coin-table th {
            background: rgba(255,255,255,0.1);
            font-weight: bold;
        }

        .coin-row {
            cursor: pointer;
        }

        .coin-row:hover {
            background: rgba(255,255,255,0.05);
        }

        .loading {
            text-align: center;
            padding: 20px;
            color: #ffc107;
        }

        #apiStatus {
            margin-top: 10px;
            padding: 10px;
            border-radius: 5px;
            font-weight: bold;
        }

        @media (max-width: 768px) {
            .main-content {
                grid-template-columns: 1fr;
            }
            
            .chart-container,
            .trading-log {
                grid-column: span 1;
            }
            
            .status-bar {
                flex-direction: column;
            }
            
            .status-item {
                width: 100%;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- 헤더 -->
        <div class="header">
            <h1>🚀 업비트 자동매매 시스템</h1>
            <div class="status-bar">
                <div class="status-item">
                    <div class="status-value" id="currentBalance">₩1,000,000</div>
                    <div class="status-label">현재 잔고</div>
                </div>
                <div class="status-item">
                    <div class="status-value profit-positive" id="dailyPnL">+0.00%</div>
                    <div class="status-label">일일 손익</div>
                </div>
                <div class="status-item">
                    <div class="status-value" id="activePositions">0</div>
                    <div class="status-label">활성 포지션</div>
                </div>
                <div class="status-item">
                    <div class="status-value" id="tradingStatus">중지됨</div>
                    <div class="status-label">거래 상태</div>
                </div>
                <div class="status-item">
                    <div class="status-value" id="lastUpdate">--:--</div>
                    <div class="status-label">마지막 업데이트</div>
                </div>
            </div>
        </div>

        <!-- 메인 컨텐츠 -->
        <div class="main-content">
            <!-- TradingConfig 설정 -->
            <div class="panel">
                <h2>⚙️ TradingConfig 설정</h2>
                
                <div class="form-group">
                    <label>초기 투자 금액 (원)</label>
                    <input type="number" id="initialAmount" value="1000000" min="10000" step="10000">
                </div>
                
                <div class="form-group">
                    <label>최소 거래 금액 (원)</label>
                    <input type="number" id="minTradeAmount" value="50000" min="5000" step="5000">
                </div>
                
                <div class="form-group">
                    <label>일일 최대 수익률 (%)</label>
                    <input type="number" id="maxDailyProfit" value="50" min="1" max="100" step="1">
                </div>
                
                <div class="form-group">
                    <label>일일 최대 손실률 (%)</label>
                    <input type="number" id="maxDailyLoss" value="3" min="1" max="20" step="0.1">
                </div>
                
                <div class="form-group">
                    <label>최대 동시 포지션 수</label>
                    <input type="number" id="maxPositions" value="5" min="1" max="10">
                </div>
                
                <div class="form-group">
                    <label>
                        <input type="checkbox" id="paperTrading" checked> 
                        모의거래 모드
                    </label>
                </div>
                
                <div class="form-group">
                    <button class="btn btn-success" onclick="saveTradingConfig()">설정 저장</button>
                    <button class="btn btn-primary" onclick="loadTradingConfig()">설정 불러오기</button>
                </div>
            </div>

            <!-- API 키 설정 -->
            <div class="panel">
                <h2>🔑 업비트 API 설정</h2>
                <div class="form-group">
                    <label>Access Key</label>
                    <input type="password" id="accessKey" placeholder="업비트 Access Key 입력">
                </div>
                <div class="form-group">
                    <label>Secret Key</label>
                    <input type="password" id="secretKey" placeholder="업비트 Secret Key 입력">
                </div>
                <div class="form-group">
                    <button class="btn btn-primary" onclick="testConnection()">연결 테스트</button>
                    <button class="btn btn-success" onclick="saveApiKeys()">저장</button>
                </div>
                <div id="apiStatus"></div>
            </div>

            <!-- 업비트 코인 목록 -->
            <div class="panel" style="grid-column: span 2;">
                <h2>🪙 업비트 코인 목록</h2>
                
                <div class="form-group">
                    <button class="btn btn-primary" onclick="loadUpbitCoins()">코인 목록 새로고침</button>
                    <span id="coinLoadStatus" style="color: #ccc; margin-left: 10px;"></span>
                </div>
                
                <div id="coinListContainer" style="max-height: 400px; overflow-y: auto;">
                    <table class="coin-table" id="coinTable">
                        <thead>
                            <tr>
                                <th>선택</th>
                                <th>코인</th>
                                <th>현재가</th>
                                <th>24h 변동률</th>
                                <th>24h 거래량</th>
                            </tr>
                        </thead>
                        <tbody id="coinTableBody">
                            <tr>
                                <td colspan="5" class="loading">
                                    "코인 목록 새로고침" 버튼을 눌러 업비트 코인을 불러오세요
                                </td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- 거래 제어 -->
            <div class="panel" style="grid-column: span 2;">
                <h2>🎮 거래 제어</h2>
                <div class="controls">
                    <button class="btn btn-success" id="startBtn" onclick="startTrading()">거래 시작</button>
                    <button class="btn btn-danger" id="stopBtn" onclick="stopTrading()" disabled>거래 중지</button>
                    <button class="btn btn-warning" onclick="pauseTrading()">일시 정지</button>
                    <button class="btn btn-danger" onclick="emergencySell()">긴급 매도</button>
                </div>
            </div>
        </div>

        <!-- 수익률 차트 -->
        <div class="chart-container">
            <h2>📊 실시간 수익률 차트</h2>
            <canvas id="profitChart"></canvas>
        </div>

        <!-- 거래 로그 -->
        <div class="trading-log">
            <h2>📈 거래 로그</h2>
            <div id="logContainer">
                <div class="log-entry">
                    <strong>[시스템]</strong> 자동매매 시스템이 준비되었습니다.
                </div>
            </div>
        </div>
    </div>

    <script>
        // 전역 변수
        let tradingBot = {
            isRunning: false,
            isPaused: false,
            dailyPnL: 0,
            positions: {},
            balance: 1000000,
            initialBalance: 1000000,
            trades: [],
            lastUpdate: new Date()
        };

        let profitChart;
        let chartData = {
            labels: [],
            datasets: [{
                label: '일일 수익률 (%)',
                data: [],
                borderColor: '#00ff00',
                backgroundColor: 'rgba(0, 255, 0, 0.1)',
                tension: 0.4,
                fill: true
            }]
        };

        let upbitCoins = [];
        let updateInterval;

        // API 호출 공통 함수
        async function apiCall(endpoint, method = 'GET', data = null) {
            try {
                const options = {
                    method: method,
                    headers: {
                        'Content-Type': 'application/json',
                    }
                };
                
                if (data) {
                    options.body = JSON.stringify(data);
                }
                
                const response = await fetch(endpoint, options);
                
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }
                
                const result = await response.json();
                return result;
                
            } catch (error) {
                console.error(`API 호출 오류 (${endpoint}):`, error);
                addLog(`❌ API 오류: ${error.message}`, 'error');
                return { success: false, message: error.message };
            }
        }

        // 차트 초기화
        function initChart() {
            const ctx = document.getElementById('profitChart').getContext('2d');
            profitChart = new Chart(ctx, {
                type: 'line',
                data: chartData,
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            labels: {
                                color: '#fff'
                            }
                        }
                    },
                    scales: {
                        x: {
                            ticks: { color: '#fff' },
                            grid: { color: 'rgba(255,255,255,0.1)' }
                        },
                        y: {
                            ticks: { color: '#fff' },
                            grid: { color: 'rgba(255,255,255,0.1)' }
                        }
                    }
                }
            });
        }

        // TradingConfig 저장
        async function saveTradingConfig() {
            try {
                const selectedCoins = Array.from(document.querySelectorAll('input[id^="coin_"]:checked'))
                                        .map(cb => cb.value);
                
                const config = {
                    initial_amount: parseFloat(document.getElementById('initialAmount').value),
                    min_trade_amount: parseFloat(document.getElementById('minTradeAmount').value),
                    max_daily_profit: parseFloat(document.getElementById('maxDailyProfit').value),
                    max_daily_loss: parseFloat(document.getElementById('maxDailyLoss').value),
                    max_positions: parseInt(document.getElementById('maxPositions').value),
                    paper_trading: document.getElementById('paperTrading').checked,
                    target_coins: selectedCoins
                };
                
                addLog('설정 저장 중...', 'info');
                const result = await apiCall('/api/config', 'POST', config);
                
                if (result.success) {
                    addLog(`✅ 설정 저장완료`, 'success');
                    alert('설정이 저장되었습니다.');
                } else {
                    throw new Error(result.message);
                }
            } catch (error) {
                addLog(`❌ 설정 저장 실패: ${error.message}`, 'error');
                alert(`설정 저장에 실패했습니다: ${error.message}`);
            }
        }

        // TradingConfig 불러오기
        async function loadTradingConfig() {
            try {
                addLog('설정 불러오는 중...', 'info');
                const result = await apiCall('/api/config');
                
                if (result.success && result.config) {
                    const config = result.config;
                    
                    document.getElementById('initialAmount').value = config.initial_amount || 1000000;
                    document.getElementById('minTradeAmount').value = config.min_trade_amount || 50000;
                    document.getElementById('maxDailyProfit').value = config.max_daily_profit || 50;
                    document.getElementById('maxDailyLoss').value = config.max_daily_loss || 3;
                    document.getElementById('maxPositions').value = config.max_positions || 5;
                    document.getElementById('paperTrading').checked = config.paper_trading !== false;
                    
                    addLog('📥 TradingConfig 설정을 불러왔습니다.', 'success');
                } else {
                    addLog('⚠️ 저장된 설정이 없습니다. 기본값을 사용합니다.', 'warning');
                }
            } catch (error) {
                addLog(`❌ 설정 로드 실패: ${error.message}`, 'error');
            }
        }

        // API 키 저장
        function saveApiKeys() {
            const accessKey = document.getElementById('accessKey').value;
            const secretKey = document.getElementById('secretKey').value;
            
            if (!accessKey || !secretKey) {
                alert('API 키를 모두 입력해주세요.');
                return;
            }

            localStorage.setItem('upbit_access_key', btoa(accessKey));
            localStorage.setItem('upbit_secret_key', btoa(secretKey));
            
            document.getElementById('apiStatus').innerHTML = 
                '<div style="color: #00ff00; background: rgba(0,255,0,0.1); padding: 10px; border-radius: 5px;">✅ API 키가 저장되었습니다.</div>';
            
            addLog('API 키가 성공적으로 저장되었습니다.', 'success');
        }

        // API 연결 테스트
        async function testConnection() {
            const accessKey = document.getElementById('accessKey').value;
            const secretKey = document.getElementById('secretKey').value;
            
            if (!accessKey || !secretKey) {
                alert('API 키를 먼저 입력해주세요.');
                return;
            }

            document.getElementById('apiStatus').innerHTML = 
                '<div style="color: #ffc107; background: rgba(255,193,7,0.1); padding: 10px; border-radius: 5px;">연결 테스트 중...</div>';

            try {
                const result = await apiCall('/api/test_connection', 'POST', {
                    access_key: accessKey,
                    secret_key: secretKey
                });
                
                if (result.success) {
                    document.getElementById('apiStatus').innerHTML = 
                        '<div style="color: #00ff00; background: rgba(0,255,0,0.1); padding: 10px; border-radius: 5px;">✅ 연결 성공! API 키가 유효합니다.</div>';
                    addLog('업비트 API 연결 테스트 성공', 'success');
                } else {
                    document.getElementById('apiStatus').innerHTML = 
                        '<div style="color: #ff4444; background: rgba(255,68,68,0.1); padding: 10px; border-radius: 5px;">❌ 연결 실패: ' + result.message + '</div>';
                    addLog('업비트 API 연결 실패: ' + result.message, 'error');
                }
            } catch (error) {
                document.getElementById('apiStatus').innerHTML = 
                    '<div style="color: #ff4444; background: rgba(255,68,68,0.1); padding: 10px; border-radius: 5px;">❌ 연결 오류: ' + error.message + '</div>';
                addLog('API 연결 오류: ' + error.message, 'error');
            }
        }

        // 업비트 코인 목록 로드
        async function loadUpbitCoins() {
            document.getElementById('coinLoadStatus').textContent = '코인 목록 로딩 중...';
            document.getElementById('coinTableBody').innerHTML = 
                '<tr><td colspan="5" class="loading">코인 목록을 불러오는 중...</td></tr>';
            
            try {
                const result = await apiCall('/api/coins');
                
                if (result.success && result.coins) {
                    upbitCoins = result.coins;
                    updateCoinTable();
                    document.getElementById('coinLoadStatus').textContent = 
                        `${result.coins.length}개 코인 로드 완료`;
                    addLog(`업비트 코인 ${result.coins.length}개 로드 완료`, 'success');
                } else {
                    throw new Error(result.message || '코인 목록 로드 실패');
                }
            } catch (error) {
                document.getElementById('coinLoadStatus').textContent = '로드 실패';
                document.getElementById('coinTableBody').innerHTML = 
                    '<tr><td colspan="5" style="text-align: center; color: #ff4444;">코인 목록 로드 실패: ' + error.message + '</td></tr>';
                addLog(`코인 목록 로드 실패: ${error.message}`, 'error');
            }
        }

        // 코인 테이블 업데이트
        function updateCoinTable() {
            const tbody = document.getElementById('coinTableBody');
            tbody.innerHTML = '';
            
            upbitCoins.forEach((coin, index) => {
                const row = document.createElement('tr');
                row.className = 'coin-row';
                row.dataset.market = coin.market;
                
                const changeColor = coin.change === 'RISE' ? '#ff4444' : 
                                   coin.change === 'FALL' ? '#4444ff' : '#ccc';
                
                // 상위 10개 코인만 기본 체크 (안전한 선택)
                const isTopCoin = index < 10;
                
                row.innerHTML = `
                    <td style="text-align: center;">
                        <input type="checkbox" id="coin_${coin.market}" value="${coin.market}" 
                               onchange="updateSelectedCoins()" ${isTopCoin ? 'checked' : ''}>
                    </td>
                    <td>
                        <div style="font-weight: bold;">${coin.market.replace('KRW-', '')}</div>
                        <div style="font-size: 0.8rem; color: #ccc;">${coin.korean_name}</div>
                    </td>
                    <td style="text-align: right; font-weight: bold;">
                        ₩${coin.current_price.toLocaleString()}
                    </td>
                    <td style="text-align: right; color: ${changeColor}; font-weight: bold;">
                        ${(coin.change_rate * 100).toFixed(2)}%
                    </td>
                    <td style="text-align: right;">
                        ₩${Math.round(coin.acc_trade_price_24h / 1000000).toLocaleString()}M
                    </td>
                `;
                
                tbody.appendChild(row);
            });
            
            // 체크된 코인 상태 업데이트
            updateSelectedCoins();
        }

        // 선택된 코인 업데이트
        function updateSelectedCoins() {
            const selected = Array.from(document.querySelectorAll('input[id^="coin_"]:checked'))
                                 .map(cb => cb.value);
            
            addLog(`선택된 코인: ${selected.length}개`, 'info');
        }

        // 거래 시작
        async function startTrading() {
            if (tradingBot.isRunning) {
                addLog('거래가 이미 실행 중입니다.', 'warning');
                return;
            }

            try {
                addLog('거래 시작 요청 중...', 'info');
                const result = await apiCall('/api/start', 'POST');
                
                if (result.success) {
                    tradingBot.isRunning = true;
                    document.getElementById('startBtn').disabled = true;
                    document.getElementById('stopBtn').disabled = false;
                    document.getElementById('tradingStatus').textContent = '실행 중';
                    
                    addLog('✅ 자동매매가 시작되었습니다.', 'success');
                    startRealTimeUpdate();
                } else {
                    addLog(`❌ 거래 시작 실패: ${result.message}`, 'error');
                }
            } catch (error) {
                addLog(`❌ 거래 시작 오류: ${error.message}`, 'error');
            }
        }

        // 거래 중지
        async function stopTrading() {
            try {
                addLog('거래 중지 요청 중...', 'info');
                const result = await apiCall('/api/stop', 'POST');
                
                if (result.success) {
                    tradingBot.isRunning = false;
                    tradingBot.isPaused = false;
                    document.getElementById('startBtn').disabled = false;
                    document.getElementById('stopBtn').disabled = true;
                    document.getElementById('tradingStatus').textContent = '중지됨';
                    
                    if (updateInterval) {
                        clearInterval(updateInterval);
                        updateInterval = null;
                    }
                    
                    addLog('⏹️ 자동매매가 중지되었습니다.', 'warning');
                } else {
                    addLog(`❌ 거래 중지 실패: ${result.message}`, 'error');
                }
            } catch (error) {
                addLog(`❌ 거래 중지 오류: ${error.message}`, 'error');
            }
        }

        // 일시 정지
        async function pauseTrading() {
            try {
                const result = await apiCall('/api/pause', 'POST');
                
                if (result.success) {
                    tradingBot.isPaused = !tradingBot.isPaused;
                    const status = tradingBot.isPaused ? '일시정지' : '실행 중';
                    document.getElementById('tradingStatus').textContent = status;
                    addLog(`⏸️ 거래가 ${status}되었습니다.`, 'warning');
                }
            } catch (error) {
                addLog(`❌ 일시정지 오류: ${error.message}`, 'error');
            }
        }

        // 긴급 매도
        async function emergencySell() {
            if (!confirm('모든 포지션을 긴급 매도하시겠습니까?')) {
                return;
            }
            
            try {
                addLog('🚨 긴급 매도 실행 중...', 'error');
                const result = await apiCall('/api/emergency_sell', 'POST');
                
                if (result.success) {
                    addLog(`✅ ${result.message}`, 'success');
                    updateDisplay();
                } else {
                    addLog(`❌ 긴급 매도 실패: ${result.message}`, 'error');
                }
            } catch (error) {
                addLog(`❌ 긴급 매도 오류: ${error.message}`, 'error');
            }
        }

        // 디스플레이 업데이트
        async function updateDisplay() {
            try {
                const result = await apiCall('/api/status');
                
                if (result.success && result.data) {
                    const status = result.data;
                    
                    // 상태 업데이트
                    document.getElementById('currentBalance').textContent = 
                        `₩${status.total_balance.toLocaleString()}`;
                    
                    const profitAmount = status.total_balance - status.initial_amount;
                    const profitRate = (profitAmount / status.initial_amount) * 100;
                    
                    const pnlElement = document.getElementById('dailyPnL');
                    pnlElement.textContent = `${profitRate >= 0 ? '+' : ''}${profitRate.toFixed(2)}%`;
                    pnlElement.className = profitRate >= 0 ? 'status-value profit-positive' : 'status-value profit-negative';
                    
                    document.getElementById('activePositions').textContent = status.positions_count || 0;
                    document.getElementById('tradingStatus').textContent = status.is_running ? 
                        (status.is_paused ? '일시정지' : '실행 중') : '중지됨';
                    document.getElementById('lastUpdate').textContent = 
                        new Date(status.last_update).toLocaleTimeString();
                    
                    // 전역 상태 업데이트
                    tradingBot.isRunning = status.is_running;
                    tradingBot.isPaused = status.is_paused;
                    tradingBot.balance = status.total_balance;
                    tradingBot.dailyPnL = profitRate;
                    
                    // 버튼 상태 업데이트
                    document.getElementById('startBtn').disabled = status.is_running;
                    document.getElementById('stopBtn').disabled = !status.is_running;
                }
            } catch (error) {
                addLog(`상태 업데이트 실패: ${error.message}`, 'error');
            }
        }

        // 실시간 업데이트 시작
        function startRealTimeUpdate() {
            if (updateInterval) {
                clearInterval(updateInterval);
            }
            
            updateInterval = setInterval(() => {
                if (tradingBot.isRunning && !tradingBot.isPaused) {
                    updateDisplay();
                    updateChart();
                }
            }, 5000); // 5초마다
        }

        // 차트 업데이트
        function updateChart() {
            const now = new Date();
            const timeLabel = now.toLocaleTimeString();
            const profitPercent = tradingBot.dailyPnL;
            
            chartData.labels.push(timeLabel);
            chartData.datasets[0].data.push(profitPercent);
            
            // 최대 50개 데이터 포인트 유지
            if (chartData.labels.length > 50) {
                chartData.labels.shift();
                chartData.datasets[0].data.shift();
            }
            
            // 차트 색상 업데이트
            chartData.datasets[0].borderColor = profitPercent >= 0 ? '#00ff00' : '#ff4444';
            chartData.datasets[0].backgroundColor = profitPercent >= 0 ? 'rgba(0, 255, 0, 0.1)' : 'rgba(255, 68, 68, 0.1)';
            
            if (profitChart) {
                profitChart.update('none');
            }
        }

        // 로그 추가
        function addLog(message, type = 'info') {
            const logContainer = document.getElementById('logContainer');
            const logEntry = document.createElement('div');
            logEntry.className = `log-entry ${type}`;
            
            const timestamp = new Date().toLocaleTimeString();
            logEntry.innerHTML = `<strong>[${timestamp}]</strong> ${message}`;
            
            // 최신 로그를 위에 추가
            logContainer.insertBefore(logEntry, logContainer.firstChild);
            
            // 최대 100개 로그 유지
            while (logContainer.children.length > 100) {
                logContainer.removeChild(logContainer.lastChild);
            }
        }

        // 설정값 불러오기 (localStorage에서)
        function loadSettings() {
            const accessKey = localStorage.getItem('upbit_access_key');
            const secretKey = localStorage.getItem('upbit_secret_key');
            
            if (accessKey) {
                try {
                    document.getElementById('accessKey').value = atob(accessKey);
                } catch (e) {
                    console.error('API 키 디코딩 오류:', e);
                }
            }
            if (secretKey) {
                try {
                    document.getElementById('secretKey').value = atob(secretKey);
                } catch (e) {
                    console.error('Secret 키 디코딩 오류:', e);
                }
            }
        }

        // 페이지 로드 완료 후 초기화
        window.addEventListener('load', async function() {
            try {
                addLog('시스템 초기화 중...', 'info');
                
                // 차트 초기화
                initChart();
                
                // 설정 불러오기
                loadSettings();
                await loadTradingConfig();
                
                // 상태 업데이트
                await updateDisplay();
                
                // 주기적 업데이트 시작 (거래 중이 아니어도 상태는 확인)
                setInterval(updateDisplay, 10000); // 10초마다 상태 확인
                
                addLog('✅ 업비트 자동매매 시스템이 준비되었습니다!', 'success');
                addLog('💡 팁: 먼저 API 키를 설정하고 연결을 테스트하세요.', 'info');
                
            } catch (error) {
                addLog(`❌ 초기화 실패: ${error.message}`, 'error');
                console.error('System initialization failed:', error);
            }
        });

        // 페이지 종료 시 경고
        window.addEventListener('beforeunload', function(e) {
            if (tradingBot.isRunning) {
                e.preventDefault();
                e.returnValue = '거래가 실행 중입니다. 정말 페이지를 나가시겠습니까?';
            }
        });

        // 키보드 단축키
        document.addEventListener('keydown', function(e) {
            if (e.ctrlKey || e.metaKey) {
                switch(e.key) {
                    case 's':
                        e.preventDefault();
                        if (tradingBot.isRunning) {
                            stopTrading();
                        } else {
                            startTrading();
                        }
                        break;
                    case 'e':
                        e.preventDefault();
                        emergencySell();
                        break;
                }
            }
        });

    </script>
</body>
</html>
    """
    
    @app.route('/')
    def dashboard():
        try:
            status = get_detailed_status()
            trades = get_trading_history()
            logs = get_recent_logs()
            
            return render_template_string(html_template, 
                                        status=status, 
                                        trades=trades, 
                                        logs=logs)
        except Exception as e:
            return f"대시보드 오류: {e}"
    
    # API 엔드포인트들
    @app.route('/api/start', methods=['POST'])
    def start_trading():
        try:
            if not getattr(bot, 'is_running', False):
                import threading
                bot.is_running = True
                threading.Thread(target=bot.start, daemon=True).start()
                return jsonify({'success': True, 'message': '거래를 시작했습니다.'})
            else:
                return jsonify({'success': False, 'message': '이미 실행 중입니다.'})
        except Exception as e:
            return jsonify({'success': False, 'message': f'오류: {e}'})
    
    @app.route('/api/stop', methods=['POST'])
    def stop_trading():
        try:
            if hasattr(bot, 'stop'):
                bot.stop()
            bot.is_running = False
            return jsonify({'success': True, 'message': '거래를 중지했습니다.'})
        except Exception as e:
            return jsonify({'success': False, 'message': f'오류: {e}'})
    
    @app.route('/api/pause', methods=['POST'])
    def pause_trading():
        try:
            bot.is_paused = not getattr(bot, 'is_paused', False)
            status = '일시정지' if bot.is_paused else '재시작'
            return jsonify({'success': True, 'message': f'거래를 {status}했습니다.'})
        except Exception as e:
            return jsonify({'success': False, 'message': f'오류: {e}'})
    
    @app.route('/api/emergency_sell', methods=['POST'])
    def emergency_sell():
        try:
            # 긴급 매도 로직
            sold_count = 0
            if hasattr(bot, 'risk_manager') and hasattr(bot.risk_manager, 'positions'):
                for symbol in list(bot.risk_manager.positions.keys()):
                    try:
                        # 모의거래든 실거래든 포지션 정리
                        if bot.config.paper_trading and hasattr(bot, 'wallet'):
                            pos = bot.risk_manager.positions[symbol]
                            current_price = pyupbit.get_current_price(symbol)
                            if current_price:
                                quantity = pos.get('quantity', 0)
                                sell_amount = quantity * current_price
                                bot.wallet.add_balance('KRW', sell_amount)
                                del bot.risk_manager.positions[symbol]
                                sold_count += 1
                        else:
                            # 실거래 긴급 매도는 실제 API 호출 필요
                            pass
                    except Exception as e:
                        print(f"긴급 매도 오류 {symbol}: {e}")
                        continue
            
            return jsonify({
                'success': True, 
                'message': f'긴급 매도 완료: {sold_count}개 포지션 정리'
            })
        except Exception as e:
            return jsonify({'success': False, 'message': f'긴급 매도 실패: {e}'})
    
    @app.route('/api/status')
    def get_status_api():
        try:
            status = get_detailed_status()
            return jsonify({'success': True, 'data': status})
        except Exception as e:
            return jsonify({'success': False, 'message': f'상태 조회 실패: {str(e)}'})
    
    @app.route('/api/coins')
    def get_coins_api():
        try:
            coins = get_upbit_coins()
            return jsonify({'success': True, 'coins': coins})
        except Exception as e:
            return jsonify({'success': False, 'message': f'코인 목록 조회 실패: {str(e)}'})
    
    @app.route('/api/config', methods=['POST'])
    def update_config():
        try:
            settings = request.get_json()
            
            # TradingConfig 업데이트
            if 'initial_amount' in settings:
                bot.config.initial_amount = float(settings['initial_amount'])
            if 'min_trade_amount' in settings:
                bot.config.min_trade_amount = float(settings['min_trade_amount'])
            if 'max_daily_profit' in settings:
                bot.config.max_daily_profit = float(settings['max_daily_profit']) / 100
            if 'max_daily_loss' in settings:
                bot.config.max_daily_loss = float(settings['max_daily_loss']) / 100
            if 'max_positions' in settings:
                bot.config.max_positions = int(settings['max_positions'])
            if 'paper_trading' in settings:
                bot.config.paper_trading = bool(settings['paper_trading'])
            if 'target_coins' in settings:
                bot.config.target_coins = settings['target_coins']
            
            # 파일로 저장
            if hasattr(bot.config, 'save_to_file'):
                bot.config.save_to_file()
            
            return jsonify({
                'success': True, 
                'message': '설정이 업데이트되었습니다.',
                'config': {
                    'initial_amount': bot.config.initial_amount,
                    'min_trade_amount': bot.config.min_trade_amount,
                    'max_daily_profit': bot.config.max_daily_profit * 100,
                    'max_daily_loss': bot.config.max_daily_loss * 100,
                    'max_positions': bot.config.max_positions,
                    'paper_trading': bot.config.paper_trading,
                    'target_coins': getattr(bot.config, 'target_coins', [])
                }
            })
            
        except Exception as e:
            return jsonify({'success': False, 'message': f'설정 업데이트 실패: {str(e)}'})

    @app.route('/api/config', methods=['GET'])
    def get_config_api():
        try:
            return jsonify({
                'success': True,
                'config': {
                    'initial_amount': bot.config.initial_amount,
                    'min_trade_amount': bot.config.min_trade_amount,
                    'max_daily_profit': bot.config.max_daily_profit * 100,
                    'max_daily_loss': bot.config.max_daily_loss * 100,
                    'max_positions': bot.config.max_positions,
                    'paper_trading': bot.config.paper_trading,
                    'target_coins': getattr(bot.config, 'target_coins', [])
                }
            })
        except Exception as e:
            return jsonify({'success': False, 'message': f'설정 조회 실패: {str(e)}'})
    
    @app.route('/api/test_connection', methods=['POST'])
    def test_connection():
        try:
            data = request.get_json()
            access_key = data.get('access_key', '')
            secret_key = data.get('secret_key', '')
            
            if not access_key or not secret_key:
                return jsonify({'success': False, 'message': 'API 키가 필요합니다.'})
            
            # 실제 업비트 API 연결 테스트
            try:
                import pyupbit
                test_upbit = pyupbit.Upbit(access=access_key, secret=secret_key)
                balance = test_upbit.get_balance('KRW')  # 잔고 조회로 연결 테스트
                return jsonify({'success': True, 'message': 'API 연결 성공', 'balance': balance})
            except Exception as e:
                return jsonify({'success': False, 'message': f'API 연결 실패: {str(e)}'})
                
        except Exception as e:
            return jsonify({'success': False, 'message': f'테스트 실패: {str(e)}'})
    
    @app.route('/api/test_coins')
    def test_coins_api():
        """코인 API 테스트용 엔드포인트"""
        try:
            # 1단계: 기본 연결 테스트
            import requests
            response = requests.get("https://api.upbit.com/v1/market/all", timeout=10)
            markets_raw = response.json()
            krw_markets = [m['market'] for m in markets_raw if m['market'].startswith('KRW-')]
            
            # 2단계: pyupbit 라이브러리 테스트
            try:
                pyupbit_markets = pyupbit.get_tickers(fiat="KRW")
                pyupbit_count = len(pyupbit_markets) if pyupbit_markets else 0
            except Exception as e:
                pyupbit_count = 0
                pyupbit_error = str(e)
            
            # 3단계: 실제 코인 데이터 함수 테스트
            coins_data = get_upbit_coins()
            
            return jsonify({
                'success': True,
                'debug_info': {
                    'direct_api_markets': len(krw_markets),
                    'pyupbit_markets': pyupbit_count,
                    'processed_coins': len(coins_data),
                    'sample_markets': krw_markets[:5],
                    'sample_coins': coins_data[:3] if coins_data else []
                }
            })
            
        except Exception as e:
            return jsonify({
                'success': False, 
                'error': str(e),
                'debug_info': 'API 테스트 실패'
            })

    return app