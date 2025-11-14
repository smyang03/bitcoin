#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
웹 서버 모듈
"""

import time
import threading
from flask import Flask, request, jsonify, render_template_string
from flask_socketio import SocketIO, emit
from dataclasses import asdict

from trading_bot import TradingBot


class WebServer:
    """웹 서버 클래스"""
    
    def __init__(self, trading_bot: TradingBot):
        self.trading_bot = trading_bot
        self.app = Flask(__name__)
        self.app.config['SECRET_KEY'] = 'upbit-trading-bot-secret-key'
        self.socketio = SocketIO(self.app, cors_allowed_origins="*")
        
        self._setup_routes()
        self._setup_websocket_events()
        self._start_status_broadcaster()
    
    def _setup_routes(self):
        """API 라우트 설정"""
        
        @self.app.route('/')
        def index():
            """메인 대시보드"""
            return render_template_string(self._get_dashboard_html())
        
        @self.app.route('/api/status')
        def get_status():
            """상태 조회 API"""
            try:
                return jsonify(self.trading_bot.get_status())
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/start', methods=['POST'])
        def start_trading():
            """거래 시작 API"""
            try:
                success = self.trading_bot.start()
                return jsonify({'success': success})
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/stop', methods=['POST'])
        def stop_trading():
            """거래 중지 API"""
            try:
                success = self.trading_bot.stop()
                return jsonify({'success': success})
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/pause', methods=['POST'])
        def pause_trading():
            """거래 일시정지 API"""
            try:
                self.trading_bot.pause_trading()
                return jsonify({'success': True})
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/resume', methods=['POST'])
        def resume_trading():
            """거래 재개 API"""
            try:
                self.trading_bot.resume_trading()
                return jsonify({'success': True})
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/emergency_sell', methods=['POST'])
        def emergency_sell():
            """긴급 매도 API"""
            try:
                success = self.trading_bot.emergency_sell_all()
                return jsonify({'success': success})
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/config', methods=['POST'])
        def update_config():
            """설정 업데이트 API"""
            try:
                config_data = request.get_json()
                success = self.trading_bot.update_config(config_data)
                return jsonify({'success': success})
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/telegram/set', methods=['POST'])
        def set_telegram():
            """텔레그램 설정 API"""
            try:
                data = request.get_json()
                self.trading_bot.set_telegram_credentials(
                    data.get('token'), 
                    data.get('chat_id')
                )
                return jsonify({'success': True})
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/trades/today')
        def get_today_trades():
            """오늘 거래 내역 API"""
            try:
                trades = self.trading_bot.db.get_daily_trades()
                return jsonify([asdict(trade) for trade in trades])
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/performance')
        def get_performance():
            """성과 분석 API"""
            try:
                performance = self.trading_bot.db.get_trading_performance(7)
                return jsonify(performance)
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/claude/manual_analysis', methods=['POST'])
        def manual_claude_analysis():
            """수동 Claude 분석 API"""
            try:
                market_data = self.trading_bot._get_portfolio_market_data()
                analysis = self.trading_bot.claude.analyze_market_condition(
                    market_data, 
                    self.trading_bot.risk_manager.positions, 
                    self.trading_bot.config
                )
                return jsonify(analysis)
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/logs')
        def get_logs():
            """로그 조회 API"""
            try:
                limit = request.args.get('limit', 100, type=int)
                logs = self.trading_bot.logger.get_recent_logs(limit)
                return jsonify(logs)
            except Exception as e:
                return jsonify({'error': str(e)}), 500
    
    def _setup_websocket_events(self):
        """WebSocket 이벤트 설정"""
        
        @self.socketio.on('connect')
        def handle_connect():
            """클라이언트 연결"""
            try:
                emit('status_update', self.trading_bot.get_status())
            except Exception as e:
                emit('error', {'message': str(e)})
        
        @self.socketio.on('request_status')
        def handle_status_request():
            """상태 요청"""
            try:
                emit('status_update', self.trading_bot.get_status())
            except Exception as e:
                emit('error', {'message': str(e)})
        
        @self.socketio.on('request_logs')
        def handle_logs_request(data):
            """로그 요청"""
            try:
                limit = data.get('limit', 50)
                logs = self.trading_bot.logger.get_recent_logs(limit)
                emit('logs_update', logs)
            except Exception as e:
                emit('error', {'message': str(e)})
    
    def _start_status_broadcaster(self):
        """실시간 상태 브로드캐스트 시작"""
        def status_broadcaster():
            """실시간 상태 브로드캐스트"""
            while True:
                try:
                    if self.trading_bot.is_running:
                        status = self.trading_bot.get_status()
                        self.socketio.emit('status_update', status)
                    time.sleep(5)  # 5초마다 업데이트
                except Exception as e:
                    print(f"상태 브로드캐스트 오류: {e}")
                    time.sleep(10)
        
        broadcast_thread = threading.Thread(target=status_broadcaster, daemon=True)
        broadcast_thread.start()
    
    def _get_dashboard_html(self) -> str:
        """대시보드 HTML 반환"""
        return '''
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>업비트 자동매매 대시보드</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.9.1/chart.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #1a1a1a; color: #ffffff; }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        .header { text-align: center; margin-bottom: 30px; }
        .header h1 { color: #00d4aa; margin-bottom: 10px; }
        .status-bar { display: flex; justify-content: center; gap: 20px; margin-bottom: 30px; }
        .status-item { background: #2a2a2a; padding: 15px 25px; border-radius: 10px; text-align: center; }
        .status-item.running { border-left: 4px solid #00d4aa; }
        .status-item.paused { border-left: 4px solid #ffa500; }
        .status-item.stopped { border-left: 4px solid #ff4757; }
        .controls { display: flex; justify-content: center; gap: 10px; margin-bottom: 30px; }
        .btn { padding: 12px 24px; border: none; border-radius: 6px; cursor: pointer; font-weight: bold; transition: all 0.3s; }
        .btn-primary { background: #00d4aa; color: white; }
        .btn-primary:hover { background: #00b894; }
        .btn-danger { background: #ff4757; color: white; }
        .btn-danger:hover { background: #ff3742; }
        .btn-warning { background: #ffa500; color: white; }
        .btn-warning:hover { background: #ff8c00; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }
        .card { background: #2a2a2a; border-radius: 10px; padding: 20px; }
        .card h3 { color: #00d4aa; margin-bottom: 15px; }
        .metric { display: flex; justify-content: space-between; margin-bottom: 10px; }
        .metric-value { font-weight: bold; }
        .positive { color: #00d4aa; }
        .negative { color: #ff4757; }
        .positions { margin-top: 20px; }
        .position-item { background: #333; padding: 10px; margin: 5px 0; border-radius: 5px; }
        .logs { max-height: 400px; overflow-y: auto; background: #1e1e1e; padding: 15px; border-radius: 5px; }
        .log-item { margin: 5px 0; padding: 5px; border-left: 3px solid #444; }
        .log-info { border-left-color: #00d4aa; }
        .log-warning { border-left-color: #ffa500; }
        .log-error { border-left-color: #ff4757; }
        .settings { margin-top: 20px; }
        .form-group { margin-bottom: 15px; }
        .form-group label { display: block; margin-bottom: 5px; color: #ccc; }
        .form-group input { width: 100%; padding: 8px; background: #333; border: 1px solid #555; border-radius: 4px; color: white; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 업비트 자동매매 대시보드</h1>
            <p>실시간 모니터링 및 제어</p>
        </div>

        <div class="status-bar">
            <div class="status-item" id="status-indicator">
                <div>상태</div>
                <div id="status-text">로딩중...</div>
            </div>
            <div class="status-item">
                <div>총 잔고</div>
                <div id="total-balance">₩0</div>
            </div>
            <div class="status-item">
                <div>일일 손익</div>
                <div id="daily-pnl">0.00%</div>
            </div>
            <div class="status-item">
                <div>활성 포지션</div>
                <div id="positions-count">0</div>
            </div>
        </div>

        <div class="controls">
            <button class="btn btn-primary" onclick="startTrading()">거래 시작</button>
            <button class="btn btn-warning" onclick="pauseTrading()">일시정지</button>
            <button class="btn btn-primary" onclick="resumeTrading()">재개</button>
            <button class="btn btn-danger" onclick="stopTrading()">거래 중지</button>
            <button class="btn btn-danger" onclick="emergencySell()">긴급 매도</button>
        </div>

        <div class="grid">
            <div class="card">
                <h3>거래 현황</h3>
                <div class="metric">
                    <span>오늘 거래 횟수</span>
                    <span class="metric-value" id="daily-trades">0</span>
                </div>
                <div class="metric">
                    <span>일일 수익률</span>
                    <span class="metric-value" id="daily-profit-rate">0.00%</span>
                </div>
                <div class="positions" id="positions-list">
                    <h4>활성 포지션</h4>
                    <div id="positions-content">포지션이 없습니다</div>
                </div>
            </div>

            <div class="card">
                <h3>Claude AI 분석</h3>
                <div id="claude-analysis">
                    <button class="btn btn-primary" onclick="requestClaudeAnalysis()">수동 분석 요청</button>
                    <div id="claude-result" style="margin-top: 15px;"></div>
                </div>
            </div>

            <div class="card">
                <h3>시스템 로그</h3>
                <div class="logs" id="logs-container">
                    로그를 불러오는 중...
                </div>
            </div>

            <div class="card">
                <h3>설정</h3>
                <div class="settings">
                    <div class="form-group">
                        <label>텔레그램 봇 토큰</label>
                        <input type="text" id="telegram-token" placeholder="봇 토큰 입력">
                    </div>
                    <div class="form-group">
                        <label>텔레그램 채팅 ID</label>
                        <input type="text" id="telegram-chat-id" placeholder="채팅 ID 입력">
                    </div>
                    <button class="btn btn-primary" onclick="saveTelegramSettings()">텔레그램 설정 저장</button>
                </div>
            </div>
        </div>
    </div>

    <script>
        const socket = io();
        
        // WebSocket 이벤트 리스너
        socket.on('status_update', updateStatus);
        socket.on('logs_update', updateLogs);
        socket.on('error', (data) => {
            console.error('Socket error:', data);
            alert('오류: ' + data.message);
        });

        // 상태 업데이트
        function updateStatus(data) {
            const statusIndicator = document.getElementById('status-indicator');
            const statusText = document.getElementById('status-text');
            
            if (data.is_running && !data.is_paused) {
                statusIndicator.className = 'status-item running';
                statusText.textContent = '실행중';
            } else if (data.is_paused) {
                statusIndicator.className = 'status-item paused';
                statusText.textContent = '일시정지';
            } else {
                statusIndicator.className = 'status-item stopped';
                statusText.textContent = '중지됨';
            }

            document.getElementById('total-balance').textContent = 
                '₩' + Math.round(data.total_balance).toLocaleString();
            
            const dailyPnl = (data.daily_pnl * 100).toFixed(2) + '%';
            const dailyPnlEl = document.getElementById('daily-pnl');
            dailyPnlEl.textContent = dailyPnl;
            dailyPnlEl.className = data.daily_pnl >= 0 ? 'positive' : 'negative';
            
            document.getElementById('positions-count').textContent = data.positions;
            document.getElementById('daily-trades').textContent = data.daily_trades;
            
            // 포지션 목록 업데이트
            const positionsContent = document.getElementById('positions-content');
            if (data.position_details && Object.keys(data.position_details).length > 0) {
                positionsContent.innerHTML = Object.entries(data.position_details)
                    .map(([symbol, pos]) => 
                        `<div class="position-item">${symbol}: ₩${Math.round(pos.amount).toLocaleString()}</div>`
                    ).join('');
            } else {
                positionsContent.innerHTML = '포지션이 없습니다';
            }
        }

        // 로그 업데이트
        function updateLogs(logs) {
            const container = document.getElementById('logs-container');
            container.innerHTML = logs.slice(0, 20).map(log => {
                const levelClass = `log-${log.level.toLowerCase()}`;
                const time = new Date(log.timestamp).toLocaleTimeString();
                return `<div class="log-item ${levelClass}">[${time}] ${log.module}: ${log.message}</div>`;
            }).join('');
        }

        // API 호출 함수들
        async function startTrading() {
            try {
                const response = await fetch('/api/start', { method: 'POST' });
                const result = await response.json();
                if (result.success) {
                    alert('거래가 시작되었습니다!');
                } else {
                    alert('거래 시작 실패: ' + (result.error || '알 수 없는 오류'));
                }
            } catch (error) {
                alert('오류: ' + error.message);
            }
        }

        async function stopTrading() {
            if (!confirm('거래를 중지하시겠습니까?')) return;
            
            try {
                const response = await fetch('/api/stop', { method: 'POST' });
                const result = await response.json();
                if (result.success) {
                    alert('거래가 중지되었습니다.');
                } else {
                    alert('거래 중지 실패: ' + (result.error || '알 수 없는 오류'));
                }
            } catch (error) {
                alert('오류: ' + error.message);
            }
        }

        async function pauseTrading() {
            try {
                const response = await fetch('/api/pause', { method: 'POST' });
                const result = await response.json();
                if (result.success) {
                    alert('거래가 일시정지되었습니다.');
                }
            } catch (error) {
                alert('오류: ' + error.message);
            }
        }

        async function resumeTrading() {
            try {
                const response = await fetch('/api/resume', { method: 'POST' });
                const result = await response.json();
                if (result.success) {
                    alert('거래가 재개되었습니다.');
                }
            } catch (error) {
                alert('오류: ' + error.message);
            }
        }

        async function emergencySell() {
            if (!confirm('정말로 모든 포지션을 긴급 매도하시겠습니까?')) return;
            
            try {
                const response = await fetch('/api/emergency_sell', { method: 'POST' });
                const result = await response.json();
                if (result.success) {
                    alert('긴급 매도가 완료되었습니다.');
                } else {
                    alert('긴급 매도 실패: ' + (result.error || '알 수 없는 오류'));
                }
            } catch (error) {
                alert('오류: ' + error.message);
            }
        }

        async function requestClaudeAnalysis() {
            try {
                document.getElementById('claude-result').innerHTML = 'Claude 분석 중...';
                
                const response = await fetch('/api/claude/manual_analysis', { method: 'POST' });
                const result = await response.json();
                
                if (result.error) {
                    document.getElementById('claude-result').innerHTML = '오류: ' + result.error;
                } else {
                    const analysisHtml = `
                        <div style="margin-top: 10px;">
                            <strong>추천:</strong> ${result.recommendation}<br>
                            <strong>신뢰도:</strong> ${(result.confidence * 100).toFixed(1)}%<br>
                            <strong>이유:</strong> ${result.reasoning}<br>
                            <strong>제안사항:</strong><br>
                            ${result.suggested_actions.map(action => `• ${action}`).join('<br>')}
                        </div>
                    `;
                    document.getElementById('claude-result').innerHTML = analysisHtml;
                }
            } catch (error) {
                document.getElementById('claude-result').innerHTML = '오류: ' + error.message;
            }
        }

        async function saveTelegramSettings() {
            const token = document.getElementById('telegram-token').value;
            const chatId = document.getElementById('telegram-chat-id').value;
            
            if (!token || !chatId) {
                alert('봇 토큰과 채팅 ID를 모두 입력해주세요.');
                return;
            }
            
            try {
                const response = await fetch('/api/telegram/set', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ token, chat_id: chatId })
                });
                
                const result = await response.json();
                if (result.success) {
                    alert('텔레그램 설정이 저장되었습니다.');
                } else {
                    alert('설정 저장 실패: ' + (result.error || '알 수 없는 오류'));
                }
            } catch (error) {
                alert('오류: ' + error.message);
            }
        }

        // 초기 데이터 로드
        socket.emit('request_status');
        socket.emit('request_logs', { limit: 20 });
        
        // 주기적으로 로그 업데이트
        setInterval(() => {
            socket.emit('request_logs', { limit: 20 });
        }, 10000);
    </script>
</body>
</html>
        '''
    
    def run(self, host='0.0.0.0', port=5000, debug=False):
        """웹 서버 실행"""
        self.socketio.run(self.app, host=host, port=port, debug=debug)