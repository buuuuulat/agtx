#!/usr/bin/env python3
"""
Мини-GUI для сбора датасета
- Только две кнопки: Старт/Стоп
- Показывает задание и таймер
- Автопоиск файла рекордера (datagrabber_69.py)
- Имя сборщика из переменной окружения OPERATOR_NAME → meta.json
- Рекордер запускается в отдельном процессе; мягкая остановка SIGINT→TERM→KILL
"""
from __future__ import annotations

import json
import os
import platform
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

import tkinter as tk
from tkinter import ttk, messagebox


# --------- Task providers (API или локальный список) ---------
@dataclass
class Task:
    task_id: str
    text: str


class TaskProvider:
    def get_next_task(self) -> Optional[Task]:
        raise NotImplementedError

    def submit_result(self, task_id: str, rec_id: str, meta: Dict[str, Any]) -> None:
        raise NotImplementedError


class HTTPTaskProvider(TaskProvider):
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def _http_get(self, path: str) -> Dict[str, Any]:
        import urllib.request
        url = f"{self.base_url}{path}"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = resp.read().decode("utf-8")
        return json.loads(data)

    def _http_post_json(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        import urllib.request
        url = f"{self.base_url}{path}"
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = resp.read().decode("utf-8")
        return json.loads(data) if data else {"ok": True}

    def get_next_task(self) -> Optional[Task]:
        try:
            data = self._http_get("/next_task")
            if not data or "text" not in data:
                return None
            return Task(task_id=str(data.get("task_id", "")), text=str(data["text"]))
        except Exception:
            return None

    def submit_result(self, task_id: str, rec_id: str, meta: Dict[str, Any]) -> None:
        payload = {"task_id": task_id, "rec_id": rec_id, "meta": meta}
        try:
            _ = self._http_post_json("/submit", payload)
        except Exception:
            pass


class LocalListTaskProvider(TaskProvider):
    def __init__(self, tasks: List[str]):
        self.tasks = [t for t in tasks if str(t).strip()]
        self.idx = 0

    def get_next_task(self) -> Optional[Task]:
        if self.idx >= len(self.tasks):
            return None
        t = self.tasks[self.idx]
        self.idx += 1
        return Task(task_id=f"local_{self.idx}", text=t)

    def submit_result(self, task_id: str, rec_id: str, meta: Dict[str, Any]) -> None:
        return


# ------------------- Мини-GUI -------------------
class App(tk.Tk):
    def __init__(self, provider: TaskProvider):
        super().__init__()
        self.title("Dataset Recorder")
        # компактное окно
        self.geometry("520x360")
        self.minsize(480, 320)

        self.provider = provider
        self.current_task: Optional[Task] = None
        self.rec_proc: Optional[subprocess.Popen] = None
        self.recording = False
        self.rec_start_time: Optional[float] = None
        self._timer_job = None

        # заранее вытащим имя оператора (в UI не показываем — минимум элементов)
        self.operator = self._detect_operator()

        # стили (зелёная/красная кнопки)
        self._init_styles()

        # UI
        self._build_ui()

        # первая задача
        self._fetch_and_show_next_task()

    # ---- цвета кнопок ----
    def _init_styles(self):
        self.style = ttk.Style(self)
        try:
            self.style.theme_use("clam")  # чтобы цвета применялись и на macOS
        except Exception:
            pass
        self.style.configure("Start.TButton", background="#22c55e", foreground="white",
                             padding=8, font=("SF Pro Text", 12, "bold"))
        self.style.map("Start.TButton",
                       background=[("active", "#16a34a"), ("disabled", "#86efac")],
                       foreground=[("disabled", "#ffffff")])

        self.style.configure("Stop.TButton", background="#ef4444", foreground="white",
                             padding=8, font=("SF Pro Text", 12, "bold"))
        self.style.map("Stop.TButton",
                       background=[("active", "#dc2626"), ("disabled", "#fca5a5")],
                       foreground=[("disabled", "#ffffff")])

    # ---- компоновка ----
    def _build_ui(self):
        # текст задания
        box = ttk.LabelFrame(self, text="Задание")
        box.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10, 6))
        self.task_text = tk.Text(box, height=6, wrap=tk.WORD)
        self.task_text.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        self.task_text.configure(state=tk.DISABLED)

        # статус + таймер
        status = ttk.Frame(self)
        status.pack(fill=tk.X, padx=10, pady=(4, 6))
        self.status_var = tk.StringVar(value="Готово")
        ttk.Label(status, textvariable=self.status_var).pack(side=tk.LEFT)
        self.timer_var = tk.StringVar(value="00:00")
        ttk.Label(status, text=" | ").pack(side=tk.LEFT)
        ttk.Label(status, text="Время:").pack(side=tk.LEFT)
        ttk.Label(status, textvariable=self.timer_var).pack(side=tk.LEFT)

        # две большие кнопки
        btns = ttk.Frame(self)
        btns.pack(fill=tk.X, padx=10, pady=(2, 10))
        self.btn_start = ttk.Button(btns, text="Начать запись", style="Start.TButton", command=self.on_start)
        self.btn_start.pack(side=tk.LEFT, expand=True, fill=tk.X)
        self.btn_finish = ttk.Button(btns, text="Завершить и отправить", style="Stop.TButton", command=self.on_finish)
        self.btn_finish.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(8, 0))
        self.btn_finish.configure(state=tk.DISABLED)

    # ---- задачи ----
    def _fetch_and_show_next_task(self):
        self.current_task = self.provider.get_next_task()
        self._set_task_text(self.current_task.text if self.current_task else "Задачи закончились. Спасибо!")
        self.btn_start.configure(state=tk.NORMAL if self.current_task else tk.DISABLED)

    def _set_task_text(self, text: str):
        self.task_text.configure(state=tk.NORMAL)
        self.task_text.delete("1.0", tk.END)
        self.task_text.insert(tk.END, text)
        self.task_text.configure(state=tk.DISABLED)

    # ---- старт/стоп ----
    def on_start(self):
        if self.recording or not self.current_task:
            return

        script_path = self._find_recorder_script()
        if not script_path:
            messagebox.showerror("Рекордер не найден",
                                 "Не найден файл рекордера: datagrabber_69.py (или задайте RECORDER_SCRIPT).")
            return

        rec_id = f"rec_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        cmd = [
            sys.executable, str(script_path),
            "--rec-id", rec_id,
            "--task", self.current_task.text,
            # Остальные параметры берутся из дефолтов рекордера
        ]
        if self.operator:
            cmd += ["--operator", self.operator]

        if platform.system() == "Darwin":
            self._maybe_show_mac_perms_hint()

        try:
            self.rec_proc = subprocess.Popen(cmd)
        except Exception as e:
            messagebox.showerror("Не удалось запустить запись", str(e))
            return

        self.recording = True
        self.rec_start_time = time.time()
        self._tick_timer()
        self.btn_start.configure(state=tk.DISABLED)
        self.btn_finish.configure(state=tk.NORMAL)
        self.status_var.set(f"Запись идёт → {rec_id}")

        # фон: ждём завершения процесса
        def watcher():
            if self.rec_proc is None:
                return
            rc = self.rec_proc.wait()
            self.after(0, lambda: self._on_recorder_stopped(rc, rec_id))

        threading.Thread(target=watcher, daemon=True).start()
        self._current_rec = {"rec_id": rec_id, "root": "./dataset"}  # корень по умолчанию в рекордере

    def on_finish(self):
        if not self.recording or self.rec_proc is None:
            return
        self.status_var.set("Завершаю запись…")
        try:
            if self.rec_proc.poll() is None:
                self.rec_proc.send_signal(signal.SIGINT)
                for _ in range(30):
                    if self.rec_proc.poll() is not None:
                        break
                    time.sleep(0.1)
            if self.rec_proc.poll() is None:
                self.rec_proc.terminate()
                for _ in range(30):
                    if self.rec_proc.poll() is not None:
                        break
                    time.sleep(0.1)
            if self.rec_proc.poll() is None:
                self.rec_proc.kill()
        except Exception:
            pass

    # ---- хелперы ----
    def _on_recorder_stopped(self, returncode: Optional[int], rec_id: str):
        if not self.recording:
            return
        self.recording = False
        if self._timer_job is not None:
            try:
                self.after_cancel(self._timer_job)
            except Exception:
                pass
            self._timer_job = None
        self.timer_var.set("00:00")
        self.btn_finish.configure(state=tk.DISABLED)

        # не считаем -2 (SIGINT) ошибкой
        if returncode not in (None, 0, -2):
            if returncode == -5:
                message = (
                    "Запись завершилась с ошибкой (SIGTRAP).\n\n"
                    "Обычно это отсутствие прав на Screen Recording / Input Monitoring.\n\n"
                    "System Settings → Privacy & Security →\n"
                    "• Screen Recording\n• Input Monitoring\n• Accessibility\n\n"
                    "Добавьте Terminal или PyCharm, затем перезапустите их."
                )
                messagebox.showerror("Нет прав (macOS)", message)
            else:
                messagebox.showerror("Ошибка записи", f"Дочерний процесс завершился с кодом: {returncode}")

        # submit (если есть API)
        try:
            rec_dir = Path("./dataset") / rec_id
            meta_path = rec_dir / "meta.json"
            meta = {}
            if meta_path.exists():
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if self.current_task:
                self.provider.submit_result(self.current_task.task_id, rec_id, meta)
        except Exception:
            pass

        # следующее задание
        self._fetch_and_show_next_task()
        self.status_var.set("Готово")
        self.btn_start.configure(state=tk.NORMAL if self.current_task else tk.DISABLED)
        self.rec_proc = None

    def _tick_timer(self):
        if not self.recording or self.rec_start_time is None:
            return
        dt = int(time.time() - self.rec_start_time)
        mm, ss = divmod(dt, 60)
        self.timer_var.set(f"{mm:02d}:{ss:02d}")
        self._timer_job = self.after(1000, self._tick_timer)

    def _maybe_show_mac_perms_hint(self):
        msg = (
            "Если запись не стартует/падает на macOS — проверьте права:\n\n"
            "System Settings → Privacy & Security →\n"
            "• Screen Recording\n• Input Monitoring\n• Accessibility\n\n"
            "Добавьте Terminal или PyCharm и перезапустите их."
        )
        print("[INFO] macOS permissions hint:\n" + msg)

    def _find_recorder_script(self) -> Optional[Path]:
        # 1) переменная окружения
        env_path = os.environ.get("RECORDER_SCRIPT", "").strip()
        if env_path and Path(env_path).exists():
            return Path(env_path).resolve()
        # 2) популярные имена рядом с GUI (предпочтение datagrabber_69.py)
        here = Path(__file__).parent
        for name in ("datagrabber_69.py", "pc_screen_dataset_recorder.py"):
            p = here / name
            if p.exists():
                return p.resolve()
        return None

    def _detect_operator(self) -> str:
        op = os.environ.get("OPERATOR_NAME", "").strip()
        if op:
            return op
        try:
            import getpass
            return getpass.getuser()
        except Exception:
            return ""


# --------- фабрика провайдера задач ---------
def make_provider_from_env() -> TaskProvider:
    base = os.environ.get("TASK_API_BASE", "").strip()
    if base:
        return HTTPTaskProvider(base)

    tasks_json = os.environ.get("TASKS_JSON", "").strip()
    if tasks_json and Path(tasks_json).exists():
        tasks = json.loads(Path(tasks_json).read_text(encoding="utf-8"))
        if isinstance(tasks, list):
            return LocalListTaskProvider([str(t) for t in tasks])

    # дефолтные демо-задачи
    return LocalListTaskProvider([
        "Откройте браузер и найдите погоду в Амстердаме",
        "Создайте документ и сохраните его на рабочий стол",
        "Откройте почту и подготовьте черновик письма другу",
    ])


if __name__ == "__main__":
    provider = make_provider_from_env()
    app = App(provider)
    app.mainloop()
