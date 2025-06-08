import logging
from typing import Optional

import qbittorrentapi
import requests.exceptions
from bs4 import BeautifulSoup
from lxml import html
from selenium.common import WebDriverException
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium import webdriver
from webdriver_manager.firefox import GeckoDriverManager

from DivxOnlineDownloader import DivxTorrent

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)


class qBittorrent:
    def __init__(self, qbt_host: Optional[str] = "127.0.0.1", qbt_port: Optional[int] = 8080,
                 qbt_username: Optional[str] = "admin", qbt_password: Optional[str] = "secret"):
        logger.info(f"Initializing qBittorrent client for host: {qbt_host}:{qbt_port}")
        self.qbt_connection = dict(
            host=qbt_host,
            port=qbt_port,
            username=qbt_username,
            password=qbt_password
        )
        self.nova3_url = "https://github.com/qbittorrent/search-plugins/tree/master/nova3/engines"
        self.qbt_plugins_url = "https://github.com/qbittorrent/search-plugins/wiki/Unofficial-search-plugins"
        self.tracker_sources = [
            'https://raw.githubusercontent.com/ngosang/trackerslist/master/trackers_all.txt',
            'https://cdn.staticaly.com/gh/XIU2/TrackersListCollection/master/all.txt'
        ]
        self.driver = None  # Initialize driver to None
        try:
            logger.info("Setting up Firefox WebDriver with GeckoDriverManager.")
            self.driver = webdriver.Firefox(service=FirefoxService(GeckoDriverManager().install()))
            logger.info("WebDriver initialized successfully.")
        except WebDriverException as e:
            logger.error(f"Error initializing WebDriver: {e}")
        except Exception as e:
            logger.error(f"An unexpected error occurred during WebDriver initialization: {e}")

        self._connect_to_qbittorrent()

    def _fetch_fastest_trackers(self, max_trackers=50):
        """Obtiene y clasifica trackers por velocidad"""
        logger.info("Fetching fastest trackers.")
        all_trackers = []
        for source in self.tracker_sources:
            logger.debug(f"Fetching trackers from source: {source}")
            try:
                response = requests.get(source, timeout=15)
                response.raise_for_status()  # It's good practice to check for HTTP errors
                trackers = [t.strip() for t in response.text.split('\n') if t.strip()]
                all_trackers.extend(trackers)
                logger.debug(f"Successfully fetched {len(trackers)} trackers from {source}.")
            except requests.exceptions.RequestException as e:
                logger.error(f"Error fetching trackers from {source}: {e}")
            except Exception as e:
                logger.error(f"An unexpected error occurred while fetching trackers from {source}: {e}")

        unique_trackers = list(set(all_trackers))
        logger.info(f"Found {len(unique_trackers)} unique trackers.")

        priority_trackers = sorted(unique_trackers, key=lambda x: (
            'udp' in x,
            'wss' not in x,
            len(x)
        ), reverse=True)
        logger.info(f"Returning top {min(max_trackers, len(priority_trackers))} trackers.")
        return priority_trackers[:max_trackers]

    def __del__(self):
        if self.driver:
            logger.info("Quitting WebDriver.")
            try:
                self.driver.quit()
            except Exception as e:
                logger.error(f"Error quitting WebDriver: {e}")

    def _connect_to_qbittorrent(self):
        logger.info("Connecting to qBittorrent API.")
        try:
            self.client = qbittorrentapi.Client(**self.qbt_connection)
            self.client.auth_log_in()  # It's good to verify the connection
            logger.info("Successfully connected to qBittorrent API and logged in.")
        except qbittorrentapi.exceptions.LoginFailed as e:
            logger.error(f"qBittorrent login failed: {e}")
        except requests.exceptions.ConnectionError as e:
            logger.error(f"qBittorrent connection failed: {e}")
        except Exception as e:
            logger.error(f"An unexpected error occurred while connecting to qBittorrent: {e}")

    def _get_nova3_plugins(self):
        logger.info(f"Fetching nova3 plugins from: {self.nova3_url}")
        try:
            response = requests.get(self.nova3_url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            plugins = set()
            for link in soup.find_all("a", href=True):
                href = link.get("href")
                if href and href.endswith(".py") and "nova3/engines" in href and "__init__" not in href:
                    plugin_url = f"https://raw.githubusercontent.com{href}" if href.startswith(
                        "/qbittorrent/search-plugins/") else href
                    plugins.add(plugin_url)
            logger.info(f"Found {len(plugins)} nova3 plugins.")
            return sorted(list(plugins))  # Ensure it's a list for extend
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching nova3 plugins: {e}")
            return []
        except Exception as e:
            logger.error(f"An unexpected error occurred while fetching nova3 plugins: {e}")
            return []

    def _get_qbt_plugins(self):
        if not self.driver:
            logger.error("WebDriver not initialized. Cannot fetch qbt_plugins.")
            return []
        logger.info(f"Fetching qbt_plugins from: {self.qbt_plugins_url} using Selenium.")
        try:
            self.driver.get(self.qbt_plugins_url)
            tree = html.fromstring(self.driver.page_source)
            # Consider closing the driver here if it's only used for this method and not needed later
            # self.driver.quit()
            # self.driver = None # Reset driver if quit
            links = tree.xpath(
                "/html/body/div[1]/div[4]/div/main/turbo-frame/div/div/div[3]/div/div[1]/div/div/table[1]/tbody/tr[position() >=2]/td[5]/animated-image/a/@href")
            plugins = set()
            for link in links:
                plugins.add(link)
            logger.info(f"Found {len(plugins)} qbt unofficial plugins.")
            return sorted(list(plugins))  # Ensure it's a list for extend
        except requests.exceptions.RequestException as e:  # This might not be the right exception for Selenium errors
            logger.error(f"Error fetching qbt_plugins with Selenium: {e}")
            return []
        except WebDriverException as e:
            logger.error(f"WebDriver error while fetching qbt_plugins: {e}")
            return []
        except Exception as e:
            logger.error(f"An unexpected error occurred while fetching qbt_plugins: {e}")
            return []
        finally:
            # If you decide to quit the driver within this method, ensure it's handled correctly.
            # For now, I'm assuming the driver is managed by __del__ or elsewhere.
            pass

    def install_plugin(self):
        logger.info("Starting plugin installation process.")
        nova3_plugins = self._get_nova3_plugins()
        qbt_other_plugins = self._get_qbt_plugins()

        all_plugins = nova3_plugins
        if qbt_other_plugins:  # Ensure it's not empty before extending
            all_plugins.extend(qbt_other_plugins)

        if not all_plugins:
            logger.warning("No plugins found to install.")
            return

        try:
            logger.info("Fetching currently installed plugins.")
            installed_plugins = self.client.search_plugins()
            tb_delete = [n["name"] for n in installed_plugins]
            if tb_delete:
                logger.info(f"Uninstalling existing plugins: {tb_delete}")
                self.client.search_uninstall_plugin(names=tb_delete)  # Use named argument for clarity
            else:
                logger.info("No existing plugins to uninstall.")

            logger.info(f"Installing {len(all_plugins)} new plugins.")
            self.client.search_install_plugin(sources=all_plugins)  # Use named argument
            logger.info("Plugin installation process completed.")
        except qbittorrentapi.exceptions.APIConnectionError as e:
            logger.error(f"API Connection error during plugin installation: {e}")
        except Exception as e:
            logger.error(f"An unexpected error occurred during plugin installation: {e}")

    def update_trackers(self):
        logger.info("Starting tracker update process.")
        try:
            downloading_torrents = self.client.torrents_info(status_filter='downloading')
            if not downloading_torrents:
                logger.info("No torrents are currently downloading. Skipping tracker update.")
                return

            downloading_hashes = [torrent_info["hash"] for torrent_info in downloading_torrents]
            logger.info(f"Found {len(downloading_hashes)} downloading torrents to update trackers for.")

            trackers_to_add = self._fetch_fastest_trackers()
            if not trackers_to_add:
                logger.warning("No trackers fetched. Skipping tracker update for torrents.")
                return

            for torrent_hash in downloading_hashes:
                logger.debug(f"Updating trackers for torrent: {torrent_hash}")
                try:
                    current_trackers = self.client.torrents_trackers(torrent_hash=torrent_hash)
                    trackers_to_remove = [tracker["url"] for tracker in current_trackers]
                    if trackers_to_remove:
                        logger.debug(f"Removing {len(trackers_to_remove)} existing trackers for {torrent_hash}.")
                        self.client.torrents_remove_trackers(torrent_hash=torrent_hash, urls=trackers_to_remove)

                    logger.debug(f"Adding {len(trackers_to_add)} new trackers for {torrent_hash}.")
                    self.client.torrents_add_trackers(torrent_hash=torrent_hash, urls=trackers_to_add)
                except qbittorrentapi.exceptions.NotFound404Error:
                    logger.warning(f"Torrent with hash {torrent_hash} not found while trying to update its trackers.")
                except Exception as e:
                    logger.error(f"Error updating trackers for torrent {torrent_hash}: {e}")

            logger.info(f"Reannouncing {len(downloading_hashes)} torrents.")
            self.client.torrents_reannounce(torrent_hashes=downloading_hashes)  # Use named argument
            logger.info("Tracker update process completed.")
        except qbittorrentapi.exceptions.APIConnectionError as e:
            logger.error(f"API Connection error during tracker update: {e}")
        except Exception as e:
            logger.error(f"An unexpected error occurred during tracker update: {e}")

    def add_torrents(self, torrents):
        if not torrents:
            logger.info("No torrents provided to add.")
            return
        logger.info(f"Adding {len(torrents)} torrent(s).")
        try:
            self.client.torrents_add(urls=torrents, is_paused=False)  # Use named argument
            logger.info(f"Successfully added {len(torrents)} torrent(s).")
            self.update_trackers()
        except qbittorrentapi.exceptions.APIConnectionError as e:
            logger.error(f"API Connection error while adding torrents: {e}")
        except Exception as e:
            logger.error(f"An unexpected error occurred while adding torrents: {e}")


if __name__ == "__main__":
    logger.info("qBittorrent script started.")
    # Example usage:
    # logger.info("Fetching torrents from DivxOnline...")
    # dvx = DivxTorrent("https://divxonline.org/serie/112432/112432/Dune-La-profecia-1-Temporada")
    # torrent_links = dvx.get_torrents()
    # if not torrent_links:
    #     logger.warning("No torrent links found from DivxOnline.")
    # else:
    #     logger.info(f"Found {len(torrent_links)} torrent links.")

    try:
        qbt = qBittorrent()
        # logger.info("Attempting to install plugins...")
        # qbt.install_plugin()
        # logger.info("Plugins installation process finished.")

        logger.info("Attempting to update trackers...")
        qbt.update_trackers()
        logger.info("Trackers update process finished.")

        # if torrent_links:
        #     logger.info("Attempting to add torrents...")
        #     qbt.add_torrents(torrent_links)
        #     logger.info("Torrents adding process finished.")
        # else:
        #     logger.info("Skipping adding torrents as no links were found.")

    except Exception as e:
        logger.critical(f"A critical error occurred in the main execution block: {e}", exc_info=True)
    finally:
        logger.info("qBittorrent script finished.")
