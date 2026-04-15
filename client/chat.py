import sys
import os
import json
import base64
import threading
import requests
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QScrollArea, QLabel, QFrame, QSplitter,
    QFileDialog, QCheckBox, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject, QSize
from PyQt6.QtGui import QFont, QPixmap, QIcon, QColor, QPalette, QAction


COLORS = {
    "bg": "#2B2B2B",
    "sidebar_bg": "#1E1E1E",
    "user_msg": "#3A3A3A",
    "assistant_msg": "#2B2B2B",
    "thinking_bg": "#1A1A2E",
    "input_bg": "#3A3A3A",
    "border": "#444444",
    "text": "#E0E0E0",
    "text_dim": "#888888",
    "accent": "#D4A574",
    "user_label": "#7CACF8",
    "assistant_label": "#D4A574",
    "button": "#4A4A4A",
    "button_hover": "#5A5A5A",
    "search_badge": "#2D5A3D",
}


class StreamSignal(QObject):
    chunk = pyqtSignal(str)
    done = pyqtSignal()
    error = pyqtSignal(str)
    search_results = pyqtSignal(str)


class MessageBubble(QFrame):
    clicked = pyqtSignal(dict)

    def __init__(self, role, content, thinking="", search_info="", image_path=""):
        super().__init__()
        self.message_data = {
            "role": role,
            "content": content,
            "thinking": thinking,
            "search_info": search_info,
        }

        self.setFrameShape(QFrame.Shape.NoFrame)
        bg = COLORS["user_msg"] if role == "user" else COLORS["assistant_msg"]
        label_color = COLORS["user_label"] if role == "user" else COLORS["assistant_label"]
        self.setStyleSheet(f"background-color: {bg}; border-bottom: 1px solid {COLORS['border']}; padding: 16px;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(60, 12, 60, 12)

        header = QLabel("You" if role == "user" else "Qwopus")
        header.setStyleSheet(f"color: {label_color}; font-weight: bold; font-size: 13px; border: none; padding: 0;")
        layout.addWidget(header)

        if image_path and os.path.exists(image_path):
            img_label = QLabel()
            pixmap = QPixmap(image_path).scaledToWidth(300, Qt.TransformationMode.SmoothTransformation)
            img_label.setPixmap(pixmap)
            img_label.setStyleSheet("border: none; padding: 4px 0;")
            layout.addWidget(img_label)

        if search_info:
            search_label = QLabel(f"Searched: {search_info}")
            search_label.setStyleSheet(
                f"color: #8BC48A; font-size: 11px; background-color: {COLORS['search_badge']}; "
                f"border-radius: 4px; padding: 3px 8px; border: none;"
            )
            search_label.setFixedHeight(22)
            layout.addWidget(search_label)

        body = QLabel(content)
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        body.setStyleSheet(f"color: {COLORS['text']}; font-size: 14px; line-height: 1.5; border: none; padding: 0;")
        layout.addWidget(body)
        self.body_label = body

        if thinking:
            hint = QLabel("Click to view thinking")
            hint.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 11px; border: none; padding: 0;")
            layout.addWidget(hint)

        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def update_content(self, text):
        self.message_data["content"] = text
        self.body_label.setText(text)

    def update_thinking(self, text):
        self.message_data["thinking"] = text

    def mousePressEvent(self, event):
        self.clicked.emit(self.message_data)
        super().mousePressEvent(event)


class ThinkingSidebar(QFrame):
    def __init__(self):
        super().__init__()
        self.setMinimumWidth(300)
        self.setMaximumWidth(500)
        self.setStyleSheet(f"background-color: {COLORS['sidebar_bg']}; border-left: 1px solid {COLORS['border']};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)

        title = QLabel("Thinking")
        title.setStyleSheet(f"color: {COLORS['accent']}; font-size: 16px; font-weight: bold; border: none;")
        layout.addWidget(title)

        self.content = QTextEdit()
        self.content.setReadOnly(True)
        self.content.setStyleSheet(
            f"color: {COLORS['text']}; background-color: {COLORS['thinking_bg']}; "
            f"border: 1px solid {COLORS['border']}; border-radius: 8px; padding: 12px; font-size: 13px;"
        )
        layout.addWidget(self.content)

        close_btn = QPushButton("Close")
        close_btn.setStyleSheet(
            f"background-color: {COLORS['button']}; color: {COLORS['text']}; "
            f"border: none; border-radius: 6px; padding: 8px 16px; font-size: 13px;"
        )
        close_btn.clicked.connect(self.hide)
        layout.addWidget(close_btn)

    def show_thinking(self, data):
        thinking = data.get("thinking", "")
        search = data.get("search_info", "")
        text = ""
        if search:
            text += f"Search: {search}\n\n"
        if thinking:
            text += thinking
        if not text:
            text = "No thinking data available for this message."
        self.content.setPlainText(text)
        self.show()


class ChatWindow(QMainWindow):
    def __init__(self, api_url, api_key, searxng_url=""):
        super().__init__()
        self.api_url = api_url
        self.api_key = api_key
        self.searxng_url = searxng_url
        self.messages = []
        self.current_image = None
        self.stream_signal = StreamSignal()
        self.stream_signal.chunk.connect(self._on_chunk)
        self.stream_signal.done.connect(self._on_done)
        self.stream_signal.error.connect(self._on_error)
        self.stream_signal.search_results.connect(self._on_search_results)

        self.setWindowTitle("Qwopus Uncensored")
        self.setMinimumSize(900, 600)
        self.showMaximized()

        self._build_ui()
        self._apply_style()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)

        chat_container = QWidget()
        chat_layout = QVBoxLayout(chat_container)
        chat_layout.setContentsMargins(0, 0, 0, 0)
        chat_layout.setSpacing(0)

        # Header
        header = QFrame()
        header.setFixedHeight(50)
        header.setStyleSheet(f"background-color: {COLORS['sidebar_bg']}; border-bottom: 1px solid {COLORS['border']};")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 0, 20, 0)
        title = QLabel("Qwopus Uncensored")
        title.setStyleSheet(f"color: {COLORS['accent']}; font-size: 16px; font-weight: bold; border: none;")
        header_layout.addWidget(title)
        header_layout.addStretch()

        new_chat_btn = QPushButton("New Chat")
        new_chat_btn.setStyleSheet(
            f"background-color: {COLORS['button']}; color: {COLORS['text']}; "
            f"border: none; border-radius: 6px; padding: 6px 14px; font-size: 12px;"
        )
        new_chat_btn.clicked.connect(self._new_chat)
        header_layout.addWidget(new_chat_btn)
        chat_layout.addWidget(header)

        # Messages area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet(
            f"QScrollArea {{ background-color: {COLORS['bg']}; border: none; }}"
            f"QScrollBar:vertical {{ background-color: {COLORS['bg']}; width: 8px; }}"
            f"QScrollBar::handle:vertical {{ background-color: {COLORS['border']}; border-radius: 4px; min-height: 30px; }}"
            f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}"
        )
        self.messages_widget = QWidget()
        self.messages_layout = QVBoxLayout(self.messages_widget)
        self.messages_layout.setContentsMargins(0, 0, 0, 0)
        self.messages_layout.setSpacing(0)
        self.messages_layout.addStretch()
        self.scroll_area.setWidget(self.messages_widget)
        chat_layout.addWidget(self.scroll_area)

        # Input area
        input_container = QFrame()
        input_container.setStyleSheet(f"background-color: {COLORS['sidebar_bg']}; border-top: 1px solid {COLORS['border']};")
        input_layout = QVBoxLayout(input_container)
        input_layout.setContentsMargins(60, 12, 60, 12)

        # Attachment preview
        self.attachment_bar = QFrame()
        self.attachment_bar.setStyleSheet(f"background-color: {COLORS['input_bg']}; border-radius: 6px; padding: 4px;")
        self.attachment_bar.hide()
        att_layout = QHBoxLayout(self.attachment_bar)
        att_layout.setContentsMargins(8, 4, 8, 4)
        self.attachment_label = QLabel()
        self.attachment_label.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 12px; border: none;")
        att_layout.addWidget(self.attachment_label)
        remove_att = QPushButton("x")
        remove_att.setFixedSize(20, 20)
        remove_att.setStyleSheet(f"color: {COLORS['text_dim']}; background: none; border: none; font-size: 14px;")
        remove_att.clicked.connect(self._remove_image)
        att_layout.addWidget(remove_att)
        input_layout.addWidget(self.attachment_bar)

        # Text input + buttons
        input_row = QHBoxLayout()

        self.search_check = QCheckBox("Search")
        self.search_check.setStyleSheet(
            f"QCheckBox {{ color: {COLORS['text_dim']}; font-size: 12px; spacing: 4px; }}"
            f"QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 3px; border: 1px solid {COLORS['border']}; background: {COLORS['input_bg']}; }}"
            f"QCheckBox::indicator:checked {{ background: {COLORS['accent']}; }}"
        )
        input_row.addWidget(self.search_check)

        img_btn = QPushButton("Image")
        img_btn.setStyleSheet(
            f"background-color: {COLORS['button']}; color: {COLORS['text']}; "
            f"border: none; border-radius: 6px; padding: 6px 12px; font-size: 12px;"
        )
        img_btn.clicked.connect(self._pick_image)
        input_row.addWidget(img_btn)

        self.input_box = QTextEdit()
        self.input_box.setFixedHeight(80)
        self.input_box.setPlaceholderText("Message Qwopus...")
        self.input_box.setStyleSheet(
            f"color: {COLORS['text']}; background-color: {COLORS['input_bg']}; "
            f"border: 1px solid {COLORS['border']}; border-radius: 12px; padding: 12px; font-size: 14px;"
        )
        self.input_box.installEventFilter(self)
        input_row.addWidget(self.input_box)

        send_btn = QPushButton("Send")
        send_btn.setFixedSize(70, 40)
        send_btn.setStyleSheet(
            f"background-color: {COLORS['accent']}; color: #1E1E1E; "
            f"border: none; border-radius: 8px; font-size: 13px; font-weight: bold;"
        )
        send_btn.clicked.connect(self._send)
        self.send_btn = send_btn
        input_row.addWidget(send_btn)

        input_layout.addLayout(input_row)
        chat_layout.addWidget(input_container)

        self.splitter.addWidget(chat_container)

        # Thinking sidebar
        self.thinking_sidebar = ThinkingSidebar()
        self.thinking_sidebar.hide()
        self.splitter.addWidget(self.thinking_sidebar)

        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)

        main_layout.addWidget(self.splitter)

    def _apply_style(self):
        self.setStyleSheet(f"QMainWindow {{ background-color: {COLORS['bg']}; }}")

    def eventFilter(self, obj, event):
        if obj == self.input_box and event.type() == event.Type.KeyPress:
            from PyQt6.QtCore import QEvent
            key = event.key()
            mods = event.modifiers()
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not (mods & Qt.KeyboardModifier.ShiftModifier):
                self._send()
                return True
        return super().eventFilter(obj, event)

    def _new_chat(self):
        self.messages = []
        while self.messages_layout.count() > 1:
            item = self.messages_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.thinking_sidebar.hide()

    def _pick_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Image", "", "Images (*.png *.jpg *.jpeg *.gif *.bmp *.webp)")
        if path:
            self.current_image = path
            self.attachment_label.setText(os.path.basename(path))
            self.attachment_bar.show()

    def _remove_image(self):
        self.current_image = None
        self.attachment_bar.hide()

    def _add_bubble(self, role, content, thinking="", search_info="", image_path=""):
        bubble = MessageBubble(role, content, thinking, search_info, image_path)
        bubble.clicked.connect(self.thinking_sidebar.show_thinking)
        self.messages_layout.insertWidget(self.messages_layout.count() - 1, bubble)
        QApplication.processEvents()
        self.scroll_area.verticalScrollBar().setValue(self.scroll_area.verticalScrollBar().maximum())
        return bubble

    def _scroll_bottom(self):
        QApplication.processEvents()
        self.scroll_area.verticalScrollBar().setValue(self.scroll_area.verticalScrollBar().maximum())

    def _send(self):
        text = self.input_box.toPlainText().strip()
        if not text:
            return

        self.input_box.clear()
        self.send_btn.setEnabled(False)
        self.send_btn.setText("...")

        image_path = self.current_image
        do_search = self.search_check.isChecked()

        self._add_bubble("user", text, image_path=image_path or "")
        self._remove_image()
        self.search_check.setChecked(False)

        content = []
        if image_path:
            with open(image_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            ext = os.path.splitext(image_path)[1].lower().replace(".", "")
            mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "gif": "image/gif", "webp": "image/webp"}.get(ext, "image/png")
            content.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}})

        content.append({"type": "text", "text": text})
        self.messages.append({"role": "user", "content": content if image_path else text})

        self.current_bubble = self._add_bubble("assistant", "...")
        self.current_text = ""
        self.current_thinking = ""
        self.current_search_info = ""

        thread = threading.Thread(target=self._stream_response, args=(do_search, text), daemon=True)
        thread.start()

    def _do_search(self, query):
        if not self.searxng_url:
            return ""
        try:
            resp = requests.get(
                f"{self.searxng_url}/search",
                params={"q": query, "format": "json"},
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=15,
            )
            data = resp.json()
            results = data.get("results", [])[:5]
            if not results:
                return ""
            summary = "\n".join([f"- {r.get('title','')}: {r.get('content','')[:200]}" for r in results])
            self.stream_signal.search_results.emit(query)
            return f"\n\nWeb search results for '{query}':\n{summary}\n"
        except Exception:
            return ""

    def _stream_response(self, do_search, user_text):
        msgs = list(self.messages)

        if do_search:
            search_context = self._do_search(user_text)
            if search_context:
                if isinstance(msgs[-1]["content"], str):
                    msgs[-1]["content"] = msgs[-1]["content"] + search_context
                else:
                    for part in msgs[-1]["content"]:
                        if part["type"] == "text":
                            part["text"] += search_context
                            break

        try:
            resp = requests.post(
                f"{self.api_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "/workspace/models/qwopus-27b",
                    "messages": msgs,
                    "max_tokens": 4096,
                    "stream": True,
                },
                stream=True,
                timeout=120,
            )

            if resp.status_code != 200:
                self.stream_signal.error.emit(f"API error {resp.status_code}: {resp.text[:200]}")
                return

            for line in resp.iter_lines():
                if not line:
                    continue
                line = line.decode("utf-8")
                if not line.startswith("data: "):
                    continue
                data = line[6:]
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                    delta = chunk["choices"][0].get("delta", {})
                    token = delta.get("content", "")
                    if token:
                        self.stream_signal.chunk.emit(token)
                except (json.JSONDecodeError, KeyError, IndexError):
                    pass

            self.stream_signal.done.emit()

        except Exception as e:
            self.stream_signal.error.emit(str(e))

    def _on_chunk(self, token):
        if self.current_text == "...":
            self.current_text = ""

        # Separate thinking from content
        if "</think>" in (self.current_text + token):
            self.current_text += token
            parts = self.current_text.split("</think>", 1)
            self.current_thinking = parts[0].replace("<think>", "").strip()
            visible = parts[1].strip() if len(parts) > 1 else ""
            self.current_bubble.update_content(visible or "...")
            self.current_bubble.update_thinking(self.current_thinking)
            self.current_text = self.current_text
        elif "<think>" in self.current_text and "</think>" not in self.current_text:
            self.current_text += token
            thinking_so_far = self.current_text.split("<think>", 1)[1]
            self.current_bubble.update_content("Thinking...")
            self.current_bubble.update_thinking(thinking_so_far)
        else:
            self.current_text += token
            if "<think>" in self.current_text:
                pass
            else:
                self.current_bubble.update_content(self.current_text)

        self._scroll_bottom()

    def _on_done(self):
        final_text = self.current_text
        if "</think>" in final_text:
            parts = final_text.split("</think>", 1)
            thinking = parts[0].replace("<think>", "").strip()
            content = parts[1].strip()
        elif "<think>" in final_text:
            thinking = final_text.replace("<think>", "").strip()
            content = ""
        else:
            thinking = ""
            content = final_text

        self.current_bubble.update_content(content or "(empty response)")
        self.current_bubble.update_thinking(thinking)
        self.current_bubble.message_data["search_info"] = self.current_search_info

        self.messages.append({"role": "assistant", "content": content})
        self.send_btn.setEnabled(True)
        self.send_btn.setText("Send")

    def _on_error(self, err):
        self.current_bubble.update_content(f"Error: {err}")
        self.send_btn.setEnabled(True)
        self.send_btn.setText("Send")

    def _on_search_results(self, query):
        self.current_search_info = query


def load_env():
    env_vars = {}
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")
    env_path = os.path.normpath(env_path)
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                env_vars[key.strip()] = val.strip()
    return env_vars


def main():
    env = load_env()

    pod_id = env.get("RUNPOD_POD_ID", "")
    api_key = env.get("QWOPUS_API_KEY", "")

    if pod_id:
        api_url = f"https://{pod_id}-8000.proxy.runpod.net/v1"
        searxng_url = f"https://{pod_id}-8080.proxy.runpod.net"
    else:
        api_url = ""
        searxng_url = ""

    if not api_url or not api_key:
        print("ERROR: Could not find API URL or key.")
        print("Make sure .env has RUNPOD_POD_ID and QWOPUS_API_KEY set.")
        print("Run ./client/qwopus to start a pod first.")
        sys.exit(1)

    print(f"Pod ID:     {pod_id}")
    print(f"vLLM API:   {api_url}")
    print(f"SearXNG:    {searxng_url or 'not configured'}")
    print(f"API Key:    {api_key[:8]}...")
    print("Starting chat...")

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(COLORS["bg"]))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(COLORS["text"]))
    palette.setColor(QPalette.ColorRole.Base, QColor(COLORS["input_bg"]))
    palette.setColor(QPalette.ColorRole.Text, QColor(COLORS["text"]))
    app.setPalette(palette)

    window = ChatWindow(api_url, api_key, searxng_url)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
