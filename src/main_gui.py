import os
import sys
from typing import List, Set

from PyQt6.QtCore import QPointF, QStandardPaths, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFileSystemModel, QImage, QPainter, QPainterPath, QPen, QUndoCommand, QUndoStack
from PyQt6.QtPrintSupport import QPrinter
from PyQt6.QtSvg import QSvgGenerator
from PyQt6.QtWidgets import (
    QApplication,
    QCompleter,
    QFileDialog,
    QGraphicsItem,
    QGraphicsPathItem,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from main import BezierTracing


class DragDropLineEdit(QLineEdit):
    def __init__(self, filter: Set[str] = None, parent: QWidget = None):
        """[summary]

        Args:
            filter (Set[str]): file extensitons e.g) {".png", ".jpg"}. Defaults to None.
            parent (QWidget, optional): Qt Object. Defaults to None.
        """
        super().__init__(parent)
        self.filters = filter
        self.setDragEnabled(True)
        self.setPlaceholderText("Enter a file path OR Drag & Drop a file")
        completer = QCompleter()
        self.fs_model = QFileSystemModel(completer)
        self.fs_model.setRootPath("")
        if self.filters is not None:
            self.fs_model.setNameFilters({f"*{filter}" for filter in self.filters})
            self.fs_model.setNameFilterDisables(False)
        completer.setModel(self.fs_model)
        self.setCompleter(completer)

    def dragEnterEvent(self, event):
        data = event.mimeData()
        urls = data.urls()
        if len(urls) == 1:
            if urls and urls[0].scheme() == "file":
                if self.filters is not None:
                    ext = os.path.splitext(str(urls[0].path()))[1].lower()
                    if ext in self.filters:
                        event.acceptProposedAction()
                else:
                    event.acceptProposedAction()

    def dragMoveEvent(self, event):
        data = event.mimeData()
        urls = data.urls()
        if urls and urls[0].scheme() == "file":
            event.acceptProposedAction()

    def dropEvent(self, event):
        data = event.mimeData()
        urls = data.urls()
        if urls and urls[0].scheme() == "file":
            file_path = str(urls[0].path())
            if file_path[-1] == "/":
                file_path = file_path[0:-1]
            self.setText(file_path)
            self.set_completer(file_path)

    def set_completer(self, file_path):
        self.fs_model.setRootPath(os.path.dirname(file_path))


class DragDropFileButton(QPushButton):

    file_selected = pyqtSignal(str)

    def __init__(self, filter: Set[str] = None, parent: QWidget = None):
        super().__init__(parent)
        self.filters = filter
        self.setText("Open")
        self.setAcceptDrops(True)
        self.clicked.connect(self.button_clicked)
        self._default_directory_location = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DesktopLocation)
        self.directory_location = self._default_directory_location

    def dragEnterEvent(self, event):
        data = event.mimeData()
        urls = data.urls()
        if urls and urls[0].scheme() == "file":
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        data = event.mimeData()
        urls = data.urls()
        if urls and urls[0].scheme() == "file":
            event.acceptProposedAction()

    def dropEvent(self, event):
        data = event.mimeData()
        urls = data.urls()
        if urls and urls[0].scheme() == "file":
            filepath = str(urls[0].path())
            if filepath[-1] == "/":
                filepath = filepath[0:-1]
            self.file_selected.emit(filepath)

    def button_clicked(self):
        self.open_file_dialog()

    def set_directory_location(self, directory_location):
        if os.path.isdir(directory_location):
            self.directory_location = directory_location
        else:
            directory_location = os.path.dirname(directory_location)
            if os.path.isdir(directory_location):
                self.directory_location = directory_location
            else:
                self.directory_location = self._default_directory_location

    def open_file_dialog(self):
        file_dialog = QFileDialog(self)

        dialog_filter = None
        if self.filters is not None:
            dialog_filter = " ".join([f"{filter} *{filter}" for filter in self.filters])

        filename = file_dialog.getOpenFileName(self, "Select a file", directory=self.directory_location, filter=dialog_filter)
        if filename[0]:
            self.file_selected.emit(filename[0])


class FileSelectWidget(QWidget):
    def __init__(self, filter: Set[str] = None, parent: QWidget = None):
        super().__init__(parent)
        self.filter = filter
        self.line_edit = DragDropLineEdit(self.filter)
        self.button = DragDropFileButton(self.filter)
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.line_edit)
        main_layout.addWidget(self.button)

        self.button.file_selected.connect(self.line_edit.setText)
        self.button.file_selected.connect(self.line_edit.set_completer)
        self.line_edit.textChanged.connect(self.button.set_directory_location)

        self.setLayout(main_layout)

    def get_path(self):
        file_path = self.line_edit.text()
        ext = os.path.splitext(file_path)[1]
        if ext in self.filter:
            if os.path.exists(file_path):
                return file_path


class CustomGraphicsView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setOptimizationFlags(QGraphicsView.OptimizationFlag.DontSavePainterState)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.SmartViewportUpdate)
        self.setCacheMode(QGraphicsView.CacheModeFlag.CacheBackground)

        self.rubber_band_origin = 0
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)

    def keyPressEvent(self, e):
        if not e.isAutoRepeat():
            if e.key() == Qt.Key.Key_Space:
                self.setInteractive(False)
                self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        super().keyPressEvent(e)

    def keyReleaseEvent(self, e):
        if e.key() == Qt.Key.Key_Space:
            self.setInteractive(True)
            self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        super().keyReleaseEvent(e)


class ItemsMoveCommand(QUndoCommand):
    def __init__(self, item_list: List[QGraphicsItem], pos_list: List[QPointF], new_pos_list: List[QPointF]):
        super().__init__()
        self.item_list = item_list
        self.pos_list = pos_list
        self.new_pos_list = new_pos_list

    def undo(self):
        for item, pos in zip(self.item_list, self.pos_list):
            item.setPos(pos)

    def redo(self):
        for item, pos in zip(self.item_list, self.new_pos_list):
            item.setPos(pos)


class ItemsDeleteCommand(QUndoCommand):
    def __init__(self, items: List[QGraphicsItem]):
        super().__init__()
        self.items = items

    def undo(self):
        for item in self.items:
            item.setVisible(True)

    def redo(self):
        for item in self.items:
            item.setVisible(False)


class CustomGraphicsScene(QGraphicsScene):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.selectionChanged.connect(self.selection_changed)
        self.undo_stack = QUndoStack()
        self.origin_item_dict = {}
        self.selected_items = {}

    def _set_item_move_command(self):
        item_list = []
        pos_list = []
        new_pos_list = []
        for item, pos in self.selected_items.items():
            if pos != item.pos():
                item_list.append(item)
                pos_list.append(pos)
                new_pos_list.append(item.pos())
        if item_list:
            command = ItemsMoveCommand(item_list, pos_list, new_pos_list)
            self.undo_stack.push(command)
        new_items = self.selectedItems()
        if new_items:
            self.selected_items.clear()
            for item in new_items:
                self.selected_items[item] = item.pos()

    def selection_changed(self):
        self._set_item_move_command()

    def keyPressEvent(self, e):
        if (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier) == e.modifiers() and e.key() == Qt.Key.Key_Z:
            self.clearSelection()
            self.undo_stack.redo()
        elif Qt.KeyboardModifier.ControlModifier == e.modifiers() and e.key() == Qt.Key.Key_Z:
            self.clearSelection()
            self.undo_stack.undo()
        elif e.key() in {Qt.Key.Key_Backspace, Qt.Key.Key_Delete}:
            items = self.selectedItems()
            self.clearSelection()
            if items:
                command = ItemsDeleteCommand(items)
                self.undo_stack.push(command)
        super().keyPressEvent(e)


class MainWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.items = []

        self.pen = QPen()
        self.pen.setColor(QColor(Qt.GlobalColor.black))
        self.pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        self.brush = QBrush()

        filter = {".png", ".jpg"}
        self.file_select_widget = FileSelectWidget(filter)
        self.view = CustomGraphicsView()
        self.view.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.view.setScene(QGraphicsScene())
        h_box = QHBoxLayout()
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setMinimum(1)
        self.slider.setMaximum(100)
        self.slider.setValue(1)
        self.slider.valueChanged.connect(self.slider_changed)

        self.image_button = QPushButton("Image")
        self.image_button.setCheckable(True)
        self.image_button.toggled.connect(self.trace_image)

        self.fill_button = QPushButton("Fill")
        self.fill_button.setCheckable(True)
        self.fill_button.toggled.connect(self.trace_image)

        self.trace_path_button = QPushButton("Path")
        self.trace_path_button.setCheckable(True)
        self.trace_path_button.clicked.connect(self.trace_image)

        self.path_structure_button = QPushButton("Point")
        self.path_structure_button.setCheckable(True)
        self.path_structure_button.clicked.connect(self.trace_image)

        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self.save)
        h_box.addStretch()
        h_box.addWidget(self.image_button)
        h_box.addWidget(self.trace_path_button)
        h_box.addWidget(self.fill_button)
        h_box.addWidget(self.path_structure_button)
        h_box.addWidget(self.slider)
        h_box.addWidget(self.save_button)
        h_box.setContentsMargins(5, 0, 5, 0)

        v_box = QVBoxLayout()
        v_box.addWidget(self.file_select_widget)
        v_box.addLayout(h_box)
        v_box.addWidget(self.view)
        v_box.setContentsMargins(5, 5, 5, 5)
        self.setLayout(v_box)
        self.resize(700, 500)

        self.image_path = None
        self.bezier_tracing_obj = None
        self.path = None

    def trace_image(self):
        file = self.file_select_widget.get_path()
        if file:
            if self.bezier_tracing_obj and self.bezier_tracing_obj.image_path == file:
                pass
            else:
                self.bezier_tracing_obj = BezierTracing(file)
                scene = CustomGraphicsScene()
                self.view.setScene(scene)
                # Image
                self.image_item = QGraphicsPixmapItem(self.bezier_tracing_obj.qt_pixmap)
                scene.addItem(self.image_item)

                # Trace Path
                self.path = self.bezier_tracing_obj.potrace_path
                self.items = []
                if self.path is not None:
                    for segment in self.path:
                        path_item = QGraphicsPathItem()
                        path_item.setPath(segment)
                        path_item.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable | QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
                        path_item.setPen(self.pen)
                        self.items.append(path_item)
                        scene.addItem(path_item)

                    self.slider.setMaximum(int(self.view.scene().sceneRect().width() / 10))

                    self.view.fitInView(self.view.scene().sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

                    for item in self.items:
                        decorate_path_item(item, min(self.view.scene().sceneRect().width(), self.view.scene().sceneRect().height()) / 300)

            self.image_item.setVisible(self.image_button.isChecked())
            for item in self.items:
                item.setVisible(self.trace_path_button.isChecked())

            for item in self.items:
                for child_item in item.childItems():
                    child_item.setVisible(self.path_structure_button.isChecked())

            if self.fill_button.isChecked():
                self.brush = QBrush(QColor(Qt.GlobalColor.black))
            else:
                self.brush = QBrush()
            for item in self.items:
                item.setBrush(self.brush)
        else:
            self.bezier_tracing_obj = None
            scene = CustomGraphicsScene()
            self.view.setScene(scene)

    def slider_changed(self, value):
        self.pen.setWidth(value)
        for item in self.items:
            item.setPen(self.pen)

    def resizeEvent(self, evt):
        if self.view.scene():
            self.view.fitInView(self.view.scene().sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        super().resizeEvent(evt)

    def save(self):
        filename = QFileDialog.getSaveFileName(
            self, caption="Save Image as png, jpg, svg or pdf", directory=os.path.join(os.path.expanduser("~"), "Desktop"), filter="*.png *.jpg *.svg *.pdf"
        )[0]

        print(filename)
        extenstion = os.path.splitext(filename)[1].lower()
        scene = self.view.scene()
        if extenstion == ".pdf":
            printer = QPrinter()
            printer.setOutputFileName(filename)
            paint = QPainter()
            if paint.begin(printer):
                scene.render(paint)
                paint.end()
        elif extenstion in {".png", ".jpg"}:
            image = QImage(scene.sceneRect().size().toSize(), QImage.Format.Format_ARGB32)
            paint = QPainter(image)
            paint.fillRect(scene.sceneRect(), QBrush(Qt.GlobalColor.white, Qt.BrushStyle.SolidPattern))
            scene.render(paint)
            image.save(filename)

        elif extenstion == ".svg":
            printer = QSvgGenerator()
            printer.setViewBox(self.view.sceneRect())
            printer.setFileName(filename)
            printer.setTitle(None)
            printer.setDescription(None)
            painter = QPainter()
            painter.begin(printer)
            painter.setPen(self.pen)
            painter.setBrush(self.brush)
            for item in self.items:
                painter.drawPath(item.path())
            painter.end()


def decorate_path_item(path_item: QGraphicsPathItem, r: float):
    item = get_points_item(path_item, r)
    item.setParentItem(path_item)


def get_points_item(path_item: QGraphicsPathItem, r: float) -> list:
    path = path_item.path()
    points = []
    is_target = False
    for i in range(path.elementCount()):
        element = path.elementAt(i)
        if element.type == QPainterPath.ElementType.CurveToDataElement:
            if is_target:
                is_target = False
                points.append(((element.x, element.y), True))
            else:
                is_target = True
                points.append(((element.x, element.y), False))
        elif element.type == QPainterPath.ElementType.CurveToElement:
            points.append(((element.x, element.y), False))
        else:
            points.append(((element.x, element.y), True))
    is_first_offpoint = True
    path = QPainterPath()
    for i in range(len(points)):
        pt, on_line = points[i]
        path.addEllipse(pt[0] - r, pt[1] - r, 2 * r, 2 * r)
        if not on_line:
            if is_first_offpoint:
                pre_pt, _ = points[i - 1]
                path.moveTo(pre_pt[0], pre_pt[1])
                path.lineTo(pt[0], pt[1])
                is_first_offpoint = False
            else:
                next_pt, _ = points[i + 1]
                path.moveTo(next_pt[0], next_pt[1])
                path.lineTo(pt[0], pt[1])
                is_first_offpoint = True
    item = QGraphicsPathItem()
    item.setPath(path)
    pen = QPen()
    pen.setColor(QColor(Qt.GlobalColor.green))
    pen.setWidth(int(r))
    item.setPen(pen)
    return item


def main():
    app = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
