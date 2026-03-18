#!/usr/bin/env python3
"""
Pomodoro Timer CLI
25-min work / 5-min break / 15-min long break after every 4 sessions
No external dependencies required.
"""

import sys
import time
import os
import signal
from datetime import datetime

# ── Terminal helpers ──────────────────────────────────────────────────────────

def clear_line():
    sys.stdout.write("\r\033[K")
    sys.stdout.flush()

def bell():
    """Ring terminal bell and print a visible alert."""
    sys.stdout.write("\a")
    sys.stdout.flush()

def color(text, code):
    """Wrap text in an ANSI color code (no-op if not a TTY)."""
    if not sys.stdout.isatty():
        return text
    return f"\033[{code}m{text}\033[0m"

def bold(text):    return color(text, "1")
def red(text):     return color(text, "31")
def green(text):   return color(text, "32")
def yellow(text):  return color(text, "33")
def cyan(text):    return color(text, "36")
def magenta(text): return color(text, "35")

def print_header():
    os.system("clear" if os.name == "posix" else "cls")
    print(bold(cyan("╔══════════════════════════════════╗")))
    print(bold(cyan("║       🍅  Pomodoro Timer          ║")))
    print(bold(cyan("╚══════════════════════════════════╝")))

def fmt_time(seconds):
    m, s = divmod(max(0, seconds), 60)
    return f"{m:02d}:{s:02d}"

# ── Session logging ───────────────────────────────────────────────────────────

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sessions.log")

def log_session(session_type, duration_seconds):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    minutes = duration_seconds // 60
    with open(LOG_FILE, "a") as f:
        f.write(f"{now}  type={session_type:<10}  duration={minutes}min\n")

# ── Countdown ─────────────────────────────────────────────────────────────────

class SessionSkipped(Exception):
    pass

class SessionQuit(Exception):
    pass

def run_countdown(label, total_seconds, bar_color_fn):
    """
    Display a live countdown for *total_seconds*.
    Returns True when finished normally, raises SessionSkipped / SessionQuit.
    Keypresses s=skip, q=quit are checked non-blockingly where possible.
    """
    # Try to set up non-blocking stdin for keypress detection
    use_tty = False
    old_settings = None
    try:
        import tty, termios
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        tty.setcbreak(fd)
        use_tty = True
    except Exception:
        pass

    import select

    start = time.time()
    elapsed = 0

    def restore():
        if use_tty and old_settings is not None:
            try:
                import termios
                termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_settings)
            except Exception:
                pass

    try:
        while elapsed < total_seconds:
            remaining = total_seconds - elapsed
            pct = elapsed / total_seconds
            bar_width = 30
            filled = int(pct * bar_width)
            bar = bar_color_fn("█" * filled) + "░" * (bar_width - filled)
            status = f"  {bold(label)}  [{bar}]  {bold(fmt_time(remaining))}  "
            clear_line()
            sys.stdout.write(status)
            sys.stdout.flush()

            # Non-blocking keypress check
            if use_tty:
                r, _, _ = select.select([sys.stdin], [], [], 1)
                if r:
                    ch = sys.stdin.read(1).lower()
                    if ch == "s":
                        print()
                        restore()
                        raise SessionSkipped()
                    elif ch == "q":
                        print()
                        restore()
                        raise SessionQuit()
            else:
                time.sleep(1)

            elapsed = int(time.time() - start)

        print()  # newline after progress bar
    except (SessionSkipped, SessionQuit):
        restore()
        raise
    except Exception:
        restore()
        raise
    finally:
        restore()

    return True

# ── Alert ─────────────────────────────────────────────────────────────────────

def alert(message):
    print()
    bell()
    print(bold(yellow("━" * 44)))
    print(bold(yellow(f"  {message}")))
    print(bold(yellow("━" * 44)))
    # Ring bell three times
    for _ in range(2):
        time.sleep(0.4)
        bell()
    time.sleep(1)

# ── Menu ──────────────────────────────────────────────────────────────────────

def show_menu(session_num, next_label):
    print()
    print(bold(f"  Session #{session_num}  →  {next_label}"))
    print()
    print(f"  {green('[s]')} Start")
    print(f"  {yellow('[k]')} Skip this session")
    print(f"  {red('[q]')} Quit")
    print()

def get_menu_choice():
    while True:
        try:
            ch = input("  Your choice: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return "q"
        if ch in ("s", "k", "q"):
            return ch
        print("  Please enter s, k, or q.")

# ── Session sequence ──────────────────────────────────────────────────────────

WORK_MINUTES = 25
SHORT_BREAK   = 5
LONG_BREAK    = 15
SESSIONS_BEFORE_LONG = 4

def session_label(work_count, is_work):
    if is_work:
        return f"Work session #{work_count + 1}"
    if (work_count % SESSIONS_BEFORE_LONG) == 0:
        return f"Long break ({LONG_BREAK} min)"
    return f"Short break ({SHORT_BREAK} min)"

def run():
    work_count = 0          # completed work sessions this cycle
    total_work  = 0         # all-time completed work sessions
    total_breaks = 0

    signal.signal(signal.SIGINT, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))

    print_header()
    print(f"\n  Log file: {LOG_FILE}\n")
    print("  During a session: press  s = skip,  q = quit\n")

    while True:
        is_work = True  # we always start with work
        label = f"Work #{total_work + 1}"
        duration = WORK_MINUTES * 60

        # ── Work session ──────────────────────────────────────────────
        show_menu(total_work + 1, f"Work session ({WORK_MINUTES} min)")
        choice = get_menu_choice()

        if choice == "q":
            print(bold(green("\n  Bye! Great work today.\n")))
            break
        if choice == "k":
            print(yellow("  Work session skipped.\n"))
            # still increment so break type is consistent
            work_count += 1
            total_work += 1
        else:
            print_header()
            print(f"\n  During session: s = skip   q = quit\n")
            try:
                run_countdown(label, duration, green)
                log_session("work", duration)
                work_count += 1
                total_work += 1
                alert(f"Work session #{total_work} complete! Time for a break.")
            except SessionSkipped:
                print(yellow("  Session skipped.\n"))
                work_count += 1
                total_work += 1
            except (SessionQuit, KeyboardInterrupt):
                print(bold(green("\n  Bye! Great work today.\n")))
                break

        # ── Break session ─────────────────────────────────────────────
        if (work_count % SESSIONS_BEFORE_LONG) == 0:
            break_duration = LONG_BREAK * 60
            break_label    = f"Long break #{work_count // SESSIONS_BEFORE_LONG}"
            break_type     = "long_break"
        else:
            break_duration = SHORT_BREAK * 60
            break_label    = f"Short break"
            break_type     = "short_break"

        show_menu(total_work, break_label)
        choice = get_menu_choice()

        if choice == "q":
            print(bold(green("\n  Bye! Great work today.\n")))
            break
        if choice == "k":
            print(yellow("  Break skipped.\n"))
            total_breaks += 1
        else:
            print_header()
            print(f"\n  During session: s = skip   q = quit\n")
            try:
                run_countdown(break_label, break_duration, magenta)
                log_session(break_type, break_duration)
                total_breaks += 1
                alert("Break over! Ready to focus?")
            except SessionSkipped:
                print(yellow("  Break skipped.\n"))
                total_breaks += 1
            except (SessionQuit, KeyboardInterrupt):
                print(bold(green("\n  Bye! Great work today.\n")))
                break

    # Summary
    print(bold(f"  Sessions completed: {total_work} work, {total_breaks} breaks"))
    print(f"  Log saved to: {LOG_FILE}\n")


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        print(bold(green("\n\n  Interrupted. Bye!\n")))
        sys.exit(0)
