import requests
from bs4 import BeautifulSoup


class DivxTorrent:
    def __init__(self, url):
        self.url = url

    def get_torrents(self) -> []:
        response = requests.get(self.url)
        torrents = []

        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            torrent = soup.find_all('a',
                                    class_='text-white bg-primary rounded-pill d-block shadow-sm text-decoration-none my-1 py-1')
            for t in torrent:
                torrents.append(f"https:{t['href']}")

        return torrents