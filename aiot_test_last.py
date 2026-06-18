import cv2                                                                      # OpenCV 라이브러리: 웹캠 영상을 받아오고 화면에 창을 띄울 때 사용
import asyncio                                                                  # 비동기 라이브러리: 텔레그램 메시지를 보낼 때 화면이 멈추는 것을 방지
import telegram                                                                 # 텔레그램 라이브러리: 라즈베리파이에서 스마트폰으로 알림을 보낼 때 사용
import time                                                                     # 시간 라이브러리: 로그에 찍힐 현재 시간 계산 및 중복 방지 대기용
import threading                                                                # 멀티스레딩 라이브러리: 웹캠 연산과 대시보드 화면 연산을 분리해 가동
import tkinter as tk                                                            # GUI 라이브러리: 모니터에 로그를 보여줄 텍스트 대시보드 창 제작용
from tkinter import scrolledtext                                                # 스크롤 텍스트 위젯: 로그가 아래로 길어질 때 스크롤바를 자동으로 생성
from pyzbar import pyzbar                                                       # pyzbar 라이브러리: 웹캠 프레임 안에서 QR 코드를 찾아내고 글자를 추출

API_TOKEN = '8616454904:AAH**********************'                              # 텔레그램 봇 토큰 번호 설정
CHAT_ID = '8424******'                                                          # 텔레그램 고유 ID 번호 설정
bot = telegram.Bot(token=API_TOKEN)                                             # 텔레그램 봇 원격 제어 객체 생성

# 등록된 사용자 데이터베이스
REGISTERED_USERS = {                                                            # 출입이 허용된 정식 사용자 명단을 딕셔너리 형태로 등록
    "202378211": "박세현",                                                      # [QR 코드 안의 학번 : 매칭할 학생 이름] - 정식 등록된 데이터
    "202300001": "홍길동",                                                      # [QR 코드 안의 학번 : 매칭할 학생 이름] - 테스트용 가상 데이터 1
    "test_admin": "관리자"                                                      # [QR 코드 안의 학번 : 매칭할 학생 이름] - 테스트용 가상 데이터 2
}                                                                               # 사용자 데이터베이스 등록 완료

# 중복 알림 발송 방지를 위한 최근 인식 기록
last_scanned = {}                                                               # QR 코드가 카메라 앞에 머물 때 알림이 계속 가는 것을 막는 저장소
COOL_DOWN_TIME = 5                                                              # 중복 방지 시간 설정 (동일한 사람은 5초가 지나야 다시 알림을 보냄)

# 전역 변수
gui_logs = []                                                                   # 카메라 스레드에서 만든 안내 문구를 대시보드 스레드로 넘겨주는 리스트
system_running = True                                                           # 전체 프로그램이 현재 정상적으로 가동 중인지 체크하는 스위치 변수

async def send_telegram_msg(text):                                              # 텔레그램 서버로 메시지를 전송하는 실제 비동기 함수 정의
    """텔레그램으로 메시지를 전송하는 비동기 함수"""                            # 함수의 역할을 기록해두는 안내문
    try:                                                                        # 인터넷 끊김이나 봇 차단 등 전송 에러가 날 수 있으므로 예외처리 시작
        await bot.send_message(chat_id=CHAT_ID, text=text)                      # 비동기 대기(await) 방식을 사용해 스마트폰으로 실시간 알림 전송
    except Exception as e:                                                      # 메시지 전송 중에 에러가 발생한 경우 예외 캐치
        print(f"텔레그램 전송 실패: {e}")                                       # 콘솔 터미널 화면에 구체적인 전송 실패 원인을 출력하여 디버깅 지원

def add_log(message):                                                           # 대시보드 화면과 터미널에 시간 정보와 안내 문구를 뿌려주는 함수
    """타임스탬프와 함께 GUI 창 및 터미널에 로그를 추가하는 함수"""             # 함수의 역할을 기록해두는 안내문
    timestamp = time.strftime('%H:%M:%S')                                       # 현재 시스템 시간을 '시:분:초' 문자열 형태로 가져옴
    full_message = f"[{timestamp}] {message}"                                   # 시간 정보와 전달받은 본문 메시지를 대괄호 포맷으로 결합
    gui_logs.append(full_message)                                               # 대시보드 화면을 갱신하기 위해 전역 로그 리스트에 메시지 추가
    print(full_message)                                                         # 디버깅용으로 라즈베리파이 검은색 터미널 창에도 동일하게 출력

def camera_and_logic_thread():                                                  # 웹캠 영상을 읽어오고 QR 코드를 분석하는 메인 핵심 함수 정의
    """웹캠 영상 처리 및 고성능 QR 비즈니스 로직을 담당하는 서브 스레드"""      # 함수의 역할을 기록해두는 안내문
    global system_running                                                       # 프로그램 종료 시 이 함수도 같이 멈추도록 전역 변수 가져오기
   
    # 웹캠 설정 (기본 카메라 0번 사용)
    camera = cv2.VideoCapture(0, cv2.CAP_V4L2)                                  # 라즈베리파이 5 시스템에 연결된 0번 USB 웹캠 장치 활성화
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)                                   # 화면 왜곡과 끊김을 줄이기 위해 카메라 가로 해상도를 640으로 지정
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)                                  # 화면 왜곡과 끊김을 줄이기 위해 카메라 세로 해상도를 480으로 지정
   
    time.sleep(1.0)                                                             # 웹캠 하드웨어가 켜진 후 화질과 초점을 맞추도록 1초 동안 대기
   
    if not camera.isOpened():                                                   # 카메라 선이 뽑혀있거나 장치 인식에 실패해 열리지 않은 경우 검사
        add_log(" 카메라이동 실패! VideoCapture(0)을 열 수 없습니다.")          # 대시보드 로그 창에 카메라 연결 에러 문구 출력
        system_running = False                                                  # 프로그램 가동 스위치를 꺼서 전체 시스템 종료 프로세스 작동
        return                                                                  # 카메라이동 실패 시 이후 코드를 실행하지 않고 함수 즉시 탈출

    window_name = "Smart Access Control Window"                                 # 모니터 화면에 따로 띄울 독립된 웹캠 비디오 창의 타이틀 이름 정의
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)                             # 라즈베리파이 5 그래픽 서버 환경에 맞는 정상적인 비디오 창 생성
    cv2.resizeWindow(window_name, 640, 480)                                     # 팝업되는 독립 웹캠 비디오 창의 초기 크기를 640x480 크기로 조절

    # 비동기 루프 획득
    try:                                                                        # 파이썬 최신 버전에 호환되도록 비동기 이벤트 루프 설정 시작
        loop = asyncio.get_running_loop()                                       # 현재 실행 중인 스레드에 이미 만들어진 비동기 루프가 있는지 확인
    except RuntimeError:                                                        # 백그라운드 스레드 특성상 루프가 아직 생성되지 않아 에러가 나면 캐치
        loop = asyncio.new_event_loop()                                         # 텔레그램 전송을 위해 이 스레드 전용의 비동기 이벤트 루프 새로 생성
        asyncio.set_event_loop(loop)                                            # 새로 만든 비동기 이벤트 루프를 현재 실행 환경에 메인으로 등록

    add_log(" 고성능 QR 스마트 출입 통제 시스템 가동.")                         # 대시보드 창에 시스템이 정상 가동되었다는 첫 안내 로그 추가
    add_log(" 웹캠 창이 켜졌습니다. QR 코드를 카메라에 비춰주세요.")            # 대시보드 창에 카메라 창이 정상적으로 활성화되었음을 기록

    while camera.isOpened() and system_running:                                 # 웹캠이 잘 연결되어 있고 가동 스위치가 켜져 있는 동안 계속 반복
        success, frame = camera.read()                                          # 웹캠으로부터 실시간 영상 이미지 프레임을 1장씩 계속 읽어옴
        if not success:                                                         # 카메라 연결선이 도중에 빠지는 등 이미지를 읽어오지 못한 경우
            break                                                               # 비디오 분석 루프를 중단하고 자원 해제 코드로 탈출

        # pyzbar를 이용해 프레임에서 모든 QR 코드 검출 (흑백 변환 없이도 강력하게 인식 가능)
        barcodes = pyzbar.decode(frame)                                         # 받아온 프레임 안에서 QR 코드 패턴이 있는지 분석해 결과 리스트 반환

        for barcode in barcodes:                                                # 현재 화면에서 발견된 QR 코드들을 하나씩 꺼내어 순차적으로 처리
            # 바코드/QR 데이터 추출 및 문자열 변환
            data = barcode.data.decode("utf-8").strip()                         # QR 내부의 바이트 코드를 일반 텍스트 문자로 바꾸고 양끝 공백 제거
           
            if data:                                                            # QR 코드에서 읽어낸 학번 텍스트 내용물이 유효하게 존재하는 경우
                current_time = time.time()                                      # 알림 도배를 막기 위해 현재 컴퓨터 내부의 절대 시간초 구하기
               
                # 5초 중복 방지 로직
                if data not in last_scanned or (current_time - last_scanned[data] > COOL_DOWN_TIME): # 처음 찍힌 QR이거나 5초 제한시간이 지난 상태라면
                    last_scanned[data] = current_time                           # 알림 폭탄을 막기 위해 현재 해당 사용자의 최종 인식 시간 업데이트
                   
                    if data in REGISTERED_USERS:                                # 읽어온 학번 텍스트가 명단 데이터베이스 안에 들어있는 경우 (승인)
                        user_name = REGISTERED_USERS[data]                      # 명단 딕셔너리에서 학번에 매칭된 실제 학생 이름을 조회하여 저장
                        display_text = f"{user_name} Enter Success"             # 비디오 화면 창 위에 합성할 승인 영문 텍스트 포맷 설정
                        msg_text = f" [출근] {user_name} 학생이 입실했습니다."  # 대시보드 창과 스마트폰 텔레그램으로 보낼 공식 출근 문구 작성
                        color = (0, 255, 0)                                     # 비디오 창의 사각형 박스와 글자 색상을 초록색(BGR)으로 지정
                    else:                                                       # 읽어온 학번이 허가되지 않은 외부 미등록 데이터인 경우 (경고)
                        display_text = "WARNING: Unregistered QR"               # 비디오 화면 창 위에 합성할 비인가 경고 영문 텍스트 설정
                        msg_text = f" [경고] 미등록 QR 접근 감지! (ID: {data})" # 보안 경고 로그 문구와 인식된 미등록 텍스트 데이터 결합
                        color = (0, 0, 255)                                     # 비디오 창의 사각형 박스와 글자 색상을 빨간색(BGR)으로 지정

                    # 텔레그램 발송 및 로그 출력
                    loop.run_until_complete(send_telegram_msg(msg_text))        # 텔레그램 메시지 전송 비동기 함수를 실행하고 끝날 때까지 대기 호출
                    add_log(msg_text)                                           # 완성된 승인 또는 경고 메시지를 실시간 GUI 대시보드 창에 반영

                # QR 코드 위치에 사각형 박스 그리기 설정 (pyzbar에서 가져온 좌표 활용)
                (x, y, w, h) = barcode.rect                                     # pyzbar가 화면 속에서 찾아낸 QR 코드의 네 모퉁이 위치 좌표 획득
                cv2.rectangle(frame, (x, y), (x + w, y + h), color, 3)          # 영상 화면의 QR 코드 테두리 주위에 두께 3짜리 사각형 박스 드로잉
               
                # 사각형 위에 결과 텍스트 출력
                cv2.putText(frame, display_text, (x, y - 10),                   # 사각형 상단 테두리에서 약간 윗부분에 글자가 들어가도록 위치 지정
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)            # 폰트 종류, 크기 0.6배, 지정한 색상, 글자 두께 2 스펙으로 화면에 합성

        # 개별 웹캠 GUI 창에 영상 출력
        cv2.imshow(window_name, frame)                                          # 박스와 글자가 실시간으로 합성된 최종 이미지 프레임을 비디오 창에 투사

        # 'q' 키 입력 시 종료
        if cv2.waitKey(1) & 0xFF == ord('q'):                                   # 비디오 창을 마우스로 클릭하고 키보드 'q' 키를 누른 상황 감지 시
            add_log(" 사용자가 'q' 키를 눌러 종료합니다.")                      # 시스템 완전 종료 절차가 시작되었음을 대시보드 로그 창에 전송
            break                                                               # 실시간 카메라 무한루프를 탈출하여 하드웨어 정리 블록으로 이동

    camera.release()                                                            # 사용을 마친 라즈베리파이 USB 웹캠 카메라 하드웨어 자원 연결 해제
    cv2.destroyAllWindows()                                                     # 컴퓨터 비전 라이브러리(OpenCV)가 생성했던 모든 비디오 창 강제 파기
    system_running = False                                                      # 시스템 가동 플래그를 꺼서 옆에 켜진 텍스트 대시보드 창도 같이 꺼지도록 함

def update_gui_logs(log_area, root):                                            # 카메라 쪽에서 보내주는 실시간 안내 로그를 대시보드 창에 그려주는 함수
    """tkinter 창에 주기적으로 로그 리스트를 반영하는 함수"""                   # 함수의 역할을 기록해두는 안내문
    global system_running                                                       # 메인 카메라 시스템의 종료 신호를 실시간 추적하기 위해 전역 변수 공유
    if not system_running:                                                      # 핵심 카메라 영상 처리 시스템의 스위치가 꺼진 상태(False)라면
        root.destroy()                                                          # 모니터 화면에 표시 중이던 텍스트 대시보드 창을 메모리에서 삭제
        return                                                                  # 대시보드 화면 갱신 백그라운드 타이머 함수를 종료하고 제어권 반환

    while gui_logs:                                                             # 아직 대시보드 화면에 출력되지 않은 신규 로그 문구가 리스트에 쌓여있는 동안
        log_msg = gui_logs.pop(0)                                               # 리스트의 맨 앞(0번)에 위치한 가장 먼저 들어온 로그 문구를 선입선출 인출
        log_area.configure(state='normal')                                      # 잠금 처리된 대시보드 텍스트 영역을 잠시 편집 가능한 상태로 활성화
        log_area.insert(tk.END, log_msg + "\n")                                 # 대시보드 텍스트 박스 맨 마지막 줄 아래에 새로운 로그 문구 한 줄 삽입
        log_area.configure(state='disabled')                                    # 사용자가 임의로 마우스나 키보드로 로그를 지우거나 쓰지 못하게 편집 잠금
        log_area.yview(tk.END)                                                  # 새 로그가 추가되면 화면이 자동으로 최하단으로 내려가도록 스크롤 이동
   
    root.after(100, update_gui_logs, log_area, root)                            # 100밀리초(0.1초) 주기로 이 화면 갱신 함수가 계속 자동 실행되도록 타이머 등록

def build_gui():                                                                # 대시보드 프로그램의 화면 구성요소(라벨, 텍스트 창 등)를 디자인하는 함수
    """텍스트 안내 문구들을 띄워줄 별개의 모니터링 GUI 창 생성"""               # 함수의 역할을 기록해두는 안내문
    root = tk.Tk()                                                              # tkinter GUI 프레임워크의 메인 최상위 윈도우 바탕 창 인스턴스 초기화
    root.title("System Access Monitor Dashboard")                               # 팝업되는 대시보드 윈도우 프로그램 좌측 상단 바에 표시될 프로그램 타이틀 설정
    root.geometry("550x400")                                                    # 대시보드 안내 창의 기본 레이아웃 가로 크기 550, 세로 크기 400으로 할당
    root.resizable(False, False)                                                # 실제 출입 통제 단말기 기기 느낌을 주기 위해 사용자의 임의 창 크기 조절 금지

    title_label = tk.Label(root, text=" 실시간 출입 통제 현황 대시보드", font=("Helvetica", 14, "bold")) # 상단 대시보드 메인 타이틀 글자 위젯 생성
    title_label.pack(pady=10)                                                   # 상하 여백 공간을 10픽셀씩 준 상태로 대시보드 창 맨 위 중심에 글자 배치

    log_area = scrolledtext.ScrolledText(root, width=60, height=18, font=("Consolas", 10)) # 가로 60칸, 세로 18줄 크기의 스크롤 로그 출력 영역 위젯 생성
    log_area.configure(state='disabled')                                        # 대시보드에 뿌려진 텍스트 데이터 로그를 마우스 드래그나 타자로 수정 불가능하게 설정
    log_area.pack(pady=5)                                                       # 주변 상하 여백 공간을 5픽셀 할당하여 대시보드 중앙 영역에 위젯 조립 배치

    add_log(" 메인 시스템 엔진 초기화 중...")                                   # 프로그램 가동 시작을 알리는 첫 로그 메시지를 생성하여 큐 리스트에 삽입

    # 백그라운드 스레드로 카메라 로직 가동
    cam_thread = threading.Thread(target=camera_and_logic_thread, daemon=True)  # 메인 GUI 창과 카메라 영상 연산이 겹쳐서 멈추지 않도록 카메라 전용 독립 스레드 생성
    cam_thread.start()                                                          # 메인 GUI 프레임워크와 병렬로 동시에 실행되도록 카메라 스레드 시동

    root.after(100, update_gui_logs, log_area, root)                            # GUI 대시보드 창이 켜지자마자 0.1초 뒤부터 주기적인 화면 로그 갱신 타이머 가동
    root.mainloop()                                                             # 제작한 대시보드 GUI 창이 모니터에서 꺼지지 않고 유지되도록 메인 루프 가동

if __name__ == "__main__":                                                      # 파이썬 내부에서 다른 파일에 호출된 게 아니라 이 파일을 직접 실행했는지 체크
    build_gui()                                                                 # 직접 가동 시 최종 완성된 대시보드 빌드 및 카메라 연동 스레드 작동 통합 함수 가동
