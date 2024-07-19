from calibre.gui2.actions import InterfaceAction
from calibre_plugins.libgen_search.actions import SearchAction
from PyQt5.Qt import QIcon
from calibre_plugins.libgen_search.common_icons import get_icon
import os

class InterfacePlugin(InterfaceAction):
    name = 'Libgen Search'

    def __init__(self, gui):
        super(InterfacePlugin, self).__init__(gui, None)
        self.gui = gui

    def genesis(self):
        self.qaction.setText('Search Libgen')
        self.qaction.setIcon(get_icon('images/libgen_search.png'))
        #icon_path = os.path.join(os.path.dirname(__file__), 'images', 'libgen_search.png')
        #if os.path.exists('/calibre_plugins/libgen_search/images/libgen_search.png'):
        #    self.qaction.setIcon(QIcon('/calibre_plugins/libgen_search/images/libgen_search.png'))
        self.search_action = SearchAction(self.gui)
        self.qaction.triggered.connect(self.show_search_dialog)
        #self.gui.keyboard.add_shortcut('Ctrl+Shift+L', self.search_action)

    def show_search_dialog(self):
        self.search_action.search_libgen()
