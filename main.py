import os
import sys
import zipfile
import requests
import json
import subprocess
import re
from PyQt5 import QtWidgets, QtGui, QtCore
import shutil
import threading

APP_VERSION = "1.0.0"
NEW_VERSION_AVAILABLE = False
LATEST_VERSION_INFO = None

def ensure_video_recovery_folder():
    user_dir = os.path.expanduser("~")
    vr_dir = os.path.join(user_dir, "VideoRecovery")
    if not os.path.exists(vr_dir):
        os.makedirs(vr_dir)
    return vr_dir

def download_and_extract_untrunc(dest_dir):
    url = "https://github.com/anthwlock/untrunc/releases/download/latest/untrunc_x64.zip"
    zip_path = os.path.join(dest_dir, "untrunc_x64.zip")
    exe_dir = os.path.join(dest_dir, "untrunc_x64")
    exe_path = os.path.join(exe_dir, "untrunc.exe")
    if not os.path.exists(exe_path):
        r = requests.get(url, stream=True)
        with open(zip_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(dest_dir)
        os.remove(zip_path)

def config_path():
    return os.path.join(ensure_video_recovery_folder(), "config.json")

def load_config():
    path = config_path()
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_config(cfg):
    path = config_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

class CreditWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("クレジット")
        self.setFixedSize(500, 140)
        self.setStyleSheet("background-color: #fff;")

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.fillRect(self.rect(), QtGui.QColor(255, 255, 255))
        painter.setPen(QtGui.QColor(40, 40, 40))
        font = painter.font()
        font.setPointSize(18)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(QtCore.QRect(20, 18, self.width()-40, 32), QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop, "クレジット")
        font.setPointSize(12)
        font.setBold(False)
        painter.setFont(font)
        painter.setPen(QtGui.QColor(100, 100, 100))
        painter.drawText(QtCore.QRect(20, 50, self.width()-40, 22), QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop, "このソフトはuntruncを使用して復元を行っています。")
        painter.setPen(QtGui.QColor(0, 102, 204))
        painter.drawText(QtCore.QRect(20, 75, self.width()-40, 20), QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop, "https://github.com/ponchio/untrunc")
        painter.drawText(QtCore.QRect(20, 95, self.width()-40, 20), QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop, "https://github.com/anthwlock/untrunc")
    def mousePressEvent(self, event):
        y = event.pos().y()
        if 75 <= y < 95:
            QtGui.QDesktopServices.openUrl(QtCore.QUrl("https://github.com/ponchio/untrunc"))
        elif 95 <= y < 115:
            QtGui.QDesktopServices.openUrl(QtCore.QUrl("https://github.com/anthwlock/untrunc"))

    def mouseMoveEvent(self, event):
        y = event.pos().y()
        if 75 <= y < 95 or 95 <= y < 115:
            self.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        else:
            self.setCursor(QtGui.QCursor(QtCore.Qt.ArrowCursor))

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ドロップ動画復元")
        self.setFixedSize(960, 540)
        self.setStyleSheet("background-color: #f5f5f5;")
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico")
        self.setWindowIcon(QtGui.QIcon(icon_path))
        self.init_menu()
        self.central_widget = UploadWidget(self)
        self.setCentralWidget(self.central_widget)

    def init_menu(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("ファイル")
        file_menu.setStyleSheet("QMenu { color: #222; background: #fff; } QMenu::item:selected { background: #e0e0e0; color: #222; }")
        recover_action = QtWidgets.QAction("ファイルを指定して復元", self)
        select_normal_action = QtWidgets.QAction("正常な動画の選択", self)
        file_menu.addAction(recover_action)
        file_menu.addAction(select_normal_action)
        credit_action = QtWidgets.QAction("クレジット", self)
        menubar.addAction(credit_action)
        credit_action.triggered.connect(self.show_credit)
        select_normal_action.triggered.connect(self.select_normal_video)
        recover_action.triggered.connect(self.recover_from_menu)

    def show_credit(self):
        self.credit_win = CreditWindow()
        self.credit_win.show()

    def select_normal_video(self):
        fname, _ = QtWidgets.QFileDialog.getOpenFileName(self, "正常な動画を選択", "", "動画ファイル (*.mp4)")
        if fname:
            cfg = load_config()
            cfg["normal_video"] = fname
            save_config(cfg)
            QtWidgets.QMessageBox.information(self, "正常な動画", "正常な動画を設定しました。")

    def recover_from_menu(self):
        fname, _ = QtWidgets.QFileDialog.getOpenFileName(self, "復元する壊れた動画を選択", "", "動画ファイル (*.mp4)")
        if fname:
            self.central_widget.start_recovery(fname)

    def closeEvent(self, event):
        QtCore.QCoreApplication.quit()
        os._exit(0)

class UploadWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.status = "idle"
        self.progress = 0
        self.dropped_file = None
        self.version_rect = None
    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.fillRect(self.rect(), QtGui.QColor(255, 255, 255))
        cx = self.width() // 2
        cy = self.height() // 2
        r = 40
        painter.setBrush(QtGui.QColor(230, 230, 230, 220))
        painter.setPen(QtGui.QPen(QtGui.QColor(230, 230, 230), 0))
        painter.drawEllipse(QtCore.QPoint(cx, cy - 50), r, r)
        arrow_pen = QtGui.QPen(QtGui.QColor(80, 80, 80), 8, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin)
        painter.setPen(arrow_pen)
        painter.setBrush(QtCore.Qt.NoBrush)
        painter.drawLine(cx, cy - 32, cx, cy - 68)
        painter.drawLine(cx, cy - 68, cx - 14, cy - 52)
        painter.drawLine(cx, cy - 68, cx + 14, cy - 52)
        painter.setPen(QtGui.QColor(40, 40, 40))
        font = painter.font()
        font.setPointSize(22)
        painter.setFont(font)
        if self.status == "idle":
            painter.drawText(QtCore.QRect(0, cy + 5, self.width(), 40), QtCore.Qt.AlignHCenter | QtCore.Qt.AlignTop, "動画をドロップして復元")
        elif self.status == "running":
            painter.drawText(QtCore.QRect(0, cy + 5, self.width(), 40), QtCore.Qt.AlignHCenter | QtCore.Qt.AlignTop, "復元中です。")
        elif self.status == "done":
            painter.drawText(QtCore.QRect(0, cy + 5, self.width(), 40), QtCore.Qt.AlignHCenter | QtCore.Qt.AlignTop, "復元が完了しました。")
        painter.setPen(QtGui.QColor(100, 100, 100))
        font.setPointSize(12)
        painter.setFont(font)
        if self.status == "idle":
            painter.drawText(QtCore.QRect(0, cy + 35, self.width(), 30), QtCore.Qt.AlignHCenter | QtCore.Qt.AlignTop, "必ずしも復元できるわけではありません。")
        elif self.status == "running":
            painter.drawText(QtCore.QRect(0, cy + 35, self.width(), 30), QtCore.Qt.AlignHCenter | QtCore.Qt.AlignTop, f"復元作業を行っています。{self.progress}%完了しました。")
        elif self.status == "done":
            painter.drawText(QtCore.QRect(0, cy + 35, self.width(), 30), QtCore.Qt.AlignHCenter | QtCore.Qt.AlignTop, "保存先を選択してください。")

        version_font = painter.font()
        version_font.setPointSize(10)
        version_font.setUnderline(False)

        copyright_font = painter.font()
        copyright_font.setPointSize(10)
        copyright_font.setUnderline(False)
        version_text = f"Version {APP_VERSION}"
        copyright_text = "© 2025 Fukuringa"
        margin = 16
        metrics = QtGui.QFontMetrics(version_font)
        version_width = metrics.width(version_text)
        version_height = metrics.height()
        dot_d = 8
        x = self.width() - margin - max(version_width + dot_d + 6, QtGui.QFontMetrics(copyright_font).width(copyright_text))
        y = self.height() - margin - version_height*2 + 2

        if NEW_VERSION_AVAILABLE:
            painter.setPen(QtGui.QColor(255, 140, 0))
            version_font.setUnderline(True)
            painter.setFont(version_font)
        else:
            painter.setPen(QtGui.QColor(0, 0, 0))
            version_font.setUnderline(False)
            painter.setFont(version_font)
        painter.drawText(x, y + version_height, version_text)

        dot_x = x + version_width + 6 + dot_d//2
        dot_y = y + version_height - dot_d//2
        if NEW_VERSION_AVAILABLE:
            painter.setBrush(QtGui.QColor(255, 140, 0))
        else:
            painter.setBrush(QtGui.QColor(0, 200, 0))
        painter.setPen(QtCore.Qt.NoPen)
        painter.drawEllipse(QtCore.QPoint(dot_x, dot_y), dot_d//2, dot_d//2)

        painter.setPen(QtGui.QColor(0, 0, 0))
        painter.setFont(copyright_font)
        painter.setBrush(QtCore.Qt.NoBrush)
        painter.drawText(x, y + version_height*2, copyright_text)

        self.version_rect = QtCore.QRect(
            x,
            int(y + version_height - version_height),
            version_width + dot_d + 10,
            version_height
        )

    def mouseMoveEvent(self, event):
        self.setCursor(QtGui.QCursor(QtCore.Qt.ArrowCursor))

    def mousePressEvent(self, event):
        if self.version_rect and self.version_rect.contains(event.pos()):
            if event.button() == QtCore.Qt.RightButton or event.button() == QtCore.Qt.LeftButton:
                self.show_version_dialog()

    def show_version_dialog(self):
        if NEW_VERSION_AVAILABLE and LATEST_VERSION_INFO:
            v = LATEST_VERSION_INFO
            msg = f"新しいバージョンがあります！\n\nバージョン: {v['version']}\n内容: {v['description']}\nリリース日: {v['time']}\n\nアップデートしますか？\n\n「はい」を押した場合、更新が始まり最大1分ほどで自動で起動します。\nそれまでの間ソフトを起動したりしないでください。"

            msgBox = QtWidgets.QMessageBox(self)
            msgBox.setWindowTitle("アップデート")
            msgBox.setText(msg)
            msgBox.setIcon(QtWidgets.QMessageBox.Question)

            yes_button = msgBox.addButton("はい", QtWidgets.QMessageBox.YesRole)
            no_button = msgBox.addButton("いいえ", QtWidgets.QMessageBox.NoRole)

            msgBox.exec_()

            if msgBox.clickedButton() == yes_button:
                threading.Thread(target=self.update_app, args=(v['url'],), daemon=True).start()
        else:
            QtWidgets.QMessageBox.information(self, "バージョン情報", "現在バージョンは最新です。")

    def update_app(self, url):
        try:
            exe_path = sys.argv[0]
            vr_dir = ensure_video_recovery_folder()
            update_script = os.path.join(vr_dir, "update_temp.bat")
            new_exe_path = exe_path + ".new"
            bat = f"""@echo off
curl -L -o "{new_exe_path}" -A "Mozilla/5.0" "{url}"
if not exist "{new_exe_path}" (
    echo ダウンロード失敗
    pause
    exit /b
)
del "{exe_path}" >nul 2>&1
rename "{new_exe_path}" "{os.path.basename(exe_path)}"
explorer "{exe_path}"
del "%~f0"
"""
            with open(update_script, "w", encoding="shift_jis") as f:
                f.write(bat)
            subprocess.Popen(
                ['cmd', '/c', update_script],
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            QtCore.QCoreApplication.quit()
            os._exit(0)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "アップデート失敗", f"アップデートに失敗しました: {e}")

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls and urls[0].toLocalFile().lower().endswith(".mp4"):
                event.acceptProposedAction()
            else:
                event.ignore()
        else:
            event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            mp4_path = urls[0].toLocalFile()
            self.start_recovery(mp4_path)

    def start_recovery(self, mp4_path):
        self.dropped_file = mp4_path
        cfg = load_config()
        normal_video = cfg.get("normal_video")
        if not normal_video:
            QtWidgets.QMessageBox.critical(self, "エラー", "正常なファイルが選択されていません。\nメニューの「ファイル」から「正常な動画を選択」してください。")
            return
        if not os.path.exists(normal_video):
            QtWidgets.QMessageBox.critical(self, "エラー", "正常な動画ファイルが存在しません。再度選択してください。")
            return
        vr_dir = ensure_video_recovery_folder()
        exe_path = os.path.join(vr_dir, "untrunc_x64", "untrunc.exe")
        if not os.path.exists(exe_path):
            QtWidgets.QMessageBox.critical(self, "エラー", "復元プログラムが存在しません。")
            return
        self.status = "running"
        self.progress = 0
        self.update()
        QtCore.QTimer.singleShot(100, self.run_recovery)

    def run_recovery(self):
        vr_dir = ensure_video_recovery_folder()
        exe_path = os.path.join(vr_dir, "untrunc_x64", "untrunc.exe")
        cfg = load_config()
        normal_video = cfg.get("normal_video")
        broken_video = self.dropped_file
        out_path = broken_video + "_fixed.mp4"

        self.progress = 0
        self.update()
        QtWidgets.QApplication.processEvents()

        try:
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = 0
            proc = subprocess.Popen(
                [exe_path, normal_video, broken_video],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="ignore",
                bufsize=1,
                startupinfo=si
            )
            while True:
                line = proc.stdout.readline()
                if not line and proc.poll() is not None:
                    break
                if line:
                    m = re.search(r'(\d+(?:\.\d+)?)%', line)
                    if m:
                        self.progress = float(m.group(1))
                        self.update()
                        QtWidgets.QApplication.processEvents()
            retcode = proc.wait()
            if retcode != 0:
                raise Exception("untruncの実行に失敗しました")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "エラー", f"復元に失敗しました: {e}")
            self.status = "idle"
            self.progress = 0
            self.update()
            return
        if not os.path.exists(out_path):
            QtWidgets.QMessageBox.critical(self, "エラー", "復元ファイルが作成されませんでした。")
            self.status = "idle"
            self.progress = 0
            self.update()
            return
        self.progress = 100
        self.status = "done"
        self.update()
        self.save_result(out_path)

    def save_result(self, out_path):
        orig_name = os.path.splitext(os.path.basename(self.dropped_file))[0]
        default_name = f"{orig_name}_復元.mp4"
        dlg = QtWidgets.QFileDialog(self, "復元した動画の保存先", default_name, "動画ファイル (*.mp4)")
        dlg.setAcceptMode(QtWidgets.QFileDialog.AcceptSave)
        dlg.setDefaultSuffix("mp4")
        if dlg.exec_():
            save_path = dlg.selectedFiles()[0]
            try:
                try:
                    os.replace(out_path, save_path)
                except OSError:
                    try:
                        shutil.move(out_path, save_path)
                    except Exception:
                        shutil.copyfile(out_path, save_path)
                        os.remove(out_path)
                QtWidgets.QMessageBox.information(self, "保存完了", "復元した動画を保存しました。")
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "保存失敗", f"保存に失敗しました: {e}")
        else:
            os.remove(out_path)
        self.status = "idle"
        self.progress = 0
        self.update()

def check_new_version():
    global NEW_VERSION_AVAILABLE, LATEST_VERSION_INFO
    try:
        resp = requests.get("https://pastebin.com/raw/fAebrmCL", timeout=3)
        if resp.status_code == 200:
            versions = resp.json()
            for v in versions:
                if compare_version(v["version"], APP_VERSION) > 0:
                    NEW_VERSION_AVAILABLE = True
                    LATEST_VERSION_INFO = v
                    break
    except Exception:
        pass

def compare_version(v1, v2):
    def parse(v): return [int(x) for x in v.split('.')]
    p1, p2 = parse(v1), parse(v2)
    for a, b in zip(p1, p2):
        if a != b:
            return a - b
    return len(p1) - len(p2)

if __name__ == "__main__":
    def start_app():
        app = QtWidgets.QApplication(sys.argv)
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico")
        app.setWindowIcon(QtGui.QIcon(icon_path))
        win = MainWindow()
        win.show()
        sys.exit(app.exec_())

    def background_init_and_start():
        check_new_version()
        vr_dir = ensure_video_recovery_folder()
        exe_dir = os.path.join(vr_dir, "untrunc_x64")
        exe_path = os.path.join(exe_dir, "untrunc.exe")
        if not os.path.exists(exe_path):
            download_and_extract_untrunc(vr_dir)
        start_app()

    threading.Thread(target=background_init_and_start, daemon=True).start()
    while True:
        QtCore.QThread.msleep(100)