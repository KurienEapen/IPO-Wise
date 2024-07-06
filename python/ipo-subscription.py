from bs4 import BeautifulSoup
import json
import requests


header = {
    "Connection": "keep-alive",
    "Cache-Control": "max-age=0",
    "DNT": "1",
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/111.0.0.0 Safari/537.36",
    "Sec-Fetch-User": "?1", "Accept": "*/*", "Sec-Fetch-Site": "none", "Sec-Fetch-Mode": "navigate",
    "Accept-Encoding": "gzip, deflate, br", "Accept-Language": "en-US,en;q=0.9,hi;q=0.8"
    }

def html_to_json(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    table = soup.find('table', class_='table subs-stat-table')
    if not table:
        raise ValueError("Table with class 'table subs-stat-table' not found.")
    headers = []
    rows = []
    for th in table.find_all('th'):
        headers.append(th.text.strip())
    for tr in table.find_all('tr')[1:]: 
        row = {}
        tds = tr.find_all('td')
        for i in range(len(headers)):
            row[headers[i]] = tds[i].text.strip()
        rows.append(row)
    result = {
        "data": rows
    }
    return json.dumps(result, indent=4)

def get_api_data(url):
    try:
        response = requests.get(url, headers=header)
        if response.status_code == 200:
            return response
        else:
            print(f"Failed to retrieve data from API. Status code: {response.status_code}")
            print(response)
            return None
    except requests.exceptions.RequestException as e:
        print(f"Error during API request: {e}")
        return None





url = "https://www.5paisa.com/ipo-subscription-status/ipo"
response = get_api_data(url)
res = html_to_json(response.text)
print(res)

