from bs4 import BeautifulSoup as BS
import time
import requests
from urllib.parse import urljoin
import json
import logging
logger = logging.getLogger("SimpleLogger")

class WikiScraper:
    def __init__(self, base_urls, home_url, depth, headers, delay_time, output_file):
        self.base_urls = base_urls #the starting pages of the scraping
        self.home_url = home_url #the name of the home page, important for link extraction
        self.depth = depth #for recursion - makes sure we only scrape relevant pages
        self.headers = headers #to avoid being treated as robots: we pretend we are using a browser instead of scraping
        self.delay_time = delay_time #to avoid being treated as robots:we take small pauses so that we stay within server limits
        self.output_file = output_file #name of the output file to be created later

        self.visited = set() #we keep track of visited urls to avoid infinite loops (recursion)
        
        self.session = requests.Session() #keeps connection to pages alive while recursion
        self.session.headers.update(headers) #keeps the header the same during the session

    def fetch_html(self, url):
        time.sleep(self.delay_time) #taking a break
        response = self.session.get(url) #getting url
        if response.status_code == 200: #checking status code, only proceed if response was successful
            logger.info(f"Visiting: {url}")
            return response.text #return raw HTML text
        else:
            logger.error('page returns error')
            return None
            
        
    def parser(self, url, html_text): 
        soup = BS(html_text, "lxml") #we want to create a searchable 'tree' of the websit in the memory

        title_tag = soup.find('h1')
        title = title_tag.get_text(strip=True) if title_tag else "No Title" #get main title
        content = soup.find('div', class_= "mw-parser-output") #identify main content

        #identiy and remove content we do not need
        if content:
            junk = ['aside.portable-infobox', 'div.toc', 'table', 'span.mw-editsection', 'sup.reference', 'div.printfooter', 'div.wds-tabber', 'nav', '.quote', '.featured-quote-container', '.gallery']
            for j in junk:
                for d in content.select(j): 
                    d.decompose()
        return url, title, content

    #time to 'crawl'
    def extract_links(self, cleaned_content):
        links_to_visit = []

        #we go through all the links found in the text and make sure to only extract the rigtht ones
        for a in cleaned_content.find_all('a', href=True): 
            if a['href'].startswith('/wiki/'): 
                if ':' not in a['href']:
                    link = urljoin(self.home_url, a['href'])
                    if link not in self.visited:
                        links_to_visit.append(link) #we only extract pages that we have not visited before

        return links_to_visit
    
    #put content into right format
    def text_to_dict(self, url, title, parsed_text): 
        output = {} #create dictionary for output
        output['url'] = url
        output['title'] = title
        output['paragraphs'] = []

        to_find = ['p', 'h2', 'h3']  #find paragraphs and titles
        tags = parsed_text.find_all(to_find)
        for t in tags:
            output['paragraphs'].append(t.get_text(strip=True)) #append paragraphs and titles to the dictionary
        
        return output #we created a dictionary with url, title and the list of paragraphs
    
    def save_to_jsonl(self, content_dict):
        with open(self.output_file, 'a', encoding='utf-8') as jsonl_file:
            jsonl_file.write(json.dumps(content_dict) + '\n')
    
    #this is the scraping pipeline, very important! we just put everything together - no comments, I think the code speaks for itself:)
    def scrape(self, link, current_depth):
        if link not in self.visited:
            if current_depth >= 0:
                self.visited.add(link) 
                raw_html = self.fetch_html(link)
                if raw_html is not None:
                    link, title, parsed_text = self.parser(link, raw_html)
                    if parsed_text is not None:
                        content_dict = self.text_to_dict(link, title, parsed_text)
                        self.save_to_jsonl(content_dict)
                        new_links = self.extract_links(parsed_text)
                        for new_link in new_links:
                            self.scrape(new_link, current_depth-1)
    
    #to start scraping we need to run the scrape method on the base url
    def start_scraping(self):
        for base_url in self.base_urls:
            self.scrape(base_url, self.depth)