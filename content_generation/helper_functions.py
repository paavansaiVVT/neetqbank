from playwright.async_api import async_playwright
from w3lib.html import get_base_url
from bs4 import BeautifulSoup
import extruct


async def scrape_url_content(url):
    """
    Scrapes content from a given URL asynchronously, including meta tags, headings, paragraphs, tables, and all schema types.
    Args:
        url (str): The URL to scrape.
    Returns:
        dict: A dictionary containing the title, meta description, headings, content, tables, and schema data in JSON format.
    """
    try:
        # Use Playwright to render dynamic content
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, timeout=30000)  # Wait for the page to load
            html_content = await page.content()  # Get fully rendered HTML
            await browser.close()
        # Parse the HTML content
        soup = BeautifulSoup(html_content, 'html.parser')
        # Extract the title
        title = soup.title.string if soup.title else 'No Title Found'
        # Extract the meta description
        meta_description = soup.find('meta', attrs={'name': 'description'})
        meta_description_content = meta_description['content'] if meta_description else 'No Meta Description Found'
        # Extract headings (H1, H2, H3)
        headings = {
            'h1': [h1.get_text(strip=True) for h1 in soup.find_all('h1')],
            'h2': [h2.get_text(strip=True) for h2 in soup.find_all('h2')],
            'h3': [h3.get_text(strip=True) for h3 in soup.find_all('h3')],}

        # Extract all paragraph content
        paragraphs = [p.get_text(strip=True) for p in soup.find_all('p') if p.get_text(strip=True)]

        # Extract tables in JSON format
        tables = []
        for table in soup.find_all('table'):
            headers = [th.get_text(strip=True) for th in table.find_all('th')]
            rows = []
            for row in table.find_all('tr'):
                cells = [cell.get_text(strip=True) for cell in row.find_all('td')]
                if headers and len(cells) == len(headers):
                    rows.append(dict(zip(headers, cells)))
                else:
                    rows.append(cells)
            tables.append({'headers': headers if headers else 'No headers found', 'rows': rows})

        # Extract schemas using Extruct
        extracted_schemas = extruct.extract(html_content,base_url=get_base_url(html_content, url),syntaxes=['json-ld', 'microdata', 'rdfa'])
        return {'title': title,'meta_description': meta_description_content,'headings': headings,'content': paragraphs,'tables': tables,'schema': extracted_schemas}
    except Exception as e:
        return {'error': f'An error occurred: {e}'}
    

def update_combined_tokens(response, state):
    """
    Update the combined tokens with the new tokens from the response.
    Args:
        response: The response object containing usage metadata.
        state: The current state dictionary containing combined tokens.
    Returns:
        dict: Updated combined tokens.
    """
    try:
        combined_tokens = {
            'input_tokens': response['input_tokens'] + state['input_tokens'],
            'output_tokens': response['output_tokens'] + state['output_tokens'],
            'total_tokens': response['total_tokens'] + state['total_tokens']}
        return combined_tokens
    except Exception as e:
        return state
