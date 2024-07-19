from calibre.customize import InterfaceActionBase

class IPFSPlugin(InterfaceActionBase):
    name = 'Remote Conn'
    description = 'A plugin to connect to remote databases via IPFS'
    supported_platforms = ['windows', 'osx', 'linux']
    author = 'Tamilarasan Thangaiah'
    version = (1, 0, 0)

    actual_plugin = 'calibre_plugins.remote_conn.main:RemoteConnPlugin'
    dont_add_to = frozenset(['context-menu-device', 'context-menu-library', 'toolbar-device', 'toolbar-library'])
    def is_customizable(self):
        return True

    def config_widget(self):
        from calibre_plugins.remote_conn.config import ConfigWidget
        return ConfigWidget()

    def save_settings(self, config_widget):
        config_widget.save_settings()

    def load_actual_plugin(self, gui):
        from calibre_plugins.remote_conn.main import RemoteConnPlugin
        return RemoteConnPlugin(gui, self.actual_plugin)
