from calibre.utils.config import JSONConfig
import os
plugin_prefs = JSONConfig('plugins/LibgenSearch')

# Set defaults
default_download_path = os.path.join(os.path.expanduser("~"), "Downloads")
plugin_prefs.defaults['search_url'] = 'https://libgen.is/search.php'
plugin_prefs.defaults['max_results'] = 15
plugin_prefs.defaults['download_path'] = '~/Downloads'