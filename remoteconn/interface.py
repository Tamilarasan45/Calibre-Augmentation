from PyQt5.Qt import QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem, QComboBox, QHBoxLayout, pyqtSignal
from calibre.gui2 import error_dialog

class RemoteConnDialog(QDialog):
    name = 'Remote Conn'
    dont_add_to = frozenset([''])
    fetchRequested = pyqtSignal(str) # Signal to fetch a ebook list
    openBookRequested = pyqtSignal(dict) # Signal for requesting to open a book
    statusUpdated = pyqtSignal(dict) # Signal for updating book status

    def __init__(self, gui, parent=None):
        super(RemoteConnDialog, self).__init__(parent)
        self.gui = gui
        self.setWindowTitle('Remote Connection')
        self.setGeometry(100, 100, 600, 400)
        self.layout = QVBoxLayout(self)

        self.cid_label = QLabel('Enter IPFS CID:', self)
        self.layout.addWidget(self.cid_label)

        self.cid_input = QLineEdit(self)
        self.layout.addWidget(self.cid_input)

        self.fetch_button = QPushButton('Fetch', self)
        self.fetch_button.clicked.connect(self.fetch_file)
        self.layout.addWidget(self.fetch_button)

        self.filter_layout = QHBoxLayout()
        self.filter_label = QLabel('Filter by Status:', self)
        self.filter_layout.addWidget(self.filter_label)

        self.filter_combo = QComboBox(self)
        self.filter_combo.addItems(['All', 'READ', 'WANT-TO-READ', 'READING', 'COMPLETE'])
        self.filter_combo.currentIndexChanged.connect(self.filter_status)
        self.filter_layout.addWidget(self.filter_combo)

        self.layout.addLayout(self.filter_layout)

        self.table = QTableWidget(self)
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(['Title', 'Author', 'Pubdate', 'Status', 'File CID', 'Format'])
        self.table.cellDoubleClicked.connect(self.handle_cell_double_clicked)
        self.layout.addWidget(self.table)

        self.disconnect_button = QPushButton('Disconnect', self)
        self.disconnect_button.clicked.connect(self.disconnect)
        self.layout.addWidget(self.disconnect_button)

        self.setLayout(self.layout)

    def fetch_file(self):
        cid = self.cid_input.text().strip()
        if not cid:
            error_dialog(self, 'Error', 'CID cannot be empty.', show=True)
            return
        self.fetchRequested.emit(cid)

    def on_fetch_complete(self, books):
        self.all_books = books  # Store all books for filtering
        self.display_books(books)

    def display_books(self, books):
        self.table.setRowCount(len(books))
        for row_idx, book in enumerate(books):
            self.table.setItem(row_idx, 0, QTableWidgetItem(book.get('title', '')))
            self.table.setItem(row_idx, 1, QTableWidgetItem(book.get('author', '')))
            self.table.setItem(row_idx, 2, QTableWidgetItem(str(book.get('pubdate', ''))))
            self.table.setItem(row_idx, 3, QTableWidgetItem(book.get('status', '')))
            self.table.setItem(row_idx, 4, QTableWidgetItem(book.get('file_cid', '')))
            self.table.setItem(row_idx, 5, QTableWidgetItem(book.get('format', '')))
        self.table.resizeColumnsToContents()

    def on_fetch_error(self, error):
        error_dialog(self, 'Fetch Failed', error, show=True)

    def handle_cell_double_clicked(self, row, column):
        if column == 3:
            self.show_status_dropdown(row)
        else:
            self.open_book(row)

    def open_book(self, row):
        title_item = self.table.item(row, 0)
        author_item = self.table.item(row, 1)
        pubdate_item = self.table.item(row, 2)
        status_item = self.table.item(row, 3)
        file_cid_item = self.table.item(row, 4)
        format_item = self.table.item(row, 5)

        book = {
            'title': title_item.text() if title_item else '',
            'author': author_item.text() if author_item else '',
            'pubdate': pubdate_item.text() if pubdate_item else '',
            'status': status_item.text() if status_item else '',
            'file_cid': file_cid_item.text() if file_cid_item else '',
            'format': format_item.text() if format_item else ''
        }

        self.openBookRequested.emit(book)

    def show_status_dropdown(self, row):
        combo = QComboBox(self)
        combo.addItems(['READING', 'WANT TO READ', 'COMPLETE'])
        self.table.setCellWidget(row, 3, combo)
        combo.activated.connect(lambda: self.update_status(row, combo))

    def update_status(self, row, combo):
        new_status = combo.currentText()
        self.table.removeCellWidget(row, 3)
        self.table.setItem(row, 3, QTableWidgetItem(new_status))

        title_item = self.table.item(row, 0)
        author_item = self.table.item(row, 1)
        pubdate_item = self.table.item(row, 2)
        file_cid_item = self.table.item(row, 4)
        format_item = self.table.item(row, 5)

        book = {
            'title': title_item.text() if title_item else '',
            'author': author_item.text() if author_item else '',
            'pubdate': pubdate_item.text() if pubdate_item else '',
            'status': new_status,
            'file_cid': file_cid_item.text() if file_cid_item else '',
            'format': format_item.text() if format_item else ''
        }

        self.statusUpdated.emit(book)

    def filter_status(self):
        selected_status = self.filter_combo.currentText()
        if selected_status == 'All':
            self.display_books(self.all_books)
        else:
            filtered_books = [book for book in self.all_books if book.get('status', '') == selected_status]
            self.display_books(filtered_books)

    def disconnect(self):
        self.table.setRowCount(0)
        self.cid_input.clear()
        self.fetchRequested.emit(None)
