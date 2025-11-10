# -*- coding: utf-8 -*-
"""
Created on Mon Nov 10 16:03:58 2025

@author: pramod yadav
"""
import sys
import json
import tempfile
import os
from pathlib import Path
import re
import math
import uuid 

# PyQt5 imports
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QTabWidget, QFrame, QLabel, QPushButton, QRadioButton, QButtonGroup,
                             QLineEdit, QScrollArea, QGroupBox, QMessageBox, QFileDialog,
                             QColorDialog, QStatusBar, QSplitter, QGraphicsView, 
                             QGraphicsScene, QInputDialog, QCheckBox, QComboBox, QGridLayout,
                             QGraphicsTextItem, QGraphicsItem, QGraphicsRectItem, QGraphicsPathItem, 
                             QGraphicsEllipseItem, QGraphicsLineItem, QPlainTextEdit, QFormLayout) # Added QPlainTextEdit, QFormLayout
from PyQt5.QtCore import Qt, QUrl, QRectF, QPointF
from PyQt5.QtGui import QPen, QColor, QBrush, QPainterPath, QPainter, QKeySequence, QFont, QPixmap, QImage
from PyQt5.QtWidgets import QShortcut
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtSvg import QSvgGenerator # Necessary for canvas SVG export

# Other required libraries
import networkx as nx
import matplotlib.figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar

# --- Custom Graphics Items ---

class EditableTextItem(QGraphicsTextItem):
    def __init__(self, parent_shape, text):
        super().__init__(text)
        self.parent_shape = parent_shape
        self.setFont(QFont("Arial", 9))
        self.setTextInteractionFlags(Qt.TextEditorInteraction)
    
    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        new_text = self.toPlainText()
        if new_text != self.parent_shape.text:
            self.parent_shape.text = new_text
            
            # Trigger auto-resize when text is changed directly on canvas
            self.parent_shape.auto_resize_to_fit_text(padding=30)
            
            # This will also update the side panel and the previews
            self.parent_shape.scene.parent_widget.refresh_preview()
            
            # Also update the selected properties panel text box
            if self.parent_shape.scene.parent_widget.selected_shape == self.parent_shape:
                 # Block signals to prevent infinite recursion
                widget = self.parent_shape.scene.parent_widget
                widget.selected_text_input.blockSignals(True)
                widget.selected_text_input.setPlainText(new_text)
                widget.selected_text_input.blockSignals(False)

class CustomGraphicsItem(QGraphicsItem):
    def __init__(self, shape_obj, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.shape_obj = shape_obj
        self.visual_item = None 
        
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)

    def boundingRect(self):
        return QRectF(0, 0, self.shape_obj.width, self.shape_obj.height)

    def paint(self, painter, option, widget=None):
        pass 

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange and self.shape_obj:
            self.shape_obj.x = value.x()
            self.shape_obj.y = value.y()
            self.shape_obj.update_text_position() 
            self.scene().parent_widget.update_all_connectors()
            return value
        
        elif change == QGraphicsItem.ItemPositionHasChanged and self.shape_obj:
            self.scene().parent_widget.refresh_preview()
            
        return super().itemChange(change, value)

class Shape:
    def __init__(self, scene, shape_type, x, y, width=100, height=60, text="Shape", shape_id=None, color=None):
        self.scene = scene
        self.type = shape_type
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.text = text
        self.id = shape_id if shape_id is not None else str(uuid.uuid4())
        self.selected = False
        self.color = color if color else QColor("lightblue")
        self.border_color = QColor("black")
        self.graphics_item = None
        self.text_item = None
        self.draw()

    def auto_resize_to_fit_text(self, padding=30):
        """Calculates and updates shape size to fit text, then redraws."""
        if not self.text_item:
            self.draw_text() # Ensure text item exists
            
        # 1. Get required text dimensions
        self.text_item.setPlainText(self.text)
        text_document = self.text_item.document()
        
        MAX_WIDTH = 300 
        MIN_WIDTH = 100
        MIN_HEIGHT = 60
        
        # Determine the maximum required width of the text *without* wrapping
        max_text_width_no_wrap = math.ceil(text_document.idealWidth())
        
        # Calculate the actual width the shape should have
        new_width_content = max(MIN_WIDTH, max_text_width_no_wrap + padding)
        
        if new_width_content > MAX_WIDTH + padding:
            new_width = MAX_WIDTH + padding
            # Set the text item width constraint to the new capped shape width - margin
            self.text_item.setTextWidth(new_width - padding) 
            # Re-read the resulting document size after wrapping
            new_height = max(MIN_HEIGHT, math.ceil(self.text_item.document().size().height()) + padding)
        else:
            new_width = new_width_content
            self.text_item.setTextWidth(new_width - padding) # Set text width to be based on the shape
            new_height = max(MIN_HEIGHT, math.ceil(self.text_item.document().size().height()) + padding)


        if new_width != self.width or new_height != self.height:
            # 2. Apply new dimensions
            self.width = new_width
            self.height = new_height
            
            # 3. Redraw shape and text items
            self.draw()
            
            # 4. Update connectors
            self.scene.parent_widget.update_all_connectors()
        else:
             # Ensure text position is centered even if size didn't change (e.g., text content did)
             self.update_text_position()

    def center_point(self):
        return QPointF(self.x + self.width / 2, self.y + self.height / 2)

    def draw(self):
        if not self.graphics_item:
            self.graphics_item = CustomGraphicsItem(self)
            self.scene.addItem(self.graphics_item)
            
        self.graphics_item.setPos(self.x, self.y)
        self.draw_shape_visual()
        self.draw_text()
        
        pen = QPen(self.border_color, 2)
        if self.selected:
            pen = QPen(QColor("red"), 3)
        
        if self.graphics_item.visual_item:
            self.graphics_item.visual_item.setPen(pen)

    def draw_shape_visual(self):
        if self.graphics_item.visual_item:
            # Remove previous visual item if it exists
            self.graphics_item.visual_item.setParentItem(None)
            self.graphics_item.visual_item = None
        
        visual_item = None
        pen = QPen(self.border_color, 2)
        brush = QBrush(self.color)
        
        if self.type in ["rectangle", "process"]:
            visual_item = QGraphicsRectItem(0, 0, self.width, self.height, self.graphics_item)
        
        elif self.type == "start_end": 
            path = QPainterPath()
            radius = min(self.width, self.height) * 0.2
            path.addRoundedRect(0, 0, self.width, self.height, radius, radius)
            visual_item = QGraphicsPathItem(path, self.graphics_item)

        elif self.type == "input_output":
            path = QPainterPath()
            slant = self.width * 0.15 
            points = [QPointF(slant, 0), QPointF(self.width, 0),
                      QPointF(self.width - slant, self.height), QPointF(0, self.height)]
            path.moveTo(points[0])
            for point in points[1:]: path.lineTo(point)
            path.closeSubpath()
            visual_item = QGraphicsPathItem(path, self.graphics_item)

        elif self.type in ["diamond", "decision"]:
            path = QPainterPath()
            points = [QPointF(self.width / 2, 0), QPointF(self.width, self.height / 2),
                      QPointF(self.width / 2, self.height), QPointF(0, self.height / 2)]
            path.moveTo(points[0])
            for point in points[1:]: path.lineTo(point)
            path.closeSubpath()
            visual_item = QGraphicsPathItem(path, self.graphics_item)
            
        elif self.type == "ellipse":
            visual_item = QGraphicsEllipseItem(0, 0, self.width, self.height, self.graphics_item)
        
        if visual_item:
            visual_item.setPen(pen)
            visual_item.setBrush(brush)
            self.graphics_item.visual_item = visual_item
            
    def draw_text(self):
        if self.text_item:
            self.scene.removeItem(self.text_item)
            
        self.text_item = EditableTextItem(self, self.text)
        self.text_item.setParentItem(self.graphics_item) 
        self.update_text_position()

    def update_text_position(self):
        if self.text_item and self.graphics_item:
            text_rect = self.text_item.boundingRect()
            text_x = self.width / 2 - text_rect.width() / 2
            text_y = self.height / 2 - text_rect.height() / 2
            self.text_item.setPos(text_x, text_y)

    def update_position(self, x, y):
        self.x = x
        self.y = y
        if self.graphics_item:
            self.graphics_item.setPos(x, y)
        self.update_text_position()

    def get_closest_point_on_bounds(self, target_point: QPointF) -> QPointF:
        center = self.center_point()
        dx = target_point.x() - center.x()
        dy = target_point.y() - center.y()
        
        if dx == 0 and dy == 0: return center
        
        t_horizontal, t_vertical = float('inf'), float('inf')
        half_width, half_height = self.width / 2, self.height / 2
        
        if dx != 0: t_horizontal = half_width / abs(dx)
        if dy != 0: t_vertical = half_height / abs(dy)
            
        t = min(t_horizontal, t_vertical)
        
        intersection_x = center.x() + t * dx
        intersection_y = center.y() + t * dy
        
        return QPointF(intersection_x, intersection_y)

class Connector(QGraphicsLineItem):
    def __init__(self, start_shape, end_shape, scene, label=""):
        super().__init__()
        self.start_shape = start_shape
        self.end_shape = end_shape
        self.scene = scene
        self.label = label
        
        self.setPen(QPen(QColor("gray"), 2, Qt.SolidLine, Qt.RoundCap, Qt.MiterJoin))
        
        self.arrow = QGraphicsPathItem(self)
        self.arrow.setPen(QPen(QColor("gray"), 2))
        self.arrow.setBrush(QBrush(QColor("gray")))
        
        self.label_item = QGraphicsTextItem(self.label, self)
        self.label_item.setFont(QFont("Arial", 8, QFont.Bold))
        
        self.update_position()
        scene.addItem(self)
        
    def mouseDoubleClickEvent(self, event):
        text, ok = QInputDialog.getText(self.scene.parent_widget, 
                                        "Edit Connector Label", 
                                        "Label (e.g., Yes/No):", 
                                        QLineEdit.Normal, 
                                        self.label)
        if ok:
            self.label = text
            self.label_item.setPlainText(self.label)
            self.update_position()
            self.scene.parent_widget.refresh_preview()
        
        super().mouseDoubleClickEvent(event)

    def update_position(self):
        center_start = self.start_shape.center_point()
        center_end = self.end_shape.center_point()
        
        start_pos = self.start_shape.get_closest_point_on_bounds(center_end)
        end_pos = self.end_shape.get_closest_point_on_bounds(center_start) 

        self.setLine(start_pos.x(), start_pos.y(), end_pos.x(), end_pos.y())
        self.update_arrowhead(start_pos, end_pos)
        self.update_label_position(start_pos, end_pos)
        
    def update_arrowhead(self, p1: QPointF, p2: QPointF):
        line_vec = p2 - p1
        line_length = math.sqrt(line_vec.x()**2 + line_vec.y()**2)
        
        if line_length < 1e-6: 
            self.arrow.setPath(QPainterPath())
            return

        arrow_size = 10.0
        end_position = p2
        angle = math.atan2(line_vec.y(), line_vec.x())
        
        path = QPainterPath()
        path.moveTo(end_position)
        
        A = end_position - QPointF(arrow_size * math.cos(angle - math.pi / 6), arrow_size * math.sin(angle - math.pi / 6))
        B = end_position - QPointF(arrow_size * math.cos(angle + math.pi / 6), arrow_size * math.sin(angle + math.pi / 6))
        
        path.lineTo(A)
        path.lineTo(B)
        path.closeSubpath()
        
        self.arrow.setPath(path)
        
    def update_label_position(self, p1: QPointF, p2: QPointF):
        if not self.label:
            self.label_item.setPlainText("")
            return
            
        mid_x = (p1.x() + p2.x()) / 2
        mid_y = (p1.y() + p2.y()) / 2
        
        label_rect = self.label_item.boundingRect()
        
        dx = p2.x() - p1.x()
        dy = p2.y() - p1.y()
        perp_x = -dy
        perp_y = dx
        
        norm = math.sqrt(perp_x**2 + perp_y**2)
        offset = 10 # distance from the line
        
        if norm > 0:
            offset_x = (perp_x / norm) * offset
            offset_y = (perp_y / norm) * offset
        else:
            offset_x, offset_y = offset, offset

        label_pos_x = mid_x + offset_x - label_rect.width() / 2
        label_pos_y = mid_y + offset_y - label_rect.height() / 2
        
        self.label_item.setPos(label_pos_x, label_pos_y)
        self.label_item.setPlainText(self.label)

# --- Main Designer Class ---

class FlowchartDesigner(QMainWindow):
    def __init__(self):
        super().__init__()
        self.shapes = []
        self.connectors = []
        self.selected_shape = None
        self.current_tool = "select"
        self.current_color = QColor("lightblue")
        
        self.connection_start_shape = None
        self.temp_line = None
        
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle("Flowchart Designer")
        self.setGeometry(100, 100, 1400, 900)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)
        
        # --- Left Panel - Controls (Simplified and Compact) ---
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        
        # --- Tools & Actions ---
        tools_group = QGroupBox("Tools & Actions")
        tools_layout = QGridLayout(tools_group)
        self.tool_group = QButtonGroup(self)
        
        tools = [
            ("Select", "select"),
            ("Connector", "connector"),
            ("Process", "rectangle"),
            ("Decision", "diamond"),
            ("Start/End", "start_end"),
            ("Input/Output", "input_output"),
            ("Ellipse", "ellipse"),
        ]
        
        row, col = 0, 0
        for text, tool in tools:
            radio = QRadioButton(text)
            radio.tool = tool
            if tool == "select":
                radio.setChecked(True)
            radio.toggled.connect(self.on_tool_changed)
            self.tool_group.addButton(radio)
            tools_layout.addWidget(radio, row, col)
            col += 1
            if col > 1:
                col = 0
                row += 1
                
        # Other Actions below the radio buttons
        row += 1
        tools_layout.addWidget(QPushButton("Load Project (JSON/MMD)", clicked=self.load_project_file), row, 0, 1, 2)
        row += 1
        tools_layout.addWidget(QPushButton("Delete Selected Shape", clicked=self.delete_selected_shape), row, 0, 1, 2)
        row += 1
        tools_layout.addWidget(QPushButton("Auto Layout (Layered)", clicked=self.auto_layout), row, 0, 1, 2)
        row += 1
        tools_layout.addWidget(QPushButton("Clear Canvas", clicked=self.clear_canvas), row, 0, 1, 2)
        
        scroll_layout.addWidget(tools_group)
        
        # --- New Shape Properties Panel ---
        props_group = QGroupBox("New Shape Properties")
        props_layout = QVBoxLayout(props_group)
        text_layout = QHBoxLayout()
        text_layout.addWidget(QLabel("Text:"))
        self.text_input = QLineEdit("Process")
        text_layout.addWidget(self.text_input)
        props_layout.addLayout(text_layout)
        color_layout = QHBoxLayout()
        color_layout.addWidget(QLabel("Color:"))
        self.color_button = QPushButton("Choose Color")
        self.color_button.clicked.connect(self.choose_color) 
        self.color_button.setStyleSheet(f"background-color: {self.current_color.name()}")
        color_layout.addWidget(self.color_button)
        props_layout.addLayout(color_layout)
        scroll_layout.addWidget(props_group)

        # --- Selected Shape Properties Panel ---
        self.selected_props_group = QGroupBox("Selected Shape Properties")
        self.selected_props_layout = QFormLayout(self.selected_props_group)
        
        # Text (Label) - Now QPlainTextEdit for multiline
        self.selected_text_input = QPlainTextEdit()
        self.selected_text_input.setMinimumHeight(60) 
        self.selected_text_input.textChanged.connect(self.update_selected_shape_property)
        self.selected_props_layout.addRow(QLabel("Label (Multiline):"), self.selected_text_input)

        # Color
        self.selected_color_button = QPushButton("Choose Color")
        self.selected_color_button.clicked.connect(self.choose_selected_color) 
        self.selected_props_layout.addRow(QLabel("Color:"), self.selected_color_button)

        # Shape Type
        self.selected_type_combo = QComboBox()
        self.selected_type_combo.addItems(["rectangle", "diamond", "start_end", "input_output", "ellipse"])
        self.selected_type_combo.currentTextChanged.connect(self.update_selected_shape_property)
        self.selected_props_layout.addRow(QLabel("Type:"), self.selected_type_combo)
        
        # Auto-Resize Button
        auto_resize_btn = QPushButton("Auto-Size to Fit Text (30px Padding)")
        auto_resize_btn.clicked.connect(self.auto_resize_selected_shape)
        self.selected_props_layout.addRow(auto_resize_btn)

        scroll_layout.addWidget(self.selected_props_group)
        self.selected_props_group.setVisible(False) # Hide until a shape is selected

        # --- Live Mermaid Code Editor Group ---
        mermaid_editor_group = QGroupBox("Live Mermaid Code Editor")
        editor_layout = QVBoxLayout(mermaid_editor_group)

        self.mermaid_code_editor = QPlainTextEdit()
        self.mermaid_code_editor.setPlaceholderText("Edit Mermaid Code here... (e.g., flowchart TD\\nA[Start] --> B(End))")
        editor_layout.addWidget(self.mermaid_code_editor)

        sync_button = QPushButton("Sync Code to Canvas")
        sync_button.clicked.connect(self.sync_mermaid_to_gui)
        editor_layout.addWidget(sync_button)

        scroll_layout.addWidget(mermaid_editor_group)
        
        # --- Export Panel (Moved down) ---
        export_group = QGroupBox("Export")
        export_layout = QGridLayout(export_group)
        
        export_layout.addWidget(QPushButton("Export Canvas (PNG/SVG)", clicked=self.export_canvas_image), 0, 0, 1, 2)
        export_layout.addWidget(QPushButton("Export Static Plot (PNG/SVG/JPG)", clicked=self.export_plot), 1, 0, 1, 2)
        export_layout.addWidget(QPushButton("Export Mermaid Code (*.mmd)", clicked=self.gui_to_mermaid_save), 2, 0, 1, 2)
        export_layout.addWidget(QPushButton("Export Mermaid Plot (PNG)", clicked=self.export_mermaid_image), 3, 0, 1, 2)
        export_layout.addWidget(QPushButton("Export JSON Project (*.json)", clicked=self.gui_to_json_save), 4, 0, 1, 2)
        export_layout.addWidget(QPushButton("Export Interactive HTML", clicked=self.export_interactive_html), 5, 0, 1, 2)
        
        scroll_layout.addWidget(export_group)

        # --- NEW: Author/Copyright Panel ---
        author_group = QGroupBox("Author Information")
        author_layout = QVBoxLayout(author_group)
        
        # Use HTML for multiline formatting and the copyright symbol
        copyright_text = QLabel("© 2025 Flowchart Designer<br>Developed by: <b>Pramod Kumar Yadav</b><br>Contact: pkyadav01234@gmail.com")
        copyright_text.setTextFormat(Qt.RichText) # Enable HTML formatting
        copyright_text.setAlignment(Qt.AlignCenter)
        author_layout.addWidget(copyright_text)
        
        scroll_layout.addWidget(author_group)
        
        # --- END NEW CONTENT ---


        scroll_layout.addStretch(1) # Push content up
        
        scroll_area.setWidget(scroll_content)
        left_layout.addWidget(scroll_area)
        
        # --- Canvas Area ---
        canvas_frame = QGroupBox("Design Canvas")
        canvas_layout = QVBoxLayout(canvas_frame)
        self.graphics_view = QGraphicsView()
        self.scene = QGraphicsScene(self)
        self.scene.parent_widget = self 
        self.graphics_view.setScene(self.scene)
        self.graphics_view.setRenderHint(QPainter.Antialiasing)
        self.graphics_view.setBackgroundBrush(QBrush(QColor(240, 240, 240)))
        canvas_layout.addWidget(self.graphics_view)
        
        # Add Canvas and Left Panel to splitter
        splitter.addWidget(left_panel)
        splitter.addWidget(canvas_frame)
        
        # --- Right Panel - Preview (Same as before) ---
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        preview_type_group = QGroupBox("Preview Selector & Options")
        preview_controls_layout = QVBoxLayout(preview_type_group)
        
        theme_layout = QHBoxLayout()
        theme_layout.addWidget(QLabel("Mermaid Theme:"))
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["default", "base", "dark", "forest"])
        self.theme_combo.setCurrentText("base")
        self.theme_combo.currentTextChanged.connect(self.refresh_preview)
        theme_layout.addWidget(self.theme_combo)
        preview_controls_layout.addLayout(theme_layout)
        
        preview_type_layout = QHBoxLayout()
        self.preview_group = QButtonGroup(self)
        preview_types = [
            ("Mermaid", "mermaid"),
            ("Interactive (PyVis)", "interactive"),
            ("Static (Matplotlib)", "static")
        ]
        
        for text, preview_type in preview_types:
            radio = QRadioButton(text)
            radio.preview_type = preview_type
            if preview_type == "mermaid":
                radio.setChecked(True)
            radio.toggled.connect(self.on_preview_type_changed)
            self.preview_group.addButton(radio)
            preview_type_layout.addWidget(radio)
            
        self.refresh_button = QPushButton("Refresh Preview")
        self.refresh_button.clicked.connect(self.refresh_preview)
        preview_type_layout.addWidget(self.refresh_button)
        preview_controls_layout.addLayout(preview_type_layout)
        
        self.pyvis_controls = QGroupBox("PyVis Options")
        self.pyvis_controls.setLayout(QVBoxLayout())
        self.physics_checkbox = QCheckBox("Enable Physics")
        self.physics_checkbox.setChecked(True)
        self.pyvis_controls.layout().addWidget(self.physics_checkbox)
        preview_controls_layout.addWidget(self.pyvis_controls)
        self.pyvis_controls.setVisible(False) 

        right_layout.addWidget(preview_type_group)
        
        preview_container = QGroupBox("Preview Output")
        preview_layout = QVBoxLayout(preview_container)
        self.preview_tabs = QTabWidget()
        
        self.mermaid_tab = QWidget()
        mermaid_layout = QVBoxLayout(self.mermaid_tab)
        self.mermaid_view = QWebEngineView()
        mermaid_layout.addWidget(self.mermaid_view)
        self.preview_tabs.addTab(self.mermaid_tab, "Mermaid")
        
        self.interactive_tab = QWidget()
        interactive_layout = QVBoxLayout(self.interactive_tab)
        self.interactive_view = QWebEngineView()
        interactive_layout.addWidget(self.interactive_view)
        self.preview_tabs.addTab(self.interactive_tab, "Interactive")
        
        self.static_tab = QWidget()
        static_layout = QVBoxLayout(self.static_tab)
        self.static_canvas = FigureCanvas(matplotlib.figure.Figure(figsize=(8, 6)))
        self.static_toolbar = NavigationToolbar(self.static_canvas, self)
        static_layout.addWidget(self.static_toolbar)
        static_layout.addWidget(self.static_canvas)
        self.preview_tabs.addTab(self.static_tab, "Static")
        
        preview_layout.addWidget(self.preview_tabs)
        right_layout.addWidget(preview_container)
        
        splitter.addWidget(right_panel)
        splitter.setSizes([250, 550, 600]) # Set initial widths for panels
        
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready. Select tool, add shapes, then connect. Double-click connectors to label.")
        
        self.scene.selectionChanged.connect(self.on_selection_changed)
        
        self.graphics_view.mousePressEvent = self.on_view_mouse_press
        self.graphics_view.mouseMoveEvent = self.on_view_mouse_move
        self.graphics_view.mouseReleaseEvent = self.on_view_mouse_release
        
        self.refresh_preview()
        
        self.delete_action = QShortcut(QKeySequence(Qt.Key_Delete), self)
        self.delete_action.activated.connect(self.delete_selected_shape)
    # --- File/Project Handling ---
    
    # Regex to capture: ID, shape definition part
    NODE_DEFINITION_PATTERN = re.compile(r'^\s*(\w+)\s*(?:\s*(.+?))?\s*$') 

    # Regex to capture connection parts
    CONN_PATTERN = re.compile(r'^\s*(\w+)(?:.*?)\s*[-=]+>\s*(?:\|(.*?)\|)?\s*(\w+)\s*(?:.*?)\s*$')

    def parse_definition(self, mermaid_id, full_def):
        text = mermaid_id
        shape_type = 'rectangle' # Default
        
        # Helper function to strip quotes from a string if present
        def strip_quotes(s):
            s = s.strip()
            if s.startswith('"') and s.endswith('"'):
                return s[1:-1].strip()
            return s.strip()

        if full_def.startswith('((') and full_def.endswith('))'):
            shape_type = 'ellipse'
            text = strip_quotes(full_def[2:-2])
        elif full_def.startswith('(') and full_def.endswith(')'):
            shape_type = 'start_end'
            text = strip_quotes(full_def[1:-1])
        elif full_def.startswith('{') and full_def.endswith('}'):
            shape_type = 'diamond'
            text = strip_quotes(full_def[1:-1])
        elif full_def.startswith('[') and full_def.endswith(']'):
            if full_def.startswith('[/') and full_def.endswith('/]'):
                shape_type = 'input_output'
                # FIX: Use the new robust quote stripping logic here
                text = strip_quotes(full_def[2:-2])
            else:
                shape_type = 'rectangle'
                text = strip_quotes(full_def[1:-1])
        elif full_def.startswith('["') and full_def.endswith('"]'): 
            shape_type = 'rectangle'
            text = full_def[2:-2].strip() # Text is already quoted, strip the outer ["]

        # If after parsing the text is empty, fall back to the ID
        return text if text else mermaid_id, shape_type


    def parse_mermaid_to_gui(self, mermaid_code: str):
        # Disconnect signal to prevent immediate refresh_preview call during auto_layout
        try:
             self.scene.selectionChanged.disconnect(self.on_selection_changed)
        except TypeError:
             pass 
        
        self.scene.clear()
        self.shapes = []
        self.connectors = []
        node_defs = {} 
        connections = [] 
        
        lines = [line.strip() for line in mermaid_code.split('\n') if line.strip() and not line.strip().startswith('%')]
        
        if not lines or not re.match(r'^flowchart\s+(TD|LR)', lines[0], re.I):
            QMessageBox.warning(self, "Parse Warning", "Mermaid file must start with 'flowchart TD' or 'flowchart LR'.")
            self.scene.selectionChanged.connect(self.on_selection_changed)
            self.refresh_preview()
            return
        
        # Pass 1: Collect ALL node definitions and connections
        for line in lines[1:]:
            
            conn_match = self.CONN_PATTERN.match(line)
            
            if conn_match:
                start_id = conn_match.group(1).strip()
                label = conn_match.group(2).strip() if conn_match.group(2) else ""
                end_id = conn_match.group(3).strip()
                connections.append((start_id, end_id, label))
            
            # Check for explicit node definitions on the line
            if not conn_match: 
                def_match = self.NODE_DEFINITION_PATTERN.match(line)
                if def_match:
                    mermaid_id = def_match.group(1).strip()
                    full_def = def_match.group(2) if def_match.group(2) else f"[{mermaid_id}]" 
                    text, shape_type = self.parse_definition(mermaid_id, full_def)
                    text = text.replace('\\n', '\n')
                    node_defs[mermaid_id] = {'text': text, 'type': shape_type}

            # Handle nodes defined inline (e.g., node1(text) in a connection)
            inline_defs = re.findall(r'(\w+)([()\[{}\/]+.+?[)\]{}\/]+)', line)
            for mermaid_id, full_def in inline_defs:
                text, shape_type = self.parse_definition(mermaid_id, full_def)
                if mermaid_id not in node_defs or (node_defs.get(mermaid_id) and node_defs[mermaid_id]['text'].replace('\n', '<br/>') == mermaid_id):
                    node_defs[mermaid_id] = {'text': text, 'type': shape_type}

        # Pass 2: Create Shapes for all used IDs
        shape_id_map = {}
        for i, (mermaid_id, def_data) in enumerate(node_defs.items()):
            text = def_data.get('text', mermaid_id)
            shape_type = def_data.get('type', 'rectangle')
            
            new_shape = Shape(self.scene, shape_type, 0, 0, text=text, shape_id=str(uuid.uuid4()))
            
            # Auto-resize after creating the shape
            new_shape.auto_resize_to_fit_text(padding=30)
            
            self.shapes.append(new_shape)
            shape_id_map[mermaid_id] = new_shape

        # Pass 3: Create Connectors
        for start_id, end_id, label in connections:
            if start_id in shape_id_map and end_id in shape_id_map:
                start_shape = shape_id_map[start_id]
                end_shape = shape_id_map[end_id]
                new_connector = Connector(start_shape, end_shape, self.scene, label=label)
                self.connectors.append(new_connector)

        if self.shapes:
             self.auto_layout()
        else:
             QMessageBox.warning(self, "Load Warning", "Could not identify any shapes from the Mermaid code.")

        # Reconnect signal
        self.scene.selectionChanged.connect(self.on_selection_changed)
        self.refresh_preview()
             
    # --- Flowchart Management ---
    
    def sync_mermaid_to_gui(self):
        mermaid_code = self.mermaid_code_editor.toPlainText()
        if not mermaid_code.strip():
            QMessageBox.warning(self, "Sync Warning", "Mermaid code editor is empty.")
            return

        reply = QMessageBox.question(self, 'Sync Code', 
                                   'Syncing will clear the current canvas design. Continue?',
                                   QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.No:
            return

        self.clear_canvas_internal() # Clear without user prompt
        
        try:
            self.parse_mermaid_to_gui(mermaid_code)
            self.status_bar.showMessage("Canvas updated from Mermaid code.")
        except Exception as e:
            QMessageBox.critical(self, "Mermaid Sync Error", f"Failed to parse Mermaid code: {e}")
            self.clear_canvas_internal() # Clear on failure to avoid half-parsed state
            self.refresh_preview() # Refresh to show clear state in previews

    def auto_layout(self):
        if not self.shapes:
            return
        
        # 1. Build a NetworkX graph
        G = nx.DiGraph()
        shape_map = {shape.id: shape for shape in self.shapes}
        
        for shape in self.shapes:
            G.add_node(shape.id)
            
        for connector in self.connectors:
            G.add_edge(connector.start_shape.id, connector.end_shape.id)
            
        # 2. Use NetworkX to determine layers (a simplified topological sort)
        try:
            layers = {}
            current_layer = 0
            unlayered_nodes = set(G.nodes())
            
            while unlayered_nodes:
                if current_layer == 0:
                    layer_nodes = [n for n in unlayered_nodes if not list(G.predecessors(n))]
                else:
                    layer_nodes = [n for n in unlayered_nodes if all(p in layers and layers[p] < current_layer for p in G.predecessors(n))]
                
                if not layer_nodes:
                    # Break if no more nodes can be placed (e.g., in case of cycles)
                    break 

                for node_id in layer_nodes:
                    layers[node_id] = current_layer
                
                unlayered_nodes -= set(layer_nodes)
                current_layer += 1
                
            # Fallback for remaining nodes (e.g., if there's a cycle)
            for i, node_id in enumerate(unlayered_nodes):
                layers[node_id] = current_layer + i 
                
        except Exception:
            layers = {shape.id: i for i, shape in enumerate(self.shapes)}


        # 3. Calculate Positions
        H_SEP = 150 
        V_SEP = 150 
        NODE_W = 100
        NODE_H = 60
        
        layer_width = {}
        layer_nodes_list = {}
        
        # Calculate max layer index
        max_layer_idx = max(layers.values()) if layers else 0
        
        for i in range(max_layer_idx + 1):
            nodes_in_layer = sorted([n for n, l in layers.items() if l == i])
            layer_nodes_list[i] = nodes_in_layer
            layer_width[i] = len(nodes_in_layer) * H_SEP - H_SEP + NODE_W if nodes_in_layer else 0
        
        # Handle case where all nodes are unlayered due to cycles and are assigned high layers
        if not layer_width and self.shapes:
             layer_width[0] = len(self.shapes) * H_SEP - H_SEP + NODE_W
             max_total_width = layer_width[0]
        else:
             max_total_width = max(layer_width.values()) if layer_width else NODE_W
             
        total_height = (max_layer_idx + 1) * V_SEP - V_SEP + NODE_H

        view_rect = self.graphics_view.viewport().rect()
        offset_x = view_rect.width() / 2 - max_total_width / 2
        offset_y = view_rect.height() / 2 - total_height / 2
        
        for layer_idx, nodes_in_layer in layer_nodes_list.items():
            num_nodes = len(nodes_in_layer)
            
            # Center the current layer horizontally
            layer_content_width = (num_nodes - 1) * H_SEP + NODE_W if num_nodes > 0 else 0
            start_x = (max_total_width - layer_content_width) / 2
            
            for i, node_id in enumerate(nodes_in_layer):
                x = start_x + i * H_SEP 
                y = layer_idx * V_SEP
                
                final_x = x + offset_x
                final_y = y + offset_y
                
                shape_map[node_id].update_position(final_x, final_y)
        
        self.update_all_connectors() 
        self.status_bar.showMessage("Layered auto-layout applied.")
        self.refresh_preview()

    # --- Selected Shape Property Handlers ---
    def auto_resize_selected_shape(self):
        if self.selected_shape:
            # Use a padding of 30 for breathing room
            self.selected_shape.auto_resize_to_fit_text(padding=30) 
            # Force update of properties panel text (if text changed on canvas)
            self.selected_text_input.setPlainText(self.selected_shape.text)
            self.status_bar.showMessage(f"Shape '{self.selected_shape.text.splitlines()[0].strip()}...' resized.")
            self.refresh_preview()

    def choose_selected_color(self):
        if self.selected_shape:
            color = QColorDialog.getColor(self.selected_shape.color, self, "Choose Shape Color")
            if color.isValid():
                self.selected_shape.color = color
                self.selected_shape.graphics_item.visual_item.setBrush(QBrush(color))
                self.selected_color_button.setStyleSheet(f"background-color: {color.name()}")
                self.refresh_preview()

    def update_selected_shape_property(self):
        if self.selected_shape:
            
            # Check for type change (from QComboBox)
            new_type = self.selected_type_combo.currentText()
            if new_type != self.selected_shape.type:
                self.selected_shape.type = new_type
                self.selected_shape.draw_shape_visual() 
                
            # Check for text change (from QPlainTextEdit)
            new_text = self.selected_text_input.toPlainText() # Get multiline text
            if new_text != self.selected_shape.text:
                self.selected_shape.text = new_text
                
                # Update the text item on the canvas immediately 
                self.selected_shape.text_item.setPlainText(new_text)
                
                # Auto-resize the shape to fit the new (possibly multiline) text
                self.selected_shape.auto_resize_to_fit_text(padding=30) 
                
            # Redraw to update selection border and trigger preview refresh
            self.selected_shape.draw()
            self.refresh_preview()

    # --- Export/Preview Functionality ---
    
    def export_canvas_image(self):
        if not self.shapes:
            QMessageBox.warning(self, "Export Warning", "No shapes on the canvas to export.")
            return

        formats = "PNG Image (*.png);;SVG Vector (*.svg)"
        file_path, selected_filter = QFileDialog.getSaveFileName(
            self, "Export Design Canvas as Image", "flowchart_canvas", formats
        )

        if not file_path:
            return

        # 1. Determine the bounding box of all items
        scene_rect = self.scene.itemsBoundingRect()
        # Add a small margin
        margin = 20
        scene_rect.setRect(
            scene_rect.x() - margin, 
            scene_rect.y() - margin, 
            scene_rect.width() + 2 * margin, 
            scene_rect.height() + 2 * margin
        )

        try:
            painter = QPainter()

            if "PNG" in selected_filter:
                # Export as PNG
                image = QImage(scene_rect.size().toSize(), QImage.Format_ARGB32)
                image.fill(Qt.white)
                
                painter.begin(image)
                painter.setRenderHint(QPainter.Antialiasing)
                
                # Translate painter so that scene_rect origin becomes (0,0) in the image
                painter.translate(-scene_rect.x(), -scene_rect.y())
                self.scene.render(painter, target=scene_rect, source=scene_rect)
                painter.end()
                
                image.save(file_path, "PNG")

            elif "SVG" in selected_filter:
                # Export as SVG using QPainter
                
                generator = QSvgGenerator()
                generator.setFileName(file_path)
                generator.setSize(scene_rect.size().toSize())
                generator.setViewBox(scene_rect)
                
                painter.begin(generator)
                painter.setRenderHint(QPainter.Antialiasing)
                self.scene.render(painter)
                painter.end()
                
            else:
                QMessageBox.warning(self, "Export Failed", "Selected format is not supported for canvas export.")
                return

            QMessageBox.information(self, "Export Successful", f"Design Canvas exported to:\n{file_path}")

        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export canvas image: {e}")
            
    def export_mermaid_image(self):
        if not self.shapes:
            QMessageBox.warning(self, "Export Warning", "No shapes to export.")
            return

        self.preview_tabs.setCurrentIndex(0)
        self.refresh_preview() 
        
        file_path, filter_name = QFileDialog.getSaveFileName(
            self, "Export Mermaid Plot as Image", "flowchart_mermaid.png", "PNG Image (*.png)"
        )
        
        if not file_path:
            return
        
        # Grab the WebEngineView content and save it
        self.mermaid_view.grab().save(file_path)
        QMessageBox.information(self, "Export Successful", f"Mermaid plot exported to:\n{file_path}")

    def generate_id_map(self):
        """Creates a sequential ID map (UUID -> nodeN) for clean exports."""
        id_map = {}
        for i, shape in enumerate(self.shapes):
            id_map[shape.id] = f"node{i}"
        return id_map
    
    def generate_mermaid_code(self):
        if not self.shapes:
            return "flowchart TD\n    %% No shapes on canvas"
            
        id_map = self.generate_id_map()
        lines = ["flowchart TD"]
        
        def clean_text_for_mermaid_io(text):
            """Strips quotes and excessive whitespace for Input/Output generation."""
            t = text.strip()
            if t.startswith('"') and t.endswith('"'):
                t = t[1:-1].strip()
            return t.replace('\n', '\\n')

        shape_to_mermaid_map = {
            "rectangle": lambda t: f"[\"{clean_text_for_mermaid_io(t)}\"]", # Explicitly quote for safety
            "diamond": lambda t: f"{{\"{clean_text_for_mermaid_io(t)}\"}}", 
            "ellipse": lambda t: f"((\"{clean_text_for_mermaid_io(t)}\"))",
            "start_end": lambda t: f"(\"{clean_text_for_mermaid_io(t)}\")",
            # FIX: Use the cleaned text helper for Input/Output generation
            "input_output": lambda t: f"[/\"{clean_text_for_mermaid_io(t)}\"/]",
        }
        
        for shape in self.shapes:
            node_id = id_map[shape.id]
            # Escape inner quotes for Mermaid
            # text_label = shape.text.replace('"', '"') 
            text_label = shape.text.replace('\n', '\n') 

            syntax_func = shape_to_mermaid_map.get(shape.type, shape_to_mermaid_map["rectangle"])
            mermaid_syntax = node_id + syntax_func(text_label)
            lines.append(f"    {mermaid_syntax}")
            
        for connector in self.connectors:
            id1 = id_map[connector.start_shape.id]
            id2 = id_map[connector.end_shape.id]
            
            # The standard labeled connector format is -->|label|
            label_part = f"|{connector.label}|" if connector.label else ""
            lines.append(f"    {id1} -->{label_part} {id2}")
        
        return "\n".join(lines)

    def generate_mermaid_preview(self):
        mermaid_code = self.generate_mermaid_code()
        theme = self.theme_combo.currentText()
        
        if not mermaid_code or "No shapes on canvas" in mermaid_code:
            html_content = self._get_placeholder_html("Mermaid Preview", "No shapes to preview. Add some shapes to the canvas.")
            self.mermaid_view.setHtml(html_content)
            return

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Mermaid Preview</title>
            <script src="https://cdn.jsdelivr.net/npm/mermaid@9.1.7/dist/mermaid.min.js"></script>
            <script>
                mermaid.initialize({{ 
                    startOnLoad: true, 
                    theme: '{theme}', 
                    flowchart: {{
                        useMaxWidth: true,
                        htmlLabels: true,
                        curve: 'basis'
                    }}
                }});
            </script>
            <style>
                body {{
                    margin: 0;
                    padding: 20px;
                    background: white;
                    font-family: Arial, sans-serif;
                }}
                .mermaid {{
                    text-align: center;
                    display: block; 
                }}
            </style>
        </head>
        <body>
            <div class="mermaid">
{mermaid_code}
            </div>
        </body>
        </html>
        """
        
        temp_dir = tempfile.gettempdir()
        self.mermaid_view.setHtml(html_content, QUrl.fromLocalFile(os.path.join(temp_dir, "temp.html")))
        self.preview_tabs.setCurrentIndex(0)
    
    def gui_to_mermaid_save(self):
        mermaid_code = self.generate_mermaid_code()
        
        if not self.shapes:
            QMessageBox.warning(self, "Warning", "No shapes to convert!")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(self, "Export Mermaid File", "flowchart.mmd", "Mermaid Files (*.mmd);;Text Files (*.txt);;All Files (*)")
        
        if file_path:
            try:
                with open(file_path, 'w') as f:
                    f.write(mermaid_code)
                QMessageBox.information(self, "Export Successful", f"Mermaid code exported to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Failed to save file: {e}")

    def gui_to_json_save(self):
        if not self.shapes:
            QMessageBox.warning(self, "Warning", "No shapes to convert!")
            return
        
        data = {"nodes": [], "connections": []}
        id_map = self.generate_id_map()
        
        for shape in self.shapes:
            data["nodes"].append({
                "id": id_map[shape.id],
                "label": shape.text,
                "type": shape.type,
                "x": shape.x,
                "y": shape.y,
                "width": shape.width,
                "height": shape.height,
                "color": shape.color.name()
            })

        for connector in self.connectors:
            data["connections"].append({
                "start_id": id_map[connector.start_shape.id],
                "end_id": id_map[connector.end_shape.id],
                "label": connector.label
            })
        
        json_data = json.dumps(data, indent=2)
        
        file_path, _ = QFileDialog.getSaveFileName(self, "Export JSON Project", "flowchart.json", "JSON Files (*.json);;All Files (*)")
        
        if file_path:
            try:
                with open(file_path, 'w') as f:
                    f.write(json_data)
                QMessageBox.information(self, "Export Successful", f"Project JSON exported to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Failed to save file: {e}")
    
    def choose_color(self):
        color = QColorDialog.getColor(self.current_color, self, "Choose Shape Color")
        if color.isValid():
            self.current_color = color
            self.color_button.setStyleSheet(f"background-color: {color.name()}")

    def on_preview_type_changed(self):
        radio = self.preview_group.checkedButton()
        preview_type = radio.preview_type if radio else "mermaid"
        self.pyvis_controls.setVisible(preview_type == "interactive")
        self.refresh_preview()

    def on_tool_changed(self):
        self.clear_temp_connection()
        radio = self.tool_group.checkedButton()
        if radio:
            self.current_tool = radio.tool
            self.status_bar.showMessage(f"Tool: {self.current_tool}")

    def on_selection_changed(self):
        selected_items = self.scene.selectedItems()
        
        # Deselect all
        for shape in self.shapes:
            if shape.selected:
                if shape.graphics_item and shape.graphics_item.scene() == self.scene: 
                    shape.selected = False
                    shape.draw()
                elif shape.selected: 
                    shape.selected = False
                    
        self.selected_shape = None 
        self.selected_props_group.setVisible(False) # Hide properties panel by default

        if selected_items:
            for item in selected_items:
                if isinstance(item, CustomGraphicsItem):
                    self.selected_shape = item.shape_obj
                    self.selected_shape.selected = True
                    self.selected_shape.draw() 
                    
                    # NEW: Update the properties panel
                    self.selected_props_group.setVisible(True)
                    # Temporarily block signals to avoid triggering update_selected_shape_property 
                    self.selected_text_input.blockSignals(True)
                    self.selected_type_combo.blockSignals(True) 
                    
                    # Use setPlainText for QPlainTextEdit
                    self.selected_text_input.setPlainText(self.selected_shape.text)
                    self.selected_type_combo.setCurrentText(self.selected_shape.type)
                    self.selected_color_button.setStyleSheet(f"background-color: {self.selected_shape.color.name()}")
                    
                    self.selected_text_input.blockSignals(False)
                    self.selected_type_combo.blockSignals(False) 
                    
                    return 
    
    def clear_canvas_internal(self):
        # Disconnect and clear without the user prompt for internal use (like sync_mermaid_to_gui)
        try:
            self.scene.selectionChanged.disconnect(self.on_selection_changed)
        except TypeError:
            pass 
            
        self.scene.clear()
        self.shapes = []
        self.connectors = []
        self.selected_shape = None
        self.selected_props_group.setVisible(False)
        self.mermaid_code_editor.setPlainText("flowchart TD\n    %% No shapes on canvas")
        
        self.scene.selectionChanged.connect(self.on_selection_changed)

    def clear_canvas(self):
        reply = QMessageBox.question(self, 'Clear Canvas', 
                                   'Clear all shapes and connectors?',
                                   QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.clear_canvas_internal()
            self.status_bar.showMessage("Canvas cleared")
            self.refresh_preview()
            
    def load_project_file(self):
        file_path, filter_name = QFileDialog.getOpenFileName(
            self, "Load Flowchart Project", "", 
            "JSON Project Files (*.json);;Mermaid Files (*.mmd *.txt);;All Files (*)"
        )
        if not file_path:
            return
        
        self.clear_canvas_internal()

        try:
            with open(file_path, 'r') as f:
                content = f.read()
            
            if file_path.lower().endswith('.json'):
                self.parse_json_to_gui(content)
            elif file_path.lower().endswith(('.mmd', '.txt')):
                self.parse_mermaid_to_gui(content)
            
            self.status_bar.showMessage(f"Project loaded from {Path(file_path).name}")
            # Refresh preview called inside parse_mermaid_to_gui/parse_json_to_gui
            # self.refresh_preview() 

        except Exception as e:
            QMessageBox.critical(self, "Load Error", f"Failed to load file: {e}")
            self.clear_canvas_internal() # Ensure a clean slate on failure
            self.refresh_preview() # Refresh to show clear state in previews
            
    def parse_json_to_gui(self, json_data: str):
        data = json.loads(json_data)
        self.shapes = []
        self.connectors = []
        shape_id_map = {}
        
        for node_data in data.get("nodes", []):
            color = QColor(node_data.get("color", "#ADD8E6")) 
            
            new_shape = Shape(
                self.scene,
                node_data.get("type", "rectangle"),
                node_data.get("x", 100),
                node_data.get("y", 100),
                width=node_data.get("width", 100),
                height=node_data.get("height", 60),
                text=node_data.get("label", "Node"),
                shape_id=str(uuid.uuid4()), 
                color=color
            )
            self.shapes.append(new_shape)
            shape_id_map[node_data.get("id")] = new_shape 
            
        for conn_data in data.get("connections", []):
            start_id = conn_data.get("start_id")
            end_id = conn_data.get("end_id")
            label = conn_data.get("label", "")
            
            if start_id in shape_id_map and end_id in shape_id_map:
                start_shape = shape_id_map[start_id]
                end_shape = shape_id_map[end_id]
                new_connector = Connector(start_shape, end_shape, self.scene, label=label)
                self.connectors.append(new_connector)
                
        if self.shapes:
             self.auto_layout()
        else:
             QMessageBox.warning(self, "Load Warning", "JSON file is empty or formatted incorrectly.")
        
        self.refresh_preview() # Final refresh after layout
             
    def update_all_connectors(self):
        for connector in self.connectors:
            connector.update_position()
            
    def delete_selected_shape(self):
        if not self.selected_shape or self.selected_shape not in self.shapes:
            QMessageBox.warning(self, "Delete Shape", "No shape is currently selected.")
            return

        reply = QMessageBox.question(self, 'Delete Shape', 
                                   f'Delete shape "{self.selected_shape.text}"?',
                                   QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            shape_to_delete = self.selected_shape
            
            connectors_to_remove = [c for c in self.connectors if c.start_shape == shape_to_delete or c.end_shape == shape_to_delete]
            for connector in connectors_to_remove:
                self.scene.removeItem(connector)
                if connector in self.connectors:
                    self.connectors.remove(connector)

            if shape_to_delete.graphics_item:
                self.scene.removeItem(shape_to_delete.graphics_item)
            
            self.shapes.remove(shape_to_delete)
            self.selected_shape = None
            self.selected_props_group.setVisible(False) # Hide properties panel
            
            self.status_bar.showMessage("Shape deleted.")
            self.refresh_preview()
            
    def get_current_preview_type(self):
        radio = self.preview_group.checkedButton()
        return radio.preview_type if radio else "mermaid"
        
    def refresh_preview(self):
        preview_type = self.get_current_preview_type()
        
        # NEW: Update the live editor on every refresh (GUI change)
        mermaid_code = self.generate_mermaid_code()
        # Only update if the content is different to avoid cursor jump/recursion
        if self.mermaid_code_editor.toPlainText().strip() != mermaid_code.strip():
            self.mermaid_code_editor.setPlainText(mermaid_code)
        
        # Update graphical previews
        if preview_type == "mermaid":
            self.generate_mermaid_preview()
        elif preview_type == "interactive":
            self.generate_interactive_preview()
        elif preview_type == "static":
            self.generate_static_preview()
            
    def find_shape_at_pos(self, scene_pos):
        items = self.scene.items(scene_pos)
        for item in items:
            if isinstance(item, CustomGraphicsItem):
                return item.shape_obj
        return None
        
    def clear_temp_connection(self):
        if self.temp_line:
            self.scene.removeItem(self.temp_line)
            self.temp_line = None
        self.connection_start_shape = None
    
    def on_view_mouse_press(self, event):
        scene_pos = self.graphics_view.mapToScene(event.pos())
        
        if self.current_tool in ["rectangle", "diamond", "ellipse", "start_end", "input_output"]:
            if event.button() == Qt.LeftButton:
                new_shape = Shape(
                    self.scene,
                    self.current_tool,
                    scene_pos.x() - 50, 
                    scene_pos.y() - 30, 
                    text=self.text_input.text(),
                    color=self.current_color
                )
                self.shapes.append(new_shape)
                self.refresh_preview()
        
        elif self.current_tool == "connector":
            start_shape = self.find_shape_at_pos(scene_pos)
            if start_shape:
                self.connection_start_shape = start_shape
                center = start_shape.center_point()
                
                self.temp_line = QGraphicsLineItem(center.x(), center.y(), center.x(), center.y())
                self.temp_line.setPen(QPen(QColor("blue"), 2, Qt.DashLine))
                self.scene.addItem(self.temp_line)
        
        QGraphicsView.mousePressEvent(self.graphics_view, event)

    def on_view_mouse_move(self, event):
        scene_pos = self.graphics_view.mapToScene(event.pos())
        
        if self.temp_line and self.connection_start_shape:
            start_point = self.connection_start_shape.get_closest_point_on_bounds(scene_pos)
            self.temp_line.setLine(start_point.x(), start_point.y(), scene_pos.x(), scene_pos.y())
        
        QGraphicsView.mouseMoveEvent(self.graphics_view, event)

    def on_view_mouse_release(self, event):
        scene_pos = self.graphics_view.mapToScene(event.pos())

        if self.current_tool == "connector" and self.connection_start_shape:
            end_shape = self.find_shape_at_pos(scene_pos)

            if end_shape and end_shape != self.connection_start_shape:
                new_connector = Connector(self.connection_start_shape, end_shape, self.scene)
                self.connectors.append(new_connector)
                self.status_bar.showMessage(f"Connected {self.connection_start_shape.text} to {end_shape.text}")
                self.refresh_preview()
            
            self.clear_temp_connection()
        
        QGraphicsView.mouseReleaseEvent(self.graphics_view, event)
        
    def generate_interactive_preview(self):
        if not self.shapes:
            html_content = self._get_placeholder_html("Interactive Preview", "No shapes to preview.")
            self.interactive_view.setHtml(html_content)
            return
        
        try:
            from pyvis.network import Network
            net = Network(height="600px", width="100%", bgcolor="#ffffff", font_color="black", directed=True, notebook=False, cdn_resources='remote')
            net.toggle_physics(self.physics_checkbox.isChecked())
            id_map = self.generate_id_map() 

            for shape in self.shapes:
                shape_map = {'rectangle': 'box', 'diamond': 'diamond', 'ellipse': 'ellipse', 'start_end': 'box', 'input_output': 'box'}
                net.add_node(id_map[shape.id], label=shape.text, shape=shape_map.get(shape.type, 'box'),
                    color=shape.color.name(), font={'size': 14}, margin=10)
            
            for connector in self.connectors:
                net.add_edge(id_map[connector.start_shape.id], id_map[connector.end_shape.id], label=connector.label)

            temp_path = Path(tempfile.gettempdir()) / "pyvis_temp.html"
            net.save_graph(str(temp_path))
            self.interactive_view.setUrl(QUrl.fromLocalFile(str(temp_path)))
            self.preview_tabs.setCurrentIndex(1)
        except Exception as e:
            error_html = self._get_error_html("Error generating interactive preview", str(e))
            self.interactive_view.setHtml(error_html)
    
    def generate_static_preview(self):
        if not self.shapes:
            self.static_canvas.figure.clear()
            self.static_canvas.draw()
            self.preview_tabs.setCurrentIndex(2) 
            return
        
        try:
            G = nx.DiGraph()
            id_map = self.generate_id_map()
            for shape in self.shapes:
                G.add_node(id_map[shape.id], label=shape.text, color=shape.color.name(), type=shape.type)
            
            edge_labels = {}
            for connector in self.connectors:
                u = id_map[connector.start_shape.id]
                v = id_map[connector.end_shape.id]
                G.add_edge(u, v)
                if connector.label:
                    edge_labels[(u, v)] = connector.label
            
            fig = self.static_canvas.figure
            fig.clear()
            ax = fig.add_subplot(111)
            
            pos = nx.spring_layout(G, k=3, iterations=50)
            node_colors = [G.nodes[node].get('color', 'lightblue') for node in G.nodes()]
            
            nx.draw_networkx_nodes(G, pos, node_color=node_colors, node_size=2500, ax=ax, alpha=0.9, edgecolors='black', linewidths=1)
            nx.draw_networkx_edges(G, pos, ax=ax, edge_color='gray', arrows=True, arrowsize=20, arrowstyle='->')
            
            labels = {node: G.nodes[node].get('label', '') for node in G.nodes()}
            nx.draw_networkx_labels(G, pos, labels, font_size=10, ax=ax, font_weight='bold')
            
            nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_color='black', font_size=9, ax=ax)
            
            ax.set_title("Flowchart Preview (Static)", fontsize=14, fontweight='bold')
            ax.axis('off')
            fig.tight_layout()
            
            self.static_canvas.draw()
            self.preview_tabs.setCurrentIndex(2) 
                
        except Exception as e:
            QMessageBox.critical(self, "Static Preview Error", f"Error creating static preview: {e}")
            
    def export_plot(self):
        if not self.shapes:
            QMessageBox.warning(self, "Export Warning", "No shapes to export.")
            return

        self.generate_static_preview() 
        formats = "PNG Image (*.png);;JPEG Image (*.jpg *.jpeg);;SVG File (*.svg)"
        file_path, filter_name = QFileDialog.getSaveFileName(self, "Export Static Plot", "flowchart_static", formats)

        if file_path:
            try:
                figure = self.static_canvas.figure
                
                if 'PNG' in filter_name:
                    figure.savefig(file_path, format='png', dpi=300)
                elif 'JPEG' in filter_name:
                    figure.savefig(file_path, format='jpeg', dpi=300)
                elif 'SVG' in filter_name:
                    figure.savefig(file_path, format='svg')
                else:
                    figure.savefig(file_path, format='png', dpi=300)
                    
                QMessageBox.information(self, "Export Successful", f"Plot exported to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Failed to export plot: {e}")

    def export_interactive_html(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Export Interactive HTML", "flowchart.html", "HTML Files (*.html);;All Files (*)")
        
        if not file_path:
            return
        
        try:
            from pyvis.network import Network
            net = Network(height="800px", width="100%", bgcolor="#ffffff", font_color="black", directed=True, notebook=False, cdn_resources='remote')
            net.toggle_physics(self.physics_checkbox.isChecked())
            id_map = self.generate_id_map()

            for shape in self.shapes:
                shape_map = {'rectangle': 'box', 'diamond': 'diamond', 'ellipse': 'ellipse', 'start_end': 'box', 'input_output': 'box'}
                net.add_node(id_map[shape.id], label=shape.text, shape=shape_map.get(shape.type, 'box'),
                    color=shape.color.name(), font={'size': 14}, margin=10)
            
            for connector in self.connectors:
                net.add_edge(id_map[connector.start_shape.id], id_map[connector.end_shape.id], label=connector.label)

            net.save_graph(file_path)
            QMessageBox.information(self, "Export Successful", f"Interactive HTML exported to:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export interactive HTML: {e}")
            
    def _get_placeholder_html(self, title, message):
        return f"""
        <!DOCTYPE html><html><head><meta charset="utf-8"><title>{title}</title><style>body {{ display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; font-family: Arial, sans-serif; background: #f5f5f5;}}.placeholder {{ text-align: center; color: #666; font-size: 18px;}}</style></head><body><div class="placeholder">{message}</div></body></html>
        """

    def _get_error_html(self, title, message):
        return f"""
        <!DOCTYPE html><html><head><meta charset="utf-8"><title>Error</title><style>body {{ display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; font-family: Arial, sans-serif; background: #f5f5f5;}}.error {{ text-align: center; color: #d32f2f; font-size: 16px; padding: 20px; background: #ffebee; border: 1px solid #f44336; border-radius: 5px;}}</style></head><body><div class="error"><h3>{title}</h3><p>{message}</p></div></body></html>
        """


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    window = FlowchartDesigner()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()