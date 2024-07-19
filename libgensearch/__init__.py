from calibre.customize import InterfaceActionBase

class LibgenSearch(InterfaceActionBase):
    name = 'Libgen Search'
    description = 'Search and download books from Libgen'
    supported_platforms = ['windows', 'osx', 'linux']
    author = 'Tamilarasan Thangaiah'
    version = (1, 0, 0)

    def load_actual_plugin(self,gui):
        from calibre_plugins.libgen_search.interface import InterfacePlugin
        return InterfacePlugin(gui)
