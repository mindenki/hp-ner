from scraping import WikiScraper
import os
import logging

logger = logging.getLogger("SimpleLogger")
logger.setLevel(logging.INFO)

console_handler = logging.StreamHandler()
logger.addHandler(console_handler)

base_urls = ['https://harrypotter.fandom.com/wiki/Harry_Potter']
home_url = 'https://harrypotter.fandom.com'
depth=1
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.117 Safari/537.36'}
delay_time=2

folder = './scraped_data/'
os.makedirs(folder, exist_ok=True)
output_file=os.path.join(folder, "wiki_data.jsonl")


scraper = WikiScraper(base_urls, home_url, depth, headers, delay_time, output_file)
scraper.start_scraping()
