#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
업비트 API 진단 도구
"""

import pyupbit
from config import APIConfig

def test_api_connection():
    """API 연결 및 응답 구조 테스트"""
    
    print("=" * 50)
    print("업비트 API 진단 시작")
    print("=" * 50)
    
    try:
        # API 키 로드
        api_config = APIConfig()
        access_key, secret_key = api_config.get_upbit_keys()
        
        print(f"Access Key: {access_key[:10]}...")
        print(f"Secret Key: {secret_key[:10]}...")
        
        # Upbit 인스턴스 생성
        upbit = pyupbit.Upbit(access=access_key, secret=secret_key)
        print("✅ Upbit 인스턴스 생성 성공")
        
    except Exception as e:
        print(f"❌ Upbit 인스턴스 생성 실패: {e}")
        return False
    
    # 1. get_balances() 테스트
    print("\n1. get_balances() 테스트:")
    try:
        balances = upbit.get_balances()
        print(f"   타입: {type(balances)}")
        print(f"   내용: {balances}")
        
        if isinstance(balances, list):
            print(f"   리스트 길이: {len(balances)}")
            if balances:
                print(f"   첫 번째 아이템: {balances[0]}")
                for item in balances:
                    if isinstance(item, dict) and item.get('currency') == 'KRW':
                        print(f"   KRW 발견: {item}")
        elif isinstance(balances, dict):
            print(f"   딕셔너리 키들: {list(balances.keys())}")
            for key, value in balances.items():
                print(f"   {key}: {value}")
        else:
            print(f"   예상하지 못한 타입: {type(balances)}")
            
    except Exception as e:
        print(f"   ❌ get_balances() 오류: {e}")
    
    # 2. get_balance("KRW") 테스트
    print("\n2. get_balance('KRW') 테스트:")
    try:
        krw_balance = upbit.get_balance("KRW")
        print(f"   결과: {krw_balance}")
        print(f"   타입: {type(krw_balance)}")
        
        if krw_balance is not None:
            try:
                krw_float = float(krw_balance)
                print(f"   숫자 변환: ₩{krw_float:,.0f}")
            except:
                print(f"   숫자 변환 실패")
        
    except Exception as e:
        print(f"   ❌ get_balance('KRW') 오류: {e}")
    
    # 3. 계정 정보 테스트
    print("\n3. 계정 정보 테스트:")
    try:
        # pyupbit의 내부 메서드 직접 호출
        import jwt
        import hashlib
        import os
        import requests
        import uuid
        from urllib.parse import urlencode
        
        server_url = "https://api.upbit.com"
        
        payload = {
            'access_key': access_key,
            'nonce': str(uuid.uuid4()),
        }
        
        jwt_token = jwt.encode(payload, secret_key, algorithm='HS256')
        authorize_token = 'Bearer {}'.format(jwt_token)
        headers = {"Authorization": authorize_token}
        
        res = requests.get(server_url + "/v1/accounts", headers=headers)
        
        print(f"   HTTP 상태: {res.status_code}")
        print(f"   응답 내용: {res.text[:200]}...")
        
        if res.status_code == 200:
            account_data = res.json()
            print(f"   JSON 파싱 성공")
            print(f"   응답 타입: {type(account_data)}")
            print(f"   응답 구조: {account_data}")
            
            # KRW 찾기
            for account in account_data:
                if account.get('currency') == 'KRW':
                    balance = account.get('balance', '0')
                    print(f"   ✅ KRW 계정 발견: {balance}")
                    
        else:
            print(f"   ❌ API 오류: {res.status_code}")
            print(f"   오류 내용: {res.text}")
            
    except Exception as e:
        print(f"   ❌ 직접 API 호출 오류: {e}")
    
    # 4. 현재 가격 테스트 (인증 불필요)
    print("\n4. 현재 가격 테스트:")
    try:
        btc_price = pyupbit.get_current_price("KRW-BTC")
        print(f"   BTC 가격: ₩{btc_price:,.0f}")
        
    except Exception as e:
        print(f"   ❌ 가격 조회 오류: {e}")
    
    print("\n" + "=" * 50)
    print("진단 완료")
    print("=" * 50)

if __name__ == "__main__":
    test_api_connection()