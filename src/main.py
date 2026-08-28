#!/usr/bin/env python3
"""
Norli Book Daddy Bot - Flirty Book Reviews for Bluesky
Scrapes Norli.no for new books, generates sexy book reviews using GPT-4o, and posts to Bluesky.
"""

import json
import logging
import os
import random
import re
import time
from datetime import datetime, timezone
from pathlib import Path
import urllib.parse

import requests
from bs4 import BeautifulSoup
from atproto import Client, models
from dotenv import load_dotenv

load_dotenv()

# API Configuration
API_KEY = os.getenv("KEY_GITHUB_TOKEN")  # Azure OpenAI via GitHub Models
API_ENDPOINT = "https://models.inference.ai.azure.com/chat/completions"
# Copilot Free/GitHub Models accounts use Auto model selection.
MODEL_NAME = "auto"

# Bluesky Configuration
BSKY_HANDLE = os.getenv("BSY_HANDLE")
BSKY_PASSWORD = os.getenv("BSKY_PASSWORD")

# URLs
NORLI_GRAPHQL_API = "https://www.norli.no/graphql"

# Global proxy cache for reuse across requests
_proxy_cache = None
_proxy_url = None
_proxy_consecutive_failures = 0

# Category filtering - Norli URL path segments that indicate suitable books
SUITABLE_CATEGORIES = [
    'skjonnlitteratur',  # Fiction
    'skjønnlitteratur',  # Fiction (Norwegian spelling)
    'romaner',  # Novels
    'fantasy',
    'science-fiction',
    'spenning',  # Suspense/Thriller
    'noveller',  # Novellas/Short stories
    'psykologiske-thrillere',  # Psychological thrillers
    'psykologiske thrillere',  # Psychological thrillers (space)
    'feelgood',  # Feel-good romance
    'norsk skjønnlitteratur',  # Norwegian fiction
    'norsk-skjonnlitteratur',  # Norwegian fiction
    'nye romaner',  # New novels
    'nye-romaner',  # New novels (hyphen)
    'populære feelgood-romaner',  # Popular feelgood novels
    'populaere-feelgood-romaner',  # Popular feelgood novels
    'nyheter og bestselgere - romaner',  # News and bestsellers - novels
    'nyheter-og-bestselgere-skjonnlitteratur',  # News and bestsellers - fiction
    'topp 10 romaner',  # Top 10 novels
    'topp-10-romaner',  # Top 10 novels (hyphen)
    'topp 50 romaner',  # Top 50 novels
    'topp-50-romaner',  # Top 50 novels (hyphen)
    'topp 200 skjønnlitteratur',  # Top 200 fiction
    'topp-200-skjonnlitteratur',  # Top 200 fiction (hyphen)
    'morgenbladet-arets-beste-romaner-og-krim',  # Morgenbladet's best novels and crime
]

# URL segments that indicate unsuitable books (non-fiction, etc.)
UNSUITABLE_CATEGORIES = [
    'krimboker',  # Crime/Mystery
    'krimbøker',  # Crime/Mystery (Norwegian spelling)
    'krim og spenning',  # Crime and suspense
    'krim-og-spenning',  # Crime and suspense (hyphen)
    'nye krimbøker',  # New crime books
    'nye-krimboker',  # New crime books (hyphen)
    'nyheter og bestselgere - krim og spenning',  # News and bestsellers - crime
    'nyheter-og-bestselgere-krim-og-spenning',  # News and bestsellers - crime
    'topp 10 krimbøker',  # Top 10 crime books
    'topp-10-krimboker',  # Top 10 crime books (hyphen)
    'påskekrim',  # Easter crime
    'paskekrim',  # Easter crime (alternative spelling)
    'krimfestivalen',  # Crime festival
    'adresseavisen-arets-beste-krimboker',  # Adresseavisen's best crime books
    'fagboker',  # Academic books
    'larebøker',  # Textbooks
    'sport',
    'sport og fritid - signert',
    'sport-og-fritid-signert',
    'trening',  # Fitness/Training
    'mat-og-drikke',  # Food & Drink
    'mat og drikke',
    'mat og drikke - signert',
    'mat-og-drikke-signert',
    'kokeboker',  # Cookbooks
    'helse',  # Health
    'familie og helse',
    'familie-og-helse',
    'selvutvikling',  # Self-help
    'selvutvikling - signert',
    'selvutvikling-signert',
    'livssyn-og-selvutvikling',  # Philosophy/Self-help
    'livssyn og selvutvikling',
    'historie-og-dokumentar',  # History/Documentary
    'historie og dokumentar',
    'historie',
    'debatt-og-samfunn',  # Debate/Society
    'debatt og samfunn',
    'biografier-og-memoarer',  # Biography/Memoir
    'biografier og memoarer',
    'biografier',
    'krig-og-historie',  # War/History
    'krig og historie',
    'politikk',  # Politics
    'juss',  # Law
    'økonomi',  # Economics
    'okonomi',
    'hobby-og-fritid',  # Hobby
    'hobby og fritid',
    'hobby og fritid - signert',
    'hobby',
    'barn-og-ungdom',  # Children/Young adult
    'strikk-hjem-og-hobby',  # Knitting/Home hobby
    'strikk, hjem og hobby',
    'handarbeid-og-strikking',  # Handicraft
    'håndarbeid og strikking',
    'natur-og-dyr',  # Nature/Animals
    'natur og dyr',
    'naturen og oss',
    'boker-om-naturkrisen',
    'dokumentar-og-fakta',  # Documentary and facts
    'dokumentar og fakta',
    'nyheter og bestselgere - dokumentar og fakta',
    'nyheter-og-bestselgere-dokumentar-og-fakta',
    'nyheter og bestselgere - hobby og fritid',
    'nyheter-og-bestselgere-hobby-og-fritid',
    'topp 10 dokumentar',
    'topp-10-dokumentar',
    'topp 10 dokumentar og fakta',
    'topp-10-dokumentar-og-fakta',
    'topp-10-kokeboker',
]

# State management
STATE_FILE = Path("book_state.json")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def scrape_book_list():
    """Get book list using GraphQL API with target_group and categories baked in.
    Returns list of dicts: {url_key, name, sku, target_group, categories}"""
    logging.info("Fetching book list from Norli GraphQL API")

    query = """
    query getCategoryList($filters: CategoryFilterInput) {
      categoryList(filters: $filters) {
        id
        name
        url_path
        products(pageSize: 200) {
          items {
            name
            url_key
            sku
            norli_junior {
              target_group
            }
            categories {
              name
              url_path
            }
          }
          total_count
        }
      }
    }
    """

    variables = {
        "filters": {
            "url_key": {"eq": "manedens-nyheter"}
        }
    }

    payload = {
        "query": query,
        "variables": variables,
        "operationName": "getCategoryList"
    }

    headers = {
        'Content-Type': 'application/json',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'store': 'pwa',
        'Accept': 'application/json',
        'Accept-Language': 'nb-NO,no;q=0.9',
        'Referer': 'https://www.norli.no/boker/aktuelt-og-anbefalt/manedens-nyheter'
    }

    try:
        response = requests.post(NORLI_GRAPHQL_API, json=payload, headers=headers, timeout=15)
        response.raise_for_status()

        data = response.json()

        if 'data' in data and 'categoryList' in data['data']:
            categories = data['data']['categoryList']
            if categories and len(categories) > 0:
                category = categories[0]
                products = category.get('products', {}).get('items', [])

                books = []
                for product in products:
                    url_key = product.get('url_key')
                    if not url_key:
                        continue
                    nj = product.get('norli_junior', {}) or {}
                    tg = nj.get('target_group', []) or []
                    cats = [c.get('name', '') for c in product.get('categories', []) if c.get('name')]
                    books.append({
                        'url_key': url_key,
                        'name': product.get('name', ''),
                        'sku': product.get('sku', ''),
                        'target_group': tg,
                        'categories': cats,
                    })

                logging.info(f"Found {len(books)} books from GraphQL API")
                logging.info(f"Total books in category: {category.get('products', {}).get('total_count', 0)}")
                return books

        logging.error(f"Unexpected API response: {data}")
        return []

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 403:
            logging.warning("GraphQL API returned 403 - geo-blocking detected, trying free proxy fallback...")
            return scrape_book_list_with_free_proxy(payload, headers)
        logging.error(f"HTTP error fetching book list: {e}")
        return []
    except Exception as e:
        logging.error(f"Error fetching book list from GraphQL: {e}")
        return []


def get_working_proxy(force_refresh=False):
    """Get a working European proxy for bypassing geo-blocking"""
    global _proxy_cache, _proxy_url, _proxy_consecutive_failures

    if _proxy_cache and not force_refresh:
        return _proxy_cache

    # Don't reset counter here — only reset on actual success below

    try:
        proxies_response = requests.get(
            "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies.json",
            timeout=10
        )
        all_proxies = proxies_response.json()

        # Filter for Norway or European proxies
        european_proxies = [p for p in all_proxies if p.get('geolocation', {}).get('country', {}).get('iso_code', '') in ['NO', 'SE', 'DK', 'FI', 'DE', 'NL']]
        # Try up to 10 EU proxies, or 10 from the full list if none match
        candidates = european_proxies[:10] if european_proxies else all_proxies[:10]

        # Try to find a working proxy
        for proxy in candidates:  # Try more proxies than before
            protocol = proxy.get('protocol', 'http')
            host = proxy.get('host')
            port = proxy.get('port')

            if not host or not port:
                continue

            proxy_url = f"{protocol}://{host}:{port}"
            try:
                response = requests.get('https://httpbin.org/ip', proxies={'http': proxy_url, 'https': proxy_url}, timeout=5)
                if response.status_code == 200:
                    _proxy_cache = proxy_url
                    _proxy_url = proxy_url
                    _proxy_consecutive_failures = 0  # Reset on success
                    logging.info(f"✅ Found working proxy: {proxy_url}")
                    return proxy_url
            except:
                continue
        # Failed to find any working proxy
        logging.warning("⚠️ No working European proxy found in proxy list")
        return None
    except Exception as e:
        logging.debug(f"Failed to get proxy list: {e}")
        return None


def _invalidate_proxy():
    """Mark current proxy as dead and increment failure counter.
    After 3 consecutive failures, gives up on proxy for this run."""
    global _proxy_cache, _proxy_url, _proxy_consecutive_failures
    logging.warning(f"♻️  Invalidating dead proxy {_proxy_url}, failure #{_proxy_consecutive_failures + 1}")
    _proxy_cache = None
    _proxy_url = None
    _proxy_consecutive_failures += 1
    if _proxy_consecutive_failures >= 3:
        logging.error("❌ Too many proxy failures (3 consecutive) — giving up on proxy for this run")
        _proxy_url = ""  # Empty string = no proxy, will fail fast with direct connection


def scrape_book_list_with_free_proxy(payload, headers):
    """Fallback: Get book list via free proxy from monosans/proxy-list GitHub repo"""
    logging.info("Using free proxy from monosans/proxy-list to bypass geo-blocking")

    working_proxy = get_working_proxy()
    if not working_proxy:
        logging.error("No working proxy found")
        return []

    try:
        response = requests.post(
            NORLI_GRAPHQL_API,
            json=payload,
            headers=headers,
            proxies={'http': working_proxy, 'https': working_proxy},
            timeout=30
        )

        if response.status_code == 200:
            data = response.json()
            if 'data' in data and 'categoryList' in data['data']:
                categories = data['data']['categoryList']
                if categories and len(categories) > 0:
                    products = categories[0].get('products', {}).get('items', [])
                    books = []
                    for p in products:
                        url_key = p.get('url_key')
                        if not url_key:
                            continue
                        nj = p.get('norli_junior', {}) or {}
                        tg = nj.get('target_group', []) or []
                        cats = [c.get('name', '') for c in p.get('categories', []) if c.get('name')]
                        books.append({
                            'url_key': url_key,
                            'name': p.get('name', ''),
                            'sku': p.get('sku', ''),
                            'target_group': tg,
                            'categories': cats,
                        })
                    logging.info(f"Found {len(books)} books via free proxy")
                    return books

        logging.warning(f"Proxy request failed with status {response.status_code}")
        return []

    except Exception as e:
        logging.error(f"Error using free proxy fallback: {e}")
        return []




def is_suitable_for_sexy_review(categories):
    """Check if book categories are suitable for sexy/flirty reviews based on Norli categories"""
    if not categories:
        # If we can't determine categories, be conservative and skip
        logging.info("No categories found - skipping for safety")
        return False
    
    # Convert all to lowercase for comparison
    categories_lower = [cat.lower() for cat in categories]
    
    # First check for unsuitable categories (immediate disqualify)
    for category in categories_lower:
        for unsuitable in UNSUITABLE_CATEGORIES:
            if unsuitable in category:
                logging.info(f"❌ Unsuitable category: '{category}' contains '{unsuitable}'")
                return False
    
    # Check if any category matches our suitable list
    for category in categories_lower:
        for suitable in SUITABLE_CATEGORIES:
            if suitable in category:
                logging.info(f"✅ Suitable category found: '{category}' matches '{suitable}'")
                return True
    
    # If no unsuitable found and no suitable found, be conservative
    logging.info(f"⚠️  Uncertain categories: {categories} - skipping to be safe")
    return False


def scrape_book_details(url_key):
    """Get book details using GraphQL API with proxy support.
    Returns dict with: url, ean, title, author, year, language, description, image_url"""
    logging.info(f"Fetching book details for {url_key}")
    
    try:
        # Use comprehensive query that includes author info via convert_product_page_attributes
        query = """
        query getProductExtraDetailForProductPage($urlKey: String!) {
          products(filter: {url_key: {eq: $urlKey}}) {
            items {
              id
              name
              sku
              url_key
              norli_junior {
                target_group
              }
              small_image {
                url
              }
              media_gallery {
                url
              }
              description {
                html
              }
              short_description {
                html
              }
              categories {
                name
                url_path
              }
              common_products {
                name
                format
                image {
                  url
                }
                thumbnail {
                  url
                }
              }
              convert_product_page_attributes {
                code
                label
                value
              }
            }
          }
        }
        """
        
        variables = {"urlKey": url_key}
        
        payload = {
            "query": query,
            "variables": variables,
            "operationName": "getProductExtraDetailForProductPage"
        }
        
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'store': 'pwa'
        }
        
        proxies = {'http': _proxy_url, 'https': _proxy_url} if _proxy_url else None
        
        try:
            response = requests.post(NORLI_GRAPHQL_API, json=payload, headers=headers, timeout=15, proxies=proxies)
        except (requests.exceptions.ProxyError, requests.exceptions.ConnectTimeout):
            if _proxy_url:
                _invalidate_proxy()
                fresh_proxy = get_working_proxy(force_refresh=True)
                new_proxies = {'http': fresh_proxy, 'https': fresh_proxy} if fresh_proxy else None
                logging.info(f"🔄 Retrying book details for {url_key} with fresh proxy...")
                response = requests.post(NORLI_GRAPHQL_API, json=payload, headers=headers, timeout=15, proxies=new_proxies)
            else:
                raise
        response.raise_for_status()
        
        # Handle 403 from dead proxy / geo-block — same fallback as scrape_book_list
        if response.status_code == 403:
            logging.warning("GraphQL API returned 403 on book details - geo-blocking/proxy died, trying fresh proxy...")
            _invalidate_proxy()
            fresh_proxy = get_working_proxy(force_refresh=True)
            new_proxies = {'http': fresh_proxy, 'https': fresh_proxy} if fresh_proxy else None
            if new_proxies:
                logging.info(f"🔄 Retrying with fresh proxy: {fresh_proxy}")
                response = requests.post(NORLI_GRAPHQL_API, json=payload, headers=headers, timeout=15, proxies=new_proxies)
                response.raise_for_status()
            else:
                logging.error("No fresh proxy available for book details")
                return None
        
        data = response.json()
        
        if 'data' not in data or 'products' not in data['data']:
            logging.error(f"No product data for {url_key}")
            return None
        
        items = data['data']['products'].get('items', [])
        if not items:
            logging.error(f"No product items for {url_key}")
            return None
        
        product = items[0]
        
        # Build book URL using category url_path for correct URL structure
        # Find the most specific category (longest url_path that's not just "boker")
        categories = product.get('categories', [])
        category_path = None
        max_depth = 0
        
        for cat in categories:
            url_path = cat.get('url_path', '')
            if url_path and url_path != 'boker':
                depth = url_path.count('/')
                if depth > max_depth:
                    max_depth = depth
                    category_path = url_path
        
        # Construct URL: https://www.norli.no/{category_url_path}/{url_key}
        if category_path:
            book_url = f"https://www.norli.no/{category_path}/{url_key}"
        else:
            # Fallback to a generic path if no specific category found
            book_url = f"https://www.norli.no/boker/{url_key}"
        
        logging.info(f"Constructed URL: {book_url}")
        
        # Extract description from HTML
        desc_html = product.get('description', {}).get('html', '')
        if not desc_html:
            desc_html = product.get('short_description', {}).get('html', '')
        
        description = ''
        if desc_html:
            soup = BeautifulSoup(desc_html, 'html.parser')
            description = soup.get_text(separator=' ', strip=True)
        
        # Extract author from convert_product_page_attributes
        author = ''
        year = ''
        language = 'Norwegian'
        for attr in product.get('convert_product_page_attributes', []):
            code = attr.get('code', '')
            value = attr.get('value', '')
            if code == 'contributorinfo' and not author:
                # Format: "Author Name (Forfatter) ; Translator (Oversetter)"
                parts = value.split(' ; ')
                if parts:
                    author = parts[0].replace(' (Forfatter)', '').strip()
            elif code == 'editionreleaseyear' and not year:
                year = value.strip()
            elif code == 'language':
                language = value.strip() if value else 'Norwegian'
        
        # Build initial book data
        book_data = {
            'url': book_url,
            'ean': product.get('sku', ''),
            'title': product.get('name', ''),
            'author': author,
            'year': year,
            'language': language,
            'description': description,
            'reviews': '',
            'image_url': ''  # Will be set after scraping
        }
        
        # Use image URL from GraphQL main product (not common_products)
        # The media_gallery and small_image URLs are correct for the specific book
        image_url = ''
        page_response = None  # Initialize for later use
        
        # Priority 1: media_gallery (usually better quality)
        media_gallery = product.get('media_gallery', [])
        if media_gallery and len(media_gallery) > 0:
            image_url = media_gallery[0].get('url', '')
            if image_url:
                logging.info(f"Using media_gallery image: {image_url}")
        
        # Priority 2: small_image (fallback)
        if not image_url:
            small_image = product.get('small_image', {})
            if small_image and small_image.get('url'):
                image_url = small_image['url']
                logging.info(f"Using small_image: {image_url}")
        
        # Transform checkout.norli.no URLs to www.norli.no format (required for external embedding)
        # From: https://checkout.norli.no/media/catalog/product/cache/{hash}/9/7/9788202869885_1_13.jpg
        # To: https://www.norli.no/media/catalog/product/9/7/9788202869885_1_13.jpg
        if image_url:
            image_url = image_url.replace('checkout.norli.no', 'www.norli.no')
            # Remove cache path: /cache/{hash}/
            if '/cache/' in image_url:
                parts = image_url.split('/media/catalog/product/')
                if len(parts) == 2:
                    # Extract everything after cache/{hash}/
                    after_product = parts[1]
                    if after_product.startswith('cache/'):
                        # Skip 'cache/{hash}/' parts (first 2 parts after split)
                        remaining_parts = after_product.split('/')
                        if len(remaining_parts) > 2:
                            after_cache = '/'.join(remaining_parts[2:])
                            image_url = parts[0] + '/media/catalog/product/' + after_cache
            logging.info(f"Transformed image URL: {image_url}")
        
        book_data['image_url'] = image_url
        logging.info(f"Extracted: {book_data['title']}" + (f" by {book_data['author']}" if book_data['author'] else ""))
        return book_data
        
    except Exception as e:
        logging.error(f"Error fetching book details: {e}")
        return None


def generate_book_review(book_data):
    """Generate a flirty 'book daddy' review using GPT-4o"""
    logging.info(f"Generating review for {book_data['title']}")
    
    if not API_KEY:
        logging.error("API key (KEY_GITHUB_TOKEN) not defined")
        return None
    
    # Build the prompt
    prompt = f"""Write a flirty, sexy, and funny book review in Norwegian as a "book daddy". Maximum 700 characters. Use a playful and seductive tone throughout.

CRITICAL RULES:
- Write ONLY the flirty review text - no technical details, no metadata
- DO NOT mention the book title, author name, or year in your review
- Just pure entertaining review content that makes people want to read the book
- Focus on the content, themes, and experience of reading it
- Make it sexy, funny, and irresistible

Book context (DO NOT repeat these in your review):
Title: '{book_data['title']}'
Author: '{book_data['author']}'
Year: '{book_data['year']}'
Language: '{book_data['language']}'
Description: {book_data['description']}
Customer reviews: {book_data['reviews']}

Write 2-3 engaging paragraphs that flow naturally. Focus on why this book is irresistible based on the description and themes."""
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    body = {
        "model": MODEL_NAME,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "max_tokens": 220,  # Roughly 700-750 chars
        "temperature": 0.9
    }
    
    try:
        resp = requests.post(API_ENDPOINT, json=body, headers=headers, timeout=60)
        resp.raise_for_status()
        
        data = resp.json()
        
        # Debug logging
        logging.debug(f"API Response: {json.dumps(data, indent=2)}")
        
        # Check if response has expected structure
        if "choices" not in data or len(data["choices"]) == 0:
            logging.error(f"Unexpected API response structure: {data}")
            return None
        
        message = data["choices"][0].get("message", {})
        if "content" not in message:
            logging.error(f"No content in message: {message}")
            return None
        
        review = message["content"].strip()
        
        logging.info(f"✅ Generated review ({len(review)} chars)")
        
        # Check if review is too long for 3 posts (max ~820 chars for content)
        max_review_length = 820
        if len(review) > max_review_length:
            logging.warning(f"Review is {len(review)} chars, requesting shorter version from GPT-4o")
            return shorten_book_review(review, book_data, max_review_length)
        
        return review
        
    except requests.exceptions.RequestException as e:
        logging.error(f"HTTP error calling OpenAI API: {e}")
        if hasattr(e.response, 'text'):
            logging.error(f"Response: {e.response.text}")
        return None
    except KeyError as e:
        logging.error(f"KeyError parsing API response: {e}")
        logging.error(f"Full response: {data if 'data' in locals() else 'No response data'}")
        return None
    except Exception as e:
        logging.error(f"Error calling OpenAI API: {e}")
        return None


def shorten_book_review(current_review, book_data, target_length):
    """Ask GPT-4o to shorten an existing review"""
    logging.info(f"Shortening review from {len(current_review)} to ~{target_length} chars")
    
    if not API_KEY:
        logging.error("API key (KEY_GITHUB_TOKEN) not defined")
        return current_review
    
    shorten_prompt = f"""The following book review is too long. Please rewrite it to be maximum {target_length} characters while keeping it flirty, sexy, funny, and engaging. Maintain the playful seductive tone.

Current review ({len(current_review)} chars):
{current_review}

RULES:
- Keep the same tone and style
- Make it shorter but still irresistible
- DO NOT add title, author, or year
- Aim for {target_length} characters or less"""
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    body = {
        "model": MODEL_NAME,
        "messages": [
            {
                "role": "user",
                "content": shorten_prompt
            }
        ],
        "max_tokens": 180,
        "temperature": 0.8
    }
    
    try:
        resp = requests.post(API_ENDPOINT, json=body, headers=headers, timeout=60)
        resp.raise_for_status()
        
        data = resp.json()
        
        message = data["choices"][0].get("message", {})
        if "content" not in message:
            logging.error(f"No content in shortening response")
            return current_review
        
        shortened = message["content"].strip()
        
        logging.info(f"✅ Shortened review to {len(shortened)} chars")
        return shortened
        
    except Exception as e:
        logging.error(f"Error shortening review: {e}")
        return current_review


def post_to_bluesky(review_text, book_data=None):
    """Post the book review to Bluesky as a thread (max 3 posts) with book cover and link. Returns post URL or None."""
    if not BSKY_HANDLE or not BSKY_PASSWORD:
        logging.error("Bluesky credentials not defined")
        return None
    
    try:
        client = Client()
        client.login(BSKY_HANDLE.strip(), BSKY_PASSWORD.strip())
        
        max_length = 290  # Leave some margin
        max_posts = 3
        
        # Split review into chunks for thread (max 3 posts)
        # Strategy: Split by sentences (periods), keep continuing naturally without truncation
        
        # Split into sentences
        sentences = []
        for sentence in review_text.split('. '):
            s = sentence.strip()
            if s:
                # Add period back unless it's the last sentence
                if not s.endswith(('.', '!', '?')):
                    s += '.'
                sentences.append(s)
        
        # Build posts by adding sentences until we hit the limit
        chunks = []
        current_chunk = ""
        
        for i, sentence in enumerate(sentences):
            test_chunk = current_chunk + (" " if current_chunk else "") + sentence
            
            # Check if adding this sentence would exceed limit
            if len(test_chunk) > max_length:
                # Save current chunk and start new one
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = sentence
                    # Check if this single sentence is also too long
                    if len(sentence) > max_length:
                        # Split the long sentence
                        split_at = sentence[:max_length].rfind(' ')
                        if split_at == -1:
                            split_at = max_length
                        chunks[-1] = chunks[-1] if len(chunks) > 0 and len(chunks[-1]) > 0 else ""
                        chunks.append(sentence[:split_at].strip())
                        current_chunk = sentence[split_at:].strip()
                else:
                    # Single sentence too long - need to split it
                    split_at = sentence[:max_length].rfind(' ')
                    if split_at == -1:
                        split_at = max_length
                    chunks.append(sentence[:split_at].strip())
                    current_chunk = sentence[split_at:].strip()
            else:
                current_chunk = test_chunk
        
        # Add remaining text
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        # CRITICAL: Validate ALL chunks are under max_length
        validated_chunks = []
        for chunk in chunks:
            while len(chunk) > max_length:
                # Split at sentence or word boundary
                split_at = chunk[:max_length].rfind('. ')
                if split_at == -1:
                    split_at = chunk[:max_length].rfind(' ')
                if split_at == -1:
                    split_at = max_length
                else:
                    split_at += 1  # Include the period
                validated_chunks.append(chunk[:split_at].strip())
                chunk = chunk[split_at:].strip()
            if chunk:
                validated_chunks.append(chunk)
        
        chunks = validated_chunks
        
        # Debug: Log chunk sizes before processing
        logging.info(f"Initial chunks: {len(chunks)} chunks")
        for i, chunk in enumerate(chunks, 1):
            logging.info(f"  Chunk {i}: {len(chunk)} chars")
        
        # Now we need exactly 3 posts:
        # Post 1: First part of review (max 290)
        # Post 2: Second part of review (max 290)
        # Post 3: Final part of review + book link
        
        book_link = f"📚 Les mer: {book_data.get('url', '')}" if book_data else ""
        book_link_length = len(book_link)
        
        if len(chunks) == 1:
            # Single chunk - split it into parts
            text = chunks[0]
            # Post 1: First 290 chars at sentence boundary
            split1 = text[:max_length].rfind('. ')
            if split1 == -1:
                split1 = text[:max_length].rfind(' ')
            if split1 == -1:
                split1 = max_length
            else:
                split1 += 1  # Include the period
            
            post1 = text[:split1].strip()
            remaining = text[split1:].strip()
            
            # Post 2: Next 290 chars at sentence boundary
            if len(remaining) > 0:
                split2 = remaining[:max_length].rfind('. ')
                if split2 == -1:
                    split2 = remaining[:max_length].rfind(' ')
                if split2 == -1:
                    split2 = max_length
                else:
                    split2 += 1
                
                post2 = remaining[:split2].strip()
                post3_text = remaining[split2:].strip()
            else:
                post2 = ""
                post3_text = ""
            
            # Post 3: Remaining text + book link
            if post3_text:
                post3 = post3_text + " " + book_link
            else:
                post3 = book_link
            
            chunks = [post1, post2, post3] if post2 else [post1, post3]
        
        elif len(chunks) == 2:
            # Two chunks - ensure both are under limit, then add book link as post 3
            post1 = chunks[0]
            post2 = chunks[1]
            
            # Ensure post1 is under limit
            if len(post1) > max_length:
                split_at = post1[:max_length].rfind('. ')
                if split_at == -1:
                    split_at = post1[:max_length].rfind(' ')
                if split_at == -1:
                    split_at = max_length
                post1 = post1[:split_at].strip()
            
            # Ensure post2 is under limit
            if len(post2) > max_length:
                split_at = post2[:max_length].rfind('. ')
                if split_at == -1:
                    split_at = post2[:max_length].rfind(' ')
                if split_at == -1:
                    split_at = max_length
                # The overflow goes to post3
                post3_text = post2[split_at:].strip()
                post2 = post2[:split_at].strip()
            else:
                post3_text = ""
            
            # Post 3: remaining text + book link
            if post3_text:
                # Ensure post3 text + link fits
                available_space = max_length - book_link_length - 1
                if len(post3_text) > available_space:
                    truncate_at = post3_text[:available_space].rfind('. ')
                    if truncate_at == -1:
                        truncate_at = post3_text[:available_space].rfind(' ')
                    if truncate_at == -1:
                        truncate_at = available_space
                    post3_text = post3_text[:truncate_at].strip()
                post3 = post3_text + " " + book_link
            else:
                post3 = book_link
            
            chunks = [post1, post2, post3]
        
        elif len(chunks) >= 3:
            # Multiple chunks - need to redistribute content evenly across 3 posts
            # Combine all chunks into one text
            full_text = ' '.join(chunks)
            
            # Strategy: Work backwards from the end
            # Post 3: Reserve space for book link and take as much text as possible
            post3_max = max_length - book_link_length - 1  # -1 for space
            if len(full_text) > post3_max:
                # Find sentence boundary for post 3 content
                post3_split = full_text[:-post3_max]  # Text that won't fit in post 3
                post3_start_pos = len(post3_split)
                
                # Look for sentence boundary before post3 starts
                boundary = post3_split.rfind('. ')
                if boundary == -1:
                    boundary = post3_split.rfind(' ')
                if boundary != -1:
                    post3_start_pos = boundary + 1
                
                post3_text = full_text[post3_start_pos:].strip()
                remaining_text = full_text[:post3_start_pos].strip()
            else:
                # All text fits in post 3
                post3_text = full_text
                remaining_text = ""
            
            post3 = post3_text + " " + book_link if post3_text else book_link
            
            # Ensure post 3 doesn't exceed 300 chars total
            while len(post3) > 300:
                # Trim post3_text
                trim_at = post3_text.rfind('. ')
                if trim_at == -1:
                    trim_at = post3_text.rfind(' ')
                if trim_at == -1:
                    trim_at = len(post3_text) - 10
                if trim_at > 0:
                    post3_text = post3_text[:trim_at].strip()
                    post3 = post3_text + " " + book_link if post3_text else book_link
                else:
                    break
            
            # Now split remaining_text between post 1 and post 2
            if remaining_text:
                # Try to split roughly in half
                mid_point = len(remaining_text) // 2
                
                # Find sentence boundary near midpoint
                search_start = max(0, mid_point - 100)
                search_end = min(len(remaining_text), mid_point + 100)
                search_region = remaining_text[search_start:search_end]
                
                split_pos = search_region.rfind('. ')
                if split_pos == -1:
                    split_pos = search_region.rfind(' ')
                
                if split_pos != -1:
                    actual_split = search_start + split_pos + 1
                else:
                    actual_split = mid_point
                
                post1 = remaining_text[:actual_split].strip()
                post2 = remaining_text[actual_split:].strip()
                
                # Ensure neither exceeds max_length
                if len(post1) > max_length:
                    trim_at = post1[:max_length].rfind('. ')
                    if trim_at == -1:
                        trim_at = post1[:max_length].rfind(' ')
                    if trim_at == -1:
                        trim_at = max_length
                    post1 = post1[:trim_at].strip()
                
                if len(post2) > max_length:
                    trim_at = post2[:max_length].rfind('. ')
                    if trim_at == -1:
                        trim_at = post2[:max_length].rfind(' ')
                    if trim_at == -1:
                        trim_at = max_length
                    post2 = post2[:trim_at].strip()
            else:
                post1 = ""
                post2 = ""
            
            # Assemble final chunks (skip empty posts)
            chunks = []
            if post1:
                chunks.append(post1)
            if post2:
                chunks.append(post2)
            chunks.append(post3)
        
        # Final logging: Show what we're about to post
        logging.info(f"Final thread structure: {len(chunks)} posts")
        for i, chunk in enumerate(chunks, 1):
            logging.info(f"  Post {i}: {len(chunk)} chars")
        
        logging.info(f"Creating {len(chunks)}-post thread")
        
        # Upload book cover image for first post
        embed = None
        if book_data and book_data.get('image_url'):
            try:
                img_resp = requests.get(book_data['image_url'], timeout=30)
                if img_resp.status_code == 200:
                    blob = client.upload_blob(img_resp.content).blob
                    embed = models.AppBskyEmbedImages.Main(
                        images=[
                            models.AppBskyEmbedImages.Image(
                                image=blob,
                                alt=f"Book cover: {book_data.get('title', 'Book')}"
                            )
                        ]
                    )
                    logging.info("✅ Uploaded book cover image")
            except Exception as e:
                logging.warning(f"Could not upload image: {e}")
        
        # Post first message with image
        root_post = client.app.bsky.feed.post.create(
            repo=client.me.did,
            record=models.AppBskyFeedPost.Record(
                text=chunks[0],
                created_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                embed=embed
            )
        )
        
        parent = root_post
        
        # Post remaining as replies
        for chunk in chunks[1:]:
            time.sleep(1)  # Be nice to the API
            parent = client.app.bsky.feed.post.create(
                repo=client.me.did,
                record=models.AppBskyFeedPost.Record(
                    text=chunk,
                    created_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    reply=models.AppBskyFeedPost.ReplyRef(
                        root=models.ComAtprotoRepoStrongRef.Main(
                            uri=root_post.uri,
                            cid=root_post.cid
                        ),
                        parent=models.ComAtprotoRepoStrongRef.Main(
                            uri=parent.uri,
                            cid=parent.cid
                        )
                    )
                )
            )
        
        post_url = f"https://bsky.app/profile/{BSKY_HANDLE}/post/{root_post.uri.split('/')[-1]}"
        logging.info(f"✅ Posted {len(chunks)}-post thread to Bluesky: {post_url}")
        return post_url
        
    except Exception as e:
        logging.error(f"Error posting to Bluesky: {e}")
        return None


def load_state():
    """Load previously reviewed books"""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, 'r') as f:
                state = json.load(f)
                # Migrate old format if needed
                if "reviewed_urls" in state and "reviewed_books" not in state:
                    state["reviewed_books"] = []
                    state.pop("reviewed_urls", None)
                return state
        except Exception as e:
            logging.warning(f"Could not load state: {e}")
    return {"reviewed_books": [], "stats": {"total_reviews": 0, "total_posted": 0}}


def save_state(state):
    """Save state of reviewed books"""
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        logging.error(f"Could not save state: {e}")


def main():
    logging.info("🎭 Starting Norli Book Daddy Bot")
    
    # Load state
    state = load_state()
    reviewed_books = state.get("reviewed_books", [])
    reviewed_eans = {book["ean"] for book in reviewed_books if "ean" in book}
    stats = state.get("stats", {"total_reviews": 0, "total_posted": 0})
    
    logging.info(f"Previously reviewed: {len(reviewed_eans)} books (by EAN)")
    logging.info(f"All-time stats: {stats['total_reviews']} reviews generated, {stats['total_posted']} posted")
    
    # Get list of books (includes target_group and categories already)
    books = scrape_book_list()
    
    if not books:
        logging.error("No books found on the monthly new books page!")
        logging.info("Canceling run - no books available")
        exit(78)  # Exit code 78 means "no new books to review"
    
    # Filter out already reviewed books and find first suitable one
    new_books = []
    for book in books:
        url_key = book['url_key']
        # EAN is embedded in url_key (last 13 digits after hyphen)
        ean_match = re.search(r'-?(978\d{10})$', url_key)
        if ean_match:
            ean = ean_match.group(1)
            if ean not in reviewed_eans:
                new_books.append((book, ean))
        else:
            logging.debug(f"Skipping url_key without EAN: {url_key}")
    
    if not new_books:
        logging.info("🛑 No new books to review! All books on the page have been reviewed.")
        logging.info("Canceling GitHub Action run - no new books available")
        exit(78)  # Exit code 78 means "no new books to review"
    
    logging.info(f"Found {len(new_books)} new books to review (not yet reviewed by EAN)")
    
    # Filter books by target group and category — data is already fetched, no extra queries needed
    # STOP at first suitable book
    logging.info("\n🔍 Checking books to find first suitable book for sexy review...")
    selected_book = None
    selected_ean = None
    
    for book, ean in new_books:
        url_key = book['url_key']
        logging.info(f"\n📚 Checking: {url_key}")
        
        # Check target_group - must include 'Voksen' (Adult)
        target_groups = book.get('target_group', [])
        if 'Voksen' not in target_groups:
            logging.info(f"  ❌ Skipping: Not for adults (target_group={target_groups})")
            continue
        
        # Check categories using pre-fetched data
        categories = book.get('categories', [])
        if is_suitable_for_sexy_review(categories):
            selected_book = book
            selected_ean = ean
            logging.info(f"  ✅ Found suitable book: {url_key}")
            logging.info(f"📖 Categories: {categories}")
            break
        else:
            logging.info(f"  ❌ Skipping: Unsuitable categories")
    
    if not selected_book:
        logging.info("\n🛑 No suitable books found for sexy reviews today!")
        logging.info("All available books are in categories that don't fit the flirty 'book daddy' style.")
        logging.info("Skipping post for today - will try again tomorrow.")
        exit(78)  # Exit code 78 means "no suitable books to review"
    
    logging.info(f"\n✅ Selected first suitable book!")
    logging.info(f"📚 URL key: {selected_book['url_key']}")
    
    # Get book details (uses proxy if needed)
    book_data = scrape_book_details(selected_book['url_key'])
    
    if not book_data or not book_data['title']:
        logging.error("Could not extract book details!")
        return
    
    # Generate review
    review = generate_book_review(book_data)
    
    if not review:
        logging.error("Could not generate review!")
        return
    
    logging.info(f"\n{'='*60}")
    logging.info(f"BOOK DADDY REVIEW:")
    logging.info(f"{'='*60}")
    logging.info(review)
    logging.info(f"{'='*60}\n")
    
    # Post to Bluesky
    post_url = post_to_bluesky(review, book_data)
    if post_url:
        # Update state with EAN and Bluesky post link
        reviewed_entry = {
            "ean": book_data['ean'],
            "title": book_data['title'],
            "author": book_data['author'],
            "norli_url": book_data['url'],
            "bluesky_post": post_url,
            "reviewed_at": datetime.now(timezone.utc).isoformat()
        }
        reviewed_books.append(reviewed_entry)
        stats['total_reviews'] += 1
        stats['total_posted'] += 1
        
        state['reviewed_books'] = reviewed_books
        state['stats'] = stats
        save_state(state)
        
        logging.info("✅ Success! Book review posted to Bluesky")
        logging.info(f"📝 Tracked EAN: {book_data['ean']}")
        logging.info(f"🔗 Bluesky post: {post_url}")
    else:
        logging.error("❌ Failed to post to Bluesky")
    
    logging.info(f"\n=== SESSION SUMMARY ===")
    logging.info(f"Book: {book_data['title']} by {book_data['author']}")
    logging.info(f"EAN: {book_data['ean']}")
    logging.info(f"Review length: {len(review)} characters")
    logging.info(f"Total books reviewed: {len(reviewed_books)}")
    logging.info(f"All-time totals: {stats['total_reviews']} reviews, {stats['total_posted']} posted")


if __name__ == "__main__":
    main()
