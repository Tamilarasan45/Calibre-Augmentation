from PyQt5.Qt import QAction, QInputDialog, QDialog, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QPushButton, QIcon, QFileDialog
from calibre.gui2 import error_dialog, info_dialog
from calibre_plugins.libgen_search.main import LibgenSearchPlugin
from calibre_plugins.libgen_search.config import plugin_prefs
from calibre.ebooks.metadata.book.base import Metadata
from calibre.ebooks.metadata import epub as epub_meta
from calibre.ebooks.metadata import pdf as pdf_meta
from calibre.ebooks.metadata import mobi as mobi_meta
from calibre_plugins.libgen_search.common_icons import get_icon
from bs4 import BeautifulSoup
import os
import re
import requests
import subprocess
from PyQt5 import QtGui, QtCore
from PyQt5.QtCore import QThread, pyqtSignal
import tempfile
import threading

PLUGIN_ICONS = ['images/libgen_search.png']

# Attempt to import ipfshttpclient and handle failure if it's not available
try:
    import ipfshttpclient
    IPFS_AVAILABLE = True
except ImportError:
    IPFS_AVAILABLE = False

class SearchAction(QAction):
    def __init__(self, gui):
        super().__init__('Search Libgen', gui)
        self.gui = gui
        self.setIcon(get_icon(PLUGIN_ICONS[0]))
        self.all_results = []
        self.results_per_page = 15
        self.current_page = 0
        self.dialog = None

        self.ipfs_client = None
        if IPFS_AVAILABLE:
            try:
                self.ipfs_client = ipfshttpclient.connect('/ip4/127.0.0.1/tcp/5001')
            except ipfshttpclient.exceptions.Error as e:
                print(f"Failed to connect to IPFS: {e}")
                self.ipfs_client = None

        self.triggered.connect(self.search_libgen)

    def search_libgen(self):
        max_results = plugin_prefs['max_results']
        libgen = LibgenSearchPlugin()
        query, ok = QInputDialog.getText(self.gui, 'Search Libgen', 'Enter search query:')
        if ok and query:
            try:
                results = libgen.search(query, max_results)
                if results:
                    self.all_results = results
                    self.current_page = 0
                    self.display_results()
                else:
                    info_dialog(self.gui, 'No Results', 'No results found for the query.', show=True)
            except Exception as e:
                error_dialog(self.gui, 'Failed to search Libgen', str(e), show=True)

    def display_results(self):
        if self.dialog is None:
            self.dialog = QDialog(self.gui)
            self.dialog.setWindowTitle('Libgen Search Results')
            self.dialog.setGeometry(100, 100, 900, 600)
            self.layout = QVBoxLayout(self.dialog)

            logo_path = os.path.join(os.path.dirname(__file__), 'images', 'libgen_search.png')
            if os.path.exists(logo_path):
                self.logo_label = QLabel(self.dialog)
                logo_pixmap = QtGui.QPixmap(logo_path)
                self.logo_label.setPixmap(logo_pixmap)
                self.logo_label.setAlignment(QtCore.Qt.AlignCenter)
                self.layout.addWidget(self.logo_label)

            self.table = QTableWidget(self.results_per_page, 6, self.dialog)
            self.table.setHorizontalHeaderLabels(['Title', 'Author', 'Year', 'Publisher', 'Format', 'Size'])
            self.table.verticalHeader().setVisible(False)
            self.table.resizeColumnsToContents()
            self.table.cellDoubleClicked.connect(lambda row, col: self.show_download_or_stream_dialog(self.all_results[self.current_page * self.results_per_page + row]))
            self.layout.addWidget(self.table)

            self.nav_layout = QVBoxLayout()

            self.previous_button = QPushButton('Previous', self.dialog)
            self.previous_button.clicked.connect(self.previous_page)
            self.nav_layout.addWidget(self.previous_button)

            self.next_button = QPushButton('Next', self.dialog)
            self.next_button.clicked.connect(self.next_page)
            self.nav_layout.addWidget(self.next_button)

            self.layout.addLayout(self.nav_layout)

            self.close_button = QPushButton('Close', self.dialog)
            self.close_button.clicked.connect(self.dialog.close)
            self.layout.addWidget(self.close_button)

            self.dialog.setLayout(self.layout)
        
        self.update_table()
        self.dialog.show()

    def update_table(self):
        start_index = self.current_page * self.results_per_page
        end_index = min(start_index + self.results_per_page, len(self.all_results))
        self.table.setRowCount(end_index - start_index)
        
        for row, result in enumerate(self.all_results[start_index:end_index]):
            self.table.setItem(row, 0, QTableWidgetItem(result.get('title', '')))
            self.table.setItem(row, 1, QTableWidgetItem(result.get('author', '')))
            self.table.setItem(row, 2, QTableWidgetItem(result.get('year', '')))
            self.table.setItem(row, 3, QTableWidgetItem(result.get('publisher', '')))
            self.table.setItem(row, 4, QTableWidgetItem(result.get('format', '')))
            self.table.setItem(row, 5, QTableWidgetItem(result.get('size', '')))
        
        self.table.resizeColumnsToContents()
        
        self.previous_button.setEnabled(self.current_page > 0)
        self.next_button.setEnabled(end_index < len(self.all_results))

    def next_page(self):
        if (self.current_page + 1) * self.results_per_page < len(self.all_results):
            self.current_page += 1
            self.update_table()

    def previous_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.update_table()

    def sanitize_filename(self, filename):
        return re.sub(r'[<>:"/\\|?*]', '', filename)

    def show_download_or_stream_dialog(self, result):
        dialog = QDialog(self.gui)
        dialog.setWindowTitle("Download or Stream")
        layout = QVBoxLayout(dialog)
        download_button = QPushButton("Download", dialog)
        download_button.clicked.connect(lambda: self.download_book(result['url'], result['title'], result['format'], dialog))
        stream_button = QPushButton("Stream", dialog)
        stream_button.clicked.connect(lambda: self.stream_book(result['url'], result['format'], dialog))
        layout.addWidget(QLabel(f"Do you want to download or stream '{result['title']}'?"))
        layout.addWidget(download_button)
        layout.addWidget(stream_button)
        dialog.setLayout(layout)
        dialog.exec_()

    def download_book(self, url, title, format,parent_dialog):
        parent_dialog.accept()
        download_path = plugin_prefs.get('download_path', os.path.join(os.path.expanduser("~"), "Downloads"))
        sanitized_title = self.sanitize_filename(title)
        default_filename = os.path.join(download_path, f"{sanitized_title}.{format.lower()}")
        save_path, _ = QFileDialog.getSaveFileName(self.gui, 'Save Book', default_filename, f"{format.upper()} Files (*.{format.lower()});;All Files (*)")
        if save_path:
            try:
                response = requests.get(url)
                response.raise_for_status()
                soup = BeautifulSoup(response.content, 'html.parser')
                ipfs_link = None
                for link in soup.find_all('a'):
                    if 'ipfs.io' in link.get('href', ''):
                        ipfs_link = link.get('href')
                        break

                if ipfs_link:
                    self.start_download(ipfs_link, save_path, title, format)
                else:
                    raise Exception('No IPFS link found on the download page.')

            except Exception as e:
                error_dialog(self.gui, 'Failed to Download Book', str(e), show=True)

    def start_download(self, url, save_path, title, format):
        self.download_thread = DownloadThread(url, save_path, format)
        self.download_thread.download_complete.connect(lambda cid: self.on_download_complete(save_path, title, format, cid))
        self.download_thread.download_failed.connect(self.on_download_failed)
        self.download_thread.start()
    
    def stream_book(self, url, format, parent_dialog):
        parent_dialog.accept()
        thread = threading.Thread(target=self.open_book_from_ipfs, args=(url, format))
        thread.start()

    def on_download_complete(self, save_path, title, format, cid):
        try:
            self.validate_download(save_path, format)
            if cid:
                info_dialog(self.gui, 'Download Complete', f'The book has been downloaded successfully with CID: {cid}.', show=True)
            else:
                info_dialog(self.gui, 'Download Complete', 'The book has been downloaded successfully.', show=True)
            self.add_to_calibre_library(save_path, title, format)
        except Exception as e:
            error_dialog(self.gui, 'Download Failed', str(e), show=True)

    def on_download_failed(self, error_message):
        error_dialog(self.gui, 'Download Failed', error_message, show=True)

    def validate_download(self, file_path, format):
        valid = False
        try:
            with open(file_path, 'rb') as file:
                file_signature = file.read(4)
                if format.lower() == 'pdf' and file_signature.startswith(b'%PDF'):
                    valid = True
                elif format.lower() == 'epub' and file_signature.startswith(b'PK'):
                    valid = True
                elif format.lower() == 'mobi' and file_signature.startswith(b'BOOK'):
                    valid = True
                else:
                    raise Exception('The downloaded file is not a valid {} file.'.format(format.upper()))
        except Exception as e:
            raise Exception('Failed to validate the downloaded file: {}'.format(str(e)))

    def add_to_calibre_library(self, file_path, title, format):
        try:
            db = self.gui.current_db
            metadata = self.get_metadata_from_file(file_path, format)
            mi = Metadata(title, authors=metadata.get('authors', []))
            mi.comments = metadata.get('description', '')
            mi.publisher = metadata.get('publisher', '')
            mi.pubdate = metadata.get('pubdate', None)
            mi.tags = metadata.get('tags', [])
            db.import_book(mi, [file_path])
            self.gui.library_view.model().refresh()
            self.gui.tags_view.recount()
            info_dialog(self.gui, 'Book Added', f'The book "{title}" has been added to your Calibre library with updated metadata.', show=True)
        except Exception as e:
            error_dialog(self.gui, 'Failed to Add Book to Library', str(e), show=True)
    
    def get_metadata_from_file(self, file_path, format):
        metadata = {}
        if format.lower() == 'epub':
            try:
                with open(file_path, 'rb') as file:
                    mi = epub_meta.get_metadata(file)
                metadata = {
                    'authors': mi.authors,
                    'description': mi.comments,
                    'publisher': mi.publisher,
                    'pubdate': mi.pubdate,
                    'tags': mi.tags,
                }
            except Exception as e:
                error_dialog(self.gui, 'Failed to Extract Metadata from EPUB', str(e), show=True)
        elif format.lower() == 'pdf':
            try:
                with open(file_path, 'rb') as file:
                    mi = pdf_meta.get_metadata(file)
                metadata = {
                    'authors': mi.authors,
                    'description': mi.comments,
                    'publisher': mi.publisher,
                    'pubdate': mi.pubdate,
                    'tags': mi.tags,
                }
            except Exception as e:
                error_dialog(self.gui, 'Failed to Extract Metadata from PDF', str(e), show=True)
        elif format.lower() == 'mobi':

            try:

                with open(file_path, 'rb') as file:

                    mi = mobi_meta.get_metadata(file)

                metadata = {
                    'authors': mi.authors,
                    'description': mi.comments,
                    'publisher': mi.publisher,
                    'pubdate': mi.pubdate,
                    'tags': mi.tags,
                }
            except Exception as e:

                error_dialog(self.gui, 'Failed to Extract Metadata from MOBI', str(e), show=True)
        return metadata
    
    def open_book_from_ipfs(self, url, format):
        try:
            response = requests.get(url)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            ipfs_link = None
            for link in soup.find_all('a'):
                if 'ipfs.io' in link.get('href', ''):
                    ipfs_link = link.get('href')
                    break

            if ipfs_link:
                cid = ipfs_link.split('/ipfs/')[-1]
                self.stream_and_open_book(cid, format)
            else:
                raise Exception('No IPFS link found on the download page.')

        except Exception as e:
            error_dialog(self.gui, 'Failed to Open Book from IPFS', str(e), show=True)

    def stream_and_open_book(self, cid, format):
        try:
            if IPFS_AVAILABLE:
                self.stream_from_ipfs(cid, format)
            else:
                self.fallback_stream_and_open_book(cid, format)
        except Exception as e:
            error_dialog(self.gui, 'Failed to Stream Book', str(e), show=True)
            
    def stream_from_ipfs(self, cid, format):
        try:
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=f".{format.lower()}")
            self.download_from_ipfs(cid, temp_file.name)
            temp_file.close()

            result = self.ipfs_client.add(temp_file.name)
            ipfs_cid = result['Hash']

            self.open_with_calibre(temp_file.name)

            self.ipfs_client.pin.rm(ipfs_cid)
            self.ipfs_client.files.rm(f'/ipfs/{ipfs_cid}')

            os.remove(temp_file.name)
        except Exception as e:
            self.fallback_stream_and_open_book(cid, format)
            
    def fallback_stream_and_open_book(self, cid, format):
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{format.lower()}") as temp_file:
                self.download_from_ipfs(cid, temp_file.name)
                temp_file.close()
                self.open_with_calibre(temp_file.name)
        except Exception as e:
            error_dialog(self.gui, 'Failed to Stream Book', str(e), show=True)

    def download_from_ipfs(self, cid, save_path):
        url = f"https://ipfs.io/ipfs/{cid}"
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

class DownloadThread(QThread):
    download_complete = pyqtSignal(str)
    download_failed = pyqtSignal(str)

    def __init__(self, url, save_path, format):
        super().__init__()
        self.url = url
        self.save_path = save_path
        self.format = format
        self.ipfs_client = None
        try:
            self.ipfs_client = ipfshttpclient.connect('/ip4/127.0.0.1/tcp/5001')
        except Exception as e:
            print(f"Failed to connect to IPFS: {e}")

    def run(self):
        try:
            response = requests.get(self.url, stream=True)
            if response.status_code == 410:
                raise Exception('The requested resource is no longer available.')
            response.raise_for_status()
            with open(self.save_path, 'wb') as file:
                for chunk in response.iter_content(chunk_size=8192):
                    file.write(chunk)
            if self.ipfs_client:
                try:
                    result = self.ipfs_client.add(self.save_path)
                    ipfs_cid = result['Hash']
                    self.download_complete.emit(ipfs_cid)  # Emit the IPFS CID
                except Exception as e:
                    print(f"Failed to add file to IPFS: {e}")
                    self.download_complete.emit('')  # Emit empty string if IPFS not used
        except Exception as e:
            self.download_failed.emit(str(e))
