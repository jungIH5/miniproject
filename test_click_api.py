import requests

res = requests.post("http://localhost:5000/api/click-log", json={
    "product_name": "Test Product",
    "product_link": "http://naver.com"
})
print("Status Code:", res.status_code)
print("Response:", res.text)
