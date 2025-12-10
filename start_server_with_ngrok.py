"""
uvicorn 서버와 ngrok을 자동으로 실행하고 ngrok URL을 브라우저에서 여는 스크립트
"""
import subprocess
import time
import webbrowser
import requests
import sys
import os

def check_ngrok_authtoken():
    """ngrok authtoken이 설정되어 있는지 확인하고, 없으면 입력받아 설정"""
    print("🔍 ngrok authtoken 확인 중...")
    try:
        # ngrok config check로 authtoken 확인
        result = subprocess.run(
            ["ngrok", "config", "check"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5
        )
        
        # stderr에 authtoken 관련 에러가 없으면 설정되어 있는 것으로 간주
        output = (result.stdout + result.stderr).lower()
        if "authtoken" in output and ("not found" in output or "missing" in output or "required" in output):
            # authtoken이 설정되어 있지 않음
            pass
        else:
            # authtoken이 설정되어 있음
            print("✅ ngrok authtoken이 이미 설정되어 있습니다.")
            return True
    except FileNotFoundError:
        print("❌ ngrok이 설치되어 있지 않거나 PATH에 없습니다.")
        print("💡 ngrok을 설치하고 PATH에 추가해주세요.")
        return False
    except (subprocess.TimeoutExpired, Exception) as e:
        # 확인 실패 시에도 진행 (이미 설정되어 있을 수 있음)
        print("⚠️  ngrok authtoken 확인 중 오류가 발생했습니다. 계속 진행합니다...")
        return True
    
    # authtoken이 설정되어 있지 않으면 입력받기
    print("⚠️  ngrok authtoken이 설정되어 있지 않습니다.")
    print("💡 ngrok authtoken은 https://dashboard.ngrok.com/get-started/your-authtoken 에서 확인할 수 있습니다.")
    print()
    
    while True:
        authtoken = input("ngrok authtoken을 입력하세요: ").strip()
        if not authtoken:
            print("❌ authtoken을 입력해주세요.")
            continue
        
        # authtoken 설정 시도
        try:
            result = subprocess.run(
                ["ngrok", "config", "authtoken", authtoken],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                print("✅ ngrok authtoken이 성공적으로 설정되었습니다!")
                return True
            else:
                error_msg = result.stderr.strip() or result.stdout.strip()
                print(f"❌ authtoken 설정 실패: {error_msg}")
                retry = input("다시 시도하시겠습니까? (y/n): ").strip().lower()
                if retry != 'y':
                    return False
        except Exception as e:
            print(f"❌ 오류 발생: {e}")
            retry = input("다시 시도하시겠습니까? (y/n): ").strip().lower()
            if retry != 'y':
                return False

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
    
    # 0. ngrok authtoken 확인 및 설정
    if not check_ngrok_authtoken():
        print("❌ ngrok authtoken 설정에 실패했습니다. 프로그램을 종료합니다.")
        sys.exit(1)
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

