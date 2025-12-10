"""
uvicorn 서버와 ngrok을 자동으로 실행하고 ngrok URL을 브라우저에서 여는 스크립트
"""
import subprocess
import time
import webbrowser
import requests
import sys
import os

def start_uvicorn():
    """uvicorn 서버를 백그라운드로 시작"""
    print("🚀 uvicorn 서버 시작 중...")
    # Windows에서는 CREATE_NEW_CONSOLE 플래그로 새 창에서 실행
    subprocess.Popen(
        ["uvicorn", "backend.main:app", "--host", "localhost", "--port", "8000"],
        creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0
    )
    print("✅ uvicorn 서버가 시작되었습니다 (포트 8000)")
    time.sleep(3)  # 서버 시작 대기

def start_ngrok():
    """ngrok을 시작하고 URL을 추출"""
    print("🌐 ngrok 시작 중...")
    # ngrok을 새 창에서 실행
    ngrok_process = subprocess.Popen(
        ["ngrok", "http", "8000"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0
    )
    
    # ngrok이 시작될 때까지 대기
    time.sleep(5)
    
    # ngrok API를 통해 터널 URL 가져오기
    max_retries = 10
    for i in range(max_retries):
        try:
            response = requests.get("http://127.0.0.1:4040/api/tunnels", timeout=2)
            if response.status_code == 200:
                data = response.json()
                tunnels = data.get("tunnels", [])
                if tunnels:
                    public_url = tunnels[0].get("public_url")
                    if public_url:
                        print(f"✅ ngrok 터널 생성 완료!")
                        print(f"🌍 Public URL: {public_url}")
                        return public_url
            time.sleep(1)
        except requests.exceptions.RequestException:
            time.sleep(1)
    
    print("⚠️  ngrok API에서 URL을 가져올 수 없습니다. 수동으로 확인해주세요.")
    return None

def open_browser(url):
    """브라우저에서 URL 열기"""
    if url:
        print(f"🔗 브라우저에서 {url} 열기...")
        webbrowser.open(url)
        print("✅ 브라우저가 열렸습니다!")
    else:
        print("❌ URL을 가져올 수 없어 브라우저를 열 수 없습니다.")

def main():
    """메인 실행 함수"""
    print("=" * 60)
    print("HS Code 분류 시스템 서버 시작")
    print("=" * 60)
    print()
    
    # 1. uvicorn 서버 시작
    start_uvicorn()
    
    # 2. ngrok 시작 및 URL 추출
    ngrok_url = start_ngrok()
    
    # 3. 브라우저에서 URL 열기
    if ngrok_url:
        open_browser(ngrok_url)
    
    print()
    print("=" * 60)
    print("서버가 실행 중입니다.")
    print("종료하려면 각 터미널 창을 닫으세요.")
    print("=" * 60)
    print()
    print("💡 ngrok 웹 인터페이스: http://127.0.0.1:4040")
    print("💡 로컬 서버: http://localhost:8000")
    if ngrok_url:
        print(f"💡 Public URL: {ngrok_url}")
    
    # 스크립트는 계속 실행되도록 대기
    try:
        input("\n종료하려면 Enter를 누르세요...")
    except KeyboardInterrupt:
        print("\n\n프로그램을 종료합니다.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n프로그램을 종료합니다.")
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        sys.exit(1)

