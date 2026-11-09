import readline  # 讓 input() 可以正確刪除中文、日文，也能用方向鍵移動游標
from src.agent import new_session, run_turn


def main():
    session = new_session()
    print("=== Tango Coach 日文單字小考 ===")
    print("輸入「開始」或「考我第 6 課 3 題」來練習，輸入「結束」離開。")
    print(f"（這次的執行紀錄會存在 {session['trace_path']}）\n")

    while True:
        try:
            user_input = input("你：").strip()
        except (EOFError, KeyboardInterrupt):     # 按 Control + C 或 Control + D 也能離開
            break
        if user_input in ("結束", "exit", "quit"):
            break
        if not user_input:
            continue

        reply = run_turn(session, user_input)
        print(f"\nCoach：{reply}\n")

    print("掰掰，下次見！")


if __name__ == "__main__":
    main()