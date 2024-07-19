import sys
import os

plugin_dir = os.path.dirname(__file__)
lib_dir = os.path.join(plugin_dir, 'lib')
sys.path.insert(0, lib_dir)

import requests
from bs4 import BeautifulSoup

class LibgenSearchPlugin:
    def search(self, query, max_results=15):
        search_url = 'https://libgen.is/search.php' #libgen url
        payload = {'req': query, 'res': max_results, 'open': 0, 'view': 'simple', 'phrase': 1, 'column': 'def'}
        response = requests.get(search_url, params=payload)
        response.raise_for_status() # Raise an error if the request was unsuccessful
        return self.parse_results(response.text) # Parse and return the search results

    def parse_results(self, html):
        soup = BeautifulSoup(html, 'html.parser') # Parse the HTML content using BeautifulSoup
        table = soup.find('table', {'class': 'c'})
        results = []
        for row in table.find_all('tr')[1:]:
            cols = row.find_all('td')
            result = {
                'title': cols[2].get_text(strip=True),
                'author': cols[1].get_text(strip=True),
                'year': cols[4].get_text(strip=True),
                'publisher': cols[5].get_text(strip=True),
                'format': cols[8].get_text(strip=True),
                'size': cols[7].get_text(strip=True),
                'url': cols[9].a['href']
            }
            results.append(result)
        return results
    
    def download_book(self, url, save_path):
        response = requests.get(url, stream=True)
        response.raise_for_status() # Raise an error if the request was unsuccessful
        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
