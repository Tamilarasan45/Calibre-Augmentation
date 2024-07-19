import json
import tempfile
import os
import sys
import subprocess
from PyQt5.Qt import QAction, QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem, QPushButton, QInputDialog, QThread, pyqtSignal
from calibre.gui2 import error_dialog, info_dialog
from calibre_plugins.remote_conn.common_icons import get_icon

PLUGIN_ICONS = ['images/remote_conn.png']
plugin_dir = os.path.dirname(__file__)
lib_dir = os.path.join(plugin_dir, 'lib')
sys.path.insert(0, lib_dir)

#To Ensure the requests module is available
try:
    import requests
except ImportError:
    raise ImportError('The requests module is required. Please ensure it is installed.')

class FetchThread(QThread):
    fetched = pyqtSignal(list) # Signal for successfully fetched books
    error = pyqtSignal(str) # Signal for errors

    def __init__(self, cid):
        super().__init__()
        self.cid = cid

    def run(self):
        try:
            ipfs_url = f'http://127.0.0.1:5001/api/v0/cat?arg={self.cid}'
            response = requests.post(ipfs_url)
            response.raise_for_status() # Raise an error if the request was unsuccessful
            books = json.loads(response.text)
            self.fetched.emit(books)
        except Exception as e:
            self.error.emit(str(e))

class RemoteConnPlugin(QAction):
    name = 'Remote Conn'
    dont_add_to = frozenset([''])
    popup_type = QDialog

    def __init__(self, gui, global_db=None):
        super().__init__('Remote Connection', gui)
        self.gui = gui
        self.global_db = global_db
        self.setIcon(get_icon(PLUGIN_ICONS[0]))
        self.ipfs_client = requests.Session()
        self.book_statuses = ['READ', 'WANT-TO-READ', 'READING', 'COMPLETE']
        self.dialog = None
        self.books = []
        self.qaction = self
        self.triggered.connect(self.show_dialog)

    def show_dialog(self):
        from calibre_plugins.remote_conn.interface import RemoteConnDialog
        self.dialog = RemoteConnDialog(self.gui)
        self.dialog.fetchRequested.connect(self.sync_remote_db)
        self.dialog.openBookRequested.connect(self.open_book)
        self.dialog.statusUpdated.connect(self.update_book_status)
        self.dialog.show()

    # Synchronize the remote database using a CID
    def sync_remote_db(self, cid):
        if cid:
            self.fetch_thread = FetchThread(cid)
            self.fetch_thread.fetched.connect(self.on_books_fetched)
            self.fetch_thread.error.connect(self.on_fetch_error)
            self.fetch_thread.start()
        else:
            self.on_disconnect()

    def on_books_fetched(self, books):
        self.books = books
        if self.dialog:
            self.dialog.on_fetch_complete(books)

    def on_fetch_error(self, error):
        if self.dialog:
            self.dialog.on_fetch_error(error)

    def on_disconnect(self):
        if self.dialog:
            self.dialog.table.setRowCount(0)
            self.dialog.cid_input.clear()
        info_dialog(self.gui, 'Disconnected', 'Disconnected from remote database.', show=True)

    # Open a book in Calibre
    def open_book(self, book):
        book_title = book.get('title', 'Unknown Title')
        book_file_cid = book.get('file_cid', None)
        book_format = book.get('format', 'pdf')
        if not book_file_cid:
            error_dialog(self.gui, 'Open Book Failed', 'No file CID provided for the book.', show=True)
            return

        # Fetch the book file from IPFS
        try:
            print(f'Fetching book with CID: {book_file_cid}')
            temp_file_path = os.path.join(tempfile.gettempdir(), f'{book_title}.{book_format.lower()}')
            self.download_from_ipfs(book_file_cid, temp_file_path)
            print(f'Book downloaded to: {temp_file_path}')

            # Open ebook using Calibre viewer
            self.open_with_calibre(temp_file_path)

            os.remove(temp_file_path)  # Clean up the temporary file
        except Exception as e:
            error_dialog(self.gui, f'Open Book Failed {book_file_cid}', str(e), show=True)
            
    def download_from_ipfs(self, cid, save_path):
        url = f"http://127.0.0.1:8080/ipfs/{cid}"
        print(f'Downloading from IPFS: {url}')
        response = requests.get(url, stream=True)
        response.raise_for_status()
        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                            
    def open_with_calibre(self, file_path):
        try:
            calibre_viewer_path = "C:\\Program Files\\Calibre2\\ebook-viewer.exe"
            subprocess.run([calibre_viewer_path, file_path])
        except Exception as e:
            error_dialog(self.gui, 'Failed to Open with Calibre', str(e), show=True)
            
    def update_book_status(self, book):
        for idx, stored_book in enumerate(self.books):
            if stored_book['title'] == book['title'] and stored_book['author'] == book['author']:
                self.books[idx] = book
                break
        self.save_books_to_ipfs()

    def save_books_to_ipfs(self):
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.json') as temp_file:
                temp_file.write(json.dumps(self.books).encode('utf-8'))
                temp_file.close()
                with open(temp_file.name, 'rb') as f:
                    files = {'file': f}
                    response = requests.post('http://127.0.0.1:5001/api/v0/add',
                        files=files)
                    response.raise_for_status()
                    ipfs_cid = response.json()['Hash']
                    info_dialog(self.gui, 'IPFS Update', f'The updated book list has been uploaded to IPFS with CID: {ipfs_cid}', show=True)
                os.remove(temp_file.name)
        except Exception as e:
            error_dialog(self.gui, 'Failed to Save Books to IPFS', str(e), show=True)

    # Disconnect from the remote database
    def disconnect_remote_db(self):
        try:
            self.books = []
            self.on_disconnect()
        except Exception as e:
            print(f"Failed to disconnect: {e}")
            raise
