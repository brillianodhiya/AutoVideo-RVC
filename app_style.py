def dapatkan_style_sheet():
    """
    Mengembalikan QSS (Qt Style Sheets) stylesheet premium bertema Modern Dark Slate / Minimalist.
    Desain natural, bersih, dan profesional (terinspirasi dari Linear dan Supabase).
    """
    return """
    /* ==================================================================== */
    /* MASTER APPLICATION STYLE - MINIMALIST DARK SLATE                     */
    /* ==================================================================== */
    
    QMainWindow {
        background-color: #09090b;
    }
    
    QWidget {
        color: #f4f4f5;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        font-size: 13px;
    }
    
    /* ---------------------------------------------------- */
    /* LABELS & TYPOGRAPHY                                 */
    /* ---------------------------------------------------- */
    QLabel {
        color: #e4e4e7;
    }
    
    QLabel#header_label {
        font-size: 22px;
        font-weight: 700;
        color: #ffffff;
        background: transparent;
        letter-spacing: -0.5px;
    }
    
    QLabel#sub_header_label {
        font-size: 13px;
        color: #a1a1aa;
        background: transparent;
    }
    
    QLabel#section_title {
        font-size: 14px;
        font-weight: 600;
        color: #ffffff;
        background: transparent;
        border-bottom: 1px solid #27272a;
        padding-bottom: 6px;
        margin-bottom: 10px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    /* ---------------------------------------------------- */
    /* CARDS & CONTAINERS                                   */
    /* ---------------------------------------------------- */
    QFrame#glass_card {
        background-color: #18181b;
        border: 1px solid #27272a;
        border-radius: 8px;
    }
    
    /* ---------------------------------------------------- */
    /* INPUT FIELDS (LINEEDIT, SPINBOX, TEXTEDIT, COMBOBOX) */
    /* ---------------------------------------------------- */
    QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {
        background-color: #09090b;
        border: 1px solid #27272a;
        border-radius: 6px;
        padding: 8px 10px;
        color: #f4f4f5;
        selection-background-color: #312e81;
    }
    
    QLineEdit:focus, QTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
        border: 1px solid #6366f1;
        background-color: #09090b;
    }
    
    QComboBox::drop-down {
        border: none;
        width: 20px;
    }
    
    QComboBox QAbstractItemView {
        background-color: #18181b;
        border: 1px solid #27272a;
        selection-background-color: #312e81;
        selection-color: #ffffff;
        color: #e4e4e7;
        border-radius: 6px;
    }
    
    /* ---------------------------------------------------- */
    /* BUTTONS                                              */
    /* ---------------------------------------------------- */
    QPushButton {
        background-color: #18181b;
        border: 1px solid #27272a;
        border-radius: 6px;
        padding: 8px 14px;
        color: #f4f4f5;
        font-weight: 500;
    }
    
    QPushButton:hover {
        background-color: #27272a;
        border: 1px solid #3f3f46;
    }
    
    QPushButton:pressed {
        background-color: #09090b;
    }
    
    QPushButton#gradient_button {
        background-color: #4f46e5;
        border: 1px solid #6366f1;
        border-radius: 6px;
        padding: 10px 16px;
        color: #ffffff;
        font-size: 13px;
        font-weight: 600;
    }
    
    QPushButton#gradient_button:hover {
        background-color: #5c54f4;
        border: 1px solid #818cf8;
    }
    
    QPushButton#gradient_button:pressed {
        background-color: #4338ca;
    }
    
    QPushButton#danger_button {
        background-color: #450a0a;
        border: 1px solid #7f1d1d;
        border-radius: 6px;
        color: #fca5a5;
        font-weight: 500;
    }
    
    QPushButton#danger_button:hover {
        background-color: #7f1d1d;
        border: 1px solid #b91c1c;
    }
    
    /* ---------------------------------------------------- */
    /* TABS WIDGET                                          */
    /* ---------------------------------------------------- */
    QTabWidget::pane {
        border: 1px solid #27272a;
        background-color: #18181b;
        border-radius: 8px;
        top: -1px;
    }
    
    QTabBar::tab {
        background-color: transparent;
        border: none;
        border-bottom: 2px solid transparent;
        padding: 10px 16px;
        color: #a1a1aa;
        font-weight: 500;
        font-size: 13px;
        margin-right: 4px;
    }
    
    QTabBar::tab:hover {
        color: #f4f4f5;
        background-color: #18181b;
    }
    
    QTabBar::tab:selected {
        color: #ffffff;
        border-bottom: 2px solid #6366f1;
        background-color: #18181b;
    }
    
    /* ---------------------------------------------------- */
    /* SLIDERS                                              */
    /* ---------------------------------------------------- */
    QSlider::groove:horizontal {
        height: 4px;
        background: #27272a;
        border-radius: 2px;
    }
    
    QSlider::handle:horizontal {
        background: #ffffff;
        border: 1px solid #3f3f46;
        width: 14px;
        height: 14px;
        margin-top: -5px;
        margin-bottom: -5px;
        border-radius: 7px;
    }
    
    QSlider::handle:horizontal:hover {
        background: #f4f4f5;
        border: 1px solid #6366f1;
    }
    
    /* ---------------------------------------------------- */
    /* TABLE WIDGET                                         */
    /* ---------------------------------------------------- */
    QTableWidget {
        background-color: #18181b;
        border: 1px solid #27272a;
        border-radius: 6px;
        gridline-color: #27272a;
        color: #e4e4e7;
        selection-background-color: #312e81;
        selection-color: #ffffff;
    }
    
    QHeaderView::section {
        background-color: #27272a;
        padding: 8px;
        border: none;
        border-bottom: 1px solid #3f3f46;
        color: #ffffff;
        font-weight: 600;
    }
    
    QTableWidget::item {
        padding: 6px;
    }
    
    QTableWidget QComboBox, QTableWidget QSpinBox, QTableWidget QLineEdit {
        background-color: #09090b;
        border: 1px solid #27272a;
        border-radius: 4px;
        padding: 2px 6px;
        margin: 2px;
        color: #f4f4f5;
    }
    
    QTableWidget QComboBox:focus, QTableWidget QSpinBox:focus, QTableWidget QLineEdit:focus {
        border: 1px solid #6366f1;
    }
    
    /* ---------------------------------------------------- */
    /* PROGRESS BAR                                         */
    /* ---------------------------------------------------- */
    QProgressBar {
        border: 1px solid #27272a;
        border-radius: 6px;
        text-align: center;
        background-color: #09090b;
        color: #ffffff;
        font-weight: 600;
    }
    
    QProgressBar::chunk {
        background-color: #4f46e5;
        border-radius: 4px;
    }
    
    /* ---------------------------------------------------- */
    /* THIN MODERN SCROLLBAR                                */
    /* ---------------------------------------------------- */
    QScrollBar:vertical {
        border: none;
        background: transparent;
        width: 8px;
        margin: 0px;
    }
    
    QScrollBar::handle:vertical {
        background: #27272a;
        min-height: 20px;
        border-radius: 4px;
    }
    
    QScrollBar::handle:vertical:hover {
        background: #3f3f46;
    }
    
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        height: 0px;
    }

    /* ---------------------------------------------------- */
    /* MODERN SIDEBAR NAVIGATION SYSTEM                     */
    /* ---------------------------------------------------- */
    QFrame#sidebar_frame {
        background-color: #09090b;
        border-right: 1px solid #1c1c1e;
    }
    
    QPushButton#sidebar_nav_btn {
        background-color: transparent;
        border: none;
        border-radius: 8px;
        padding: 10px 16px;
        color: #a1a1aa;
        font-weight: 500;
        font-size: 13px;
        text-align: left;
    }
    
    QPushButton#sidebar_nav_btn:hover {
        background-color: #18181b;
        color: #f4f4f5;
    }
    
    QPushButton#sidebar_nav_btn[active="true"] {
        background-color: #2563eb;
        color: #ffffff;
        font-weight: 600;
    }
    """
