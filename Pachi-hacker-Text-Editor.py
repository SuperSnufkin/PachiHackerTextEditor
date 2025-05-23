#!/usr/bin/env python3
import sys, os, json, tempfile, atexit
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTextEdit, QAction, QFileDialog,
    QToolBar, QComboBox, QTabWidget, QWidget, QVBoxLayout,
    QInputDialog, QMessageBox
)
from PyQt5.QtGui import (
    QIcon, QTextCursor, QTextCharFormat, QFont, QSyntaxHighlighter,
    QTextDocumentWriter
)
from PyQt5.QtCore import Qt, QTimer, QRegularExpression
from PyQt5.QtPrintSupport import QPrinter

SESSION_FILE = os.path.join(tempfile.gettempdir(), "hacker_editor_session.json")

# --- Resaltador básico Python ---
class PythonHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        kw = QTextCharFormat(); kw.setForeground(Qt.cyan); kw.setFontWeight(QFont.Bold)
        com = QTextCharFormat(); com.setForeground(Qt.darkGreen)
        self.rules = [
            (QRegularExpression(r"\b(def|class|if|else|elif|while|for|in|import|from|as|return|with|try|except)\b"), kw),
            (QRegularExpression(r"#[^\n]*"), com),
        ]

    def highlightBlock(self, text):
        for pattern, fmt in self.rules:
            it = pattern.globalMatch(text)
            while it.hasNext():
                m = it.next()
                self.setFormat(m.capturedStart(), m.capturedLength(), fmt)

# --- Pestaña de editor ---
class EditorTab(QWidget):
    def __init__(self, path=None, html=None):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.text = QTextEdit()
        self.text.setStyleSheet(
            "background-color: black; color: #00FF00; "
            "font-family: Courier; font-size: 14pt;"
        )
        PythonHighlighter(self.text.document())
        # Cargar sesión con formato (HTML) o archivo plano
        if html is not None:
            self.text.setHtml(html)
        elif path:
            with open(path, encoding="utf-8") as f:
                self.text.setPlainText(f.read())
        self.layout.addWidget(self.text)
        self.path = path

    def filename(self):
        return os.path.basename(self.path) if self.path else "Untitled"

# --- Ventana principal ---
class HackerEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Pachi Hacker-Text-Editor")
        self.resize(900, 600)

        # Pestañas
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # Auto‐guardado de sesión
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.auto_save_session)
        self.timer.start(60000)
        atexit.register(self.auto_save_session)

        self.load_session()
        self._init_ui()

    def _init_ui(self):
        toolbar = QToolBar(self)
        toolbar.setStyleSheet("background-color: #111;")
        self.addToolBar(toolbar)

        def mk(icon_name, text, slot, shortcut=None, checkable=False):
            if icon_name:
                act = QAction(QIcon.fromTheme(icon_name), text, self)
            else:
                act = QAction(text, self)
            if shortcut:
                act.setShortcut(shortcut)
            act.setCheckable(checkable)
            act.triggered.connect(slot)
            toolbar.addAction(act)
            return act

        # Archivo y pestañas
        mk("document-open", "Abrir .txt/.py",    self.open_txt_py,      "Ctrl+O")
        mk("document-save", "Guardar .txt",      self.save_txt,         "Ctrl+S")
        mk(None,            "Guardar .odt",      self.save_odt)
        mk(None,            "Exportar PDF",      self.export_pdf)
        mk("tab-new",       "Nueva pestaña",     self.new_tab,          "Ctrl+T")
        toolbar.addSeparator()

        # Deshacer / Rehacer
        mk(None, "Deshacer", self.undo, "Ctrl+Z")
        mk(None, "Rehacer",  self.redo, "Ctrl+Y")
        toolbar.addSeparator()

        # Buscar / Reemplazar
        mk(None, "Buscar/Reemplazar", self.find_replace, "Ctrl+F")
        toolbar.addSeparator()

        # Alineación
        mk(None, "Izquierda", lambda: self.align(Qt.AlignLeft))
        mk(None, "Centro",    lambda: self.align(Qt.AlignCenter))
        mk(None, "Derecha",   lambda: self.align(Qt.AlignRight))
        toolbar.addSeparator()

        # Negrita
        self.bold_act = mk(None, "Negrita", self.toggle_bold, "Ctrl+B", True)
        toolbar.addSeparator()

        # Tamaño de fuente
        size_label = QAction("Tamaño:", self); size_label.setEnabled(False)
        toolbar.addAction(size_label)
        self.size_cb = QComboBox()
        self.size_cb.addItems(map(str, range(6, 25)))
        self.size_cb.setCurrentText("14")
        self.size_cb.setFixedWidth(50)
        self.size_cb.currentTextChanged.connect(self.change_size)
        toolbar.addWidget(self.size_cb)
        toolbar.addSeparator()

        # Tema
        self.theme_cb = QComboBox()
        self.theme_cb.addItems(["Hacker (negro/verde)", "Claro (blanco/negro)"])
        self.theme_cb.currentIndexChanged.connect(self.change_theme)
        toolbar.addWidget(self.theme_cb)
        toolbar.addSeparator()

        # Acerca de
        mk(None, "Acerca de", self.show_about)

    # — Funciones de información —
    def show_about(self):
        msg = QMessageBox(self)
        msg.setWindowTitle("Acerca de")
        msg.setTextFormat(Qt.RichText)
        msg.setText(
            'Este Editor de Texto "Hacker-Minimalista" fue creado por Israel G. Bistrain y Pachi.<br>'
            'Puedes seguirnos en Mastodon: '
            '<a href="https://mastodon.social/@supersnufkin" style="color:#00FF00;">'
            '@supersnufkin@mastodon.social</a>'
        )
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec_()

    # — Helpers de pestañas y sesión —
    def current(self):
        return self.tabs.currentWidget().text

    def new_tab(self):
        tab = EditorTab()
        self.tabs.addTab(tab, tab.filename())
        self.tabs.setCurrentWidget(tab)

    def load_session(self):
        if os.path.exists(SESSION_FILE):
            with open(SESSION_FILE, encoding="utf-8") as f:
                data = json.load(f)
            for item in data:
                tab = EditorTab(item.get("path"), html=item.get("html"))
                self.tabs.addTab(tab, tab.filename())
        if self.tabs.count() == 0:
            self.new_tab()

    def auto_save_session(self):
        data = []
        for i in range(self.tabs.count()):
            t = self.tabs.widget(i)
            data.append({
                "path": t.path,
                "html": t.text.toHtml()
            })
        with open(SESSION_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f)

    # — Abrir/Guardar TXT & PY —
    def open_txt_py(self):
        path, _ = QFileDialog.getOpenFileName(self, "Abrir", "", "Text (*.txt *.py)")
        if not path: return
        txt = open(path, encoding="utf-8").read()
        self.current().setPlainText(txt)
        tab = self.tabs.currentWidget()
        tab.path = path
        self.tabs.setTabText(self.tabs.currentIndex(), tab.filename())

    def save_txt(self):
        path, _ = QFileDialog.getSaveFileName(self, "Guardar .txt", "", "Text (*.txt)")
        if not path: return
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.current().toPlainText())
        tab = self.tabs.currentWidget()
        tab.path = path
        self.tabs.setTabText(self.tabs.currentIndex(), tab.filename())

    # — Guardar ODT puro Qt —
    def save_odt(self):
        path, _ = QFileDialog.getSaveFileName(self, "Guardar .odt", "", "ODT (*.odt)")
        if not path: return
        writer = QTextDocumentWriter(path, b"ODF")
        writer.write(self.current().document())
        tab = self.tabs.currentWidget()
        tab.path = path
        self.tabs.setTabText(self.tabs.currentIndex(), tab.filename())

    # — Exportar PDF —
    def export_pdf(self):
        path, _ = QFileDialog.getSaveFileName(self, "Exportar PDF", "", "PDF (*.pdf)")
        if not path: return
        printer = QPrinter(QPrinter.HighResolution)
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(path)
        self.current().document().print_(printer)
        QMessageBox.information(self, "PDF guardado", f"Guardado en:\n{path}")

    # — Deshacer/Rehacer —
    def undo(self): self.current().undo()
    def redo(self): self.current().redo()

    # — Buscar/Reemplazar simple —
    def find_replace(self):
        ed = self.current()
        find_text, ok = QInputDialog.getText(self, "Buscar", "Texto:")
        if not ok or not find_text: return
        replace_text, _ = QInputDialog.getText(self, "Reemplazar", "Por:")
        doc = ed.document(); cur = QTextCursor(doc)
        while True:
            cur = doc.find(find_text, cur)
            if cur.isNull(): break
            cur.insertText(replace_text)

    # — Formato dinámico —
    def merge(self, fmt: QTextCharFormat):
        ed = self.current(); cur = ed.textCursor()
        if cur.hasSelection():
            cur.mergeCharFormat(fmt); ed.setTextCursor(cur)
        else:
            ed.mergeCurrentCharFormat(fmt)

    def toggle_bold(self, checked):
        fmt = QTextCharFormat()
        fmt.setFontWeight(QFont.Bold if checked else QFont.Normal)
        self.merge(fmt)

    def change_size(self, s):
        try: sz = int(s)
        except ValueError: return
        fmt = QTextCharFormat()
        fmt.setFontPointSize(sz)
        self.merge(fmt)

    def change_theme(self, idx):
        ss = ("background-color:black;color:#00FF00; font-family:Courier; font-size:14pt;"
              if idx == 0 else
              "background:white;color:black; font-family:Courier; font-size:14pt;")
        for i in range(self.tabs.count()):
            self.tabs.widget(i).text.setStyleSheet(ss)

    def align(self, alignment):
        self.current().setAlignment(alignment)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = HackerEditor()
    win.show()
    sys.exit(app.exec_())

