from bs4 import BeautifulSoup as BS
import time
import requests
from urllib.parse import urljoin
import json
import logging
logger = logging.getLogger("SimpleLogger")

REAL_WORLD_CATEGORY_KEYWORDS = [
    'films', 'film', 'film series', 'actors', 'actor', 'actress', 'Fandom', 'fandom', 'book series', 'comic series', 
    'actresses', 'video games', 'soundtracks', 'video game', 'soundtrack', 'tv', 'tv series', 'tv show',
    'production', 'adaptations', 'adaptation', 'media', 'media adaptations', 'real-life', 'real life', 'real people', 'real person', 'real-world', 'real world'
]

def is_real_world(categories: list[str]) -> bool:
    """ Returns True if any category contains keywords indicating the page is about real-world media or people. """
    return any(
        any(k in c for k in REAL_WORLD_CATEGORY_KEYWORDS)
        for c in categories
    )
    
def is_valid_title(title: str) -> bool:
    '''
    Filters out pages that are likely real-world / production-related
    rather than in-universe Harry Potter content.
    '''


    title_lower = title.lower()

    return not any(keyword in title_lower for keyword in REAL_WORLD_CATEGORY_KEYWORDS)

class WikiScraper:
    '''
    A web scraper for Wiki-based websites.
    Recursively crawls pages starting from base URLs up to a given depth,
    extracts and cleans text content, and saves the results to a JSONL file.
    '''

    def __init__(self, base_urls: list[str], home_url: str, depth: int, headers: dict[str,str], delay_time: float, output_file: str) -> None:
        '''
        Initializes the WikiScraper with configuration for crawling behavior and output.
        Sets up a persistent HTTP session with the provided headers,
        and initializes a set to track visited URLs.
        '''
        self.base_urls: list[str] = base_urls #the starting pages of the scraping
        self.home_url: str = home_url #the name of the home page, important for link extraction
        self.depth: int = depth #for recursion - makes sure we only scrape relevant pages
        self.headers: dict[str, str] = headers #to avoid being treated as robots: we pretend we are using a browser instead of scraping
        self.delay_time: float = delay_time #to avoid being treated as robots:we take small pauses so that we stay within server limits
        self.output_file: str = output_file #name of the output file to be created later

        self.visited: set[str]= set() #we keep track of visited urls to avoid infinite loops (recursion)
        
        self.session = requests.Session() #keeps connection to pages alive while recursion
        self.session.headers.update(headers) #keeps the header the same during the session

    def fetch_html(self, url: str) -> str | None:
        '''
        Fetches the raw HTML content of a given URL.
        Introduces a delay before each request to avoid being flagged as a bot.
        Returns the HTML as a string if the request succeeds,
        or None if it fails, logging the error details.
        '''
        time.sleep(self.delay_time) #taking a break
        response = self.session.get(url) #getting url
        if response.status_code == 200: #checking status code, only proceed if response was successful
            logger.info(f"Visiting: {url}")
            return response.text #return raw HTML text
        else:
            logger.error(f'Page returned error {response.status_code} for {url}')
            logger.error(f'Response headers: {dict(response.headers)}')
            logger.error(f'Response body preview: {response.text[:500]}')
            return None
            
        
    def parser(self, url: str, html_text: str) -> tuple[str, str, BS | None, list[str]]: 
        '''
        Parses raw HTML into a structured BeautifulSoup object.
        Extracts the page title from the first <h1> tag and the main content
        from the wiki content div. Removes unwanted elements such as infoboxes,
        tables, edit links, references, and navigation elements before returning.
        '''
        soup = BS(html_text, "lxml") #we want to create a searchable 'tree' of the websit in the memory

        title_tag: BS | None = soup.find('h1')
        title: str = title_tag.get_text(strip=True) if title_tag else "No Title" #get main title
        content: BS | None = soup.find('div', class_= "mw-parser-output") #identify main content

        #identiy and remove content we do not need
        if content:
            junk: list[str] = ['aside.portable-infobox', 'div.toc', 'table', 'span.mw-editsection',
                                'sup.reference', 'div.printfooter'
                                , 'div.wds-tabber', 'nav', '.quote', 
                                '.featured-quote-container', '.gallery',
                                'div.thumbcaption', 'div.mw-caption', 'figcaption'] 
            for j in junk:
                for d in content.select(j): 
                    d.decompose()
        
        categories = []
        cat_container = soup.select('#mw-normal-catlinks a')
        for c in cat_container:
            text = c.get_text(strip=True).lower()
            if text != "categories":  # skip header link
                categories.append(text)
                
        return url, title, content, categories

    #time to 'crawl'
    def extract_links(self, cleaned_content: BS) -> list[str]:
        '''
        Extracts internal wiki links from the parsed page content.
        Only includes links that start with /wiki/ and do not contain colons
        (which typically indicate special or meta pages). Skips any URLs
        that have already been visited.
        '''
        links_to_visit: list[str] = []

        #we go through all the links found in the text and make sure to only extract the rigtht ones
        for a in cleaned_content.find_all('a', href=True): 
            if a['href'].startswith('/wiki/'): 
                if ':' not in a['href']:
                    link: str = urljoin(self.home_url, a['href'])
                    if link not in self.visited:
                        links_to_visit.append(link) #we only extract pages that we have not visited before

        return links_to_visit
    
    def text_to_dict(self, url:str, title:str, parsed_text: BS) -> dict:
        '''
        Converts parsed page content into a structured dictionary.
        Extracts all paragraph and heading tags (<p>, <h2>, <h3>) as plain text
        and stores them in a list under the key "paragraphs", along with
        the page URL and title. It discards the irrelevant sections.
        ''' 
        EXCLUDED_SECTIONS: set[str] = {"behind the scenes", "trivia", "notes", "references", "external links", "see also", "appearances", "sources", "further reading", "gallery", "video", "videos", "navigation", "fans"}
        
        output:dict = {} #create dictionary for output
        output['url'] = url
        output['title'] = title
        output['paragraphs'] = []

        skip: bool = False

        to_find: list[str] = ['p', 'h2', 'h3']  #find paragraphs and titles
        tags = parsed_text.find_all(to_find)
        for t in tags:
            if t.name in ['h2', 'h3']:
                heading: str = t.get_text(separator=" ", strip=True).lower()
                skip = heading in EXCLUDED_SECTIONS
            if not skip:
                output['paragraphs'].append(t.get_text(separator = " ", strip=True)) #append paragraphs and titles to the dictionary
        
        return output #we created a dictionary with url, title and the list of paragraphs
    
    def save_to_jsonl(self, content_dict: str) -> None:
        '''
        Appends a content dictionary as a JSON line to the output file.
        Each call writes one record followed by a newline,
        producing a valid JSONL (JSON Lines) formatted file.
        '''
        with open(self.output_file, 'a', encoding='utf-8') as jsonl_file:
            jsonl_file.write(json.dumps(content_dict) + '\n')
    
    #this is the scraping pipeline, very important! we just put everything together - no comments, I think the code speaks for itself:)
    def scrape(self, link: str, current_depth: int) -> None:
        '''
        Recursively scrapes a wiki page and its linked pages up to the given depth.
        Skips already-visited URLs. For each new page, fetches the HTML, parses it,
        saves the content to JSONL, extracts further links, and recurses
        with a decremented depth counter.
        '''
        if link not in self.visited:
            if current_depth >= 0:
                raw_html: str | None = self.fetch_html(link)
                if raw_html is None:
                    return
                link, title, parsed_text, categories = self.parser(link, raw_html)
                if not is_valid_title(title):
                    return
                if is_real_world(categories):
                    return
                self.visited.add(link) 
                if parsed_text is not None:
                    content_dict: dict = self.text_to_dict(link, title, parsed_text)
                    self.save_to_jsonl(content_dict)
                    new_links: list[str] = self.extract_links(parsed_text)
                    for new_link in new_links:
                        self.scrape(new_link, current_depth-1)
    
    #to start scraping we need to run the scrape method on the base url
    def start_scraping(self) -> None:
        '''
        Entry point for the scraping process.
        Iterates over all base URLs and initiates recursive scraping
        for each one at the configured starting depth.
        '''
        for base_url in self.base_urls:
            self.scrape(base_url, self.depth)