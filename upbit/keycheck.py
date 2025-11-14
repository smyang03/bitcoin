import jwt
import uuid
import hashlib
import requests
from urllib.parse import urlencode
import pyupbit


# 발급받은 키 입력
ACCESS_KEY = "DqHAiYdOQmoxjYJgp8MhP720ITetfqNl38oep15o"
SECRET_KEY = "C3mQRe42CoBjL1iSvTfcNial2zB5S97Kjg5hQbsV"

upbit = pyupbit.Upbit(access=ACCESS_KEY, secret=SECRET_KEY)
print(upbit.get_balances())
# # JWT 토큰 생성
# payload = {
#     'access_key': ACCESS_KEY,
#     'nonce': str(uuid.uuid4()),
# }
# jwt_token = jwt.encode(payload, SECRET_KEY, algorithm='HS256')
# authorization = f'Bearer {jwt_token}'
# headers = {"Authorization": authorization}

# # 계좌 정보 조회 (조회 권한만 있어도 가능)
# url = "https://api.upbit.com/v1/accounts"
# res = requests.get(url, headers=headers)

# if res.status_code == 200:
#     print("✅ API Key 정상:", res.json())
# else:
#     print("❌ 오류 발생:", res.status_code, res.text)
