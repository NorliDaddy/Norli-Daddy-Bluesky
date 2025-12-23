#!/usr/bin/env python3
"""
Norli Book Daddy Bot - Flirty Book Reviews for Bluesky
Scrapes Norli.no for new books, generates sexy book reviews using GPT-4o, and posts to Bluesky.
"""

import json
import logging
import os
import random
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from atproto import Client, models
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

load_dotenv()

# API Configuration
API_KEY = os.getenv("KEY_GITHUB_TOKEN")  # Azure OpenAI via GitHub Models
API_ENDPOINT = "https://models.inference.ai.azure.com/chat/completions"
MODEL_NAME = "gpt-4o"

# Bluesky Configuration
BSKY_HANDLE = os.getenv("BSKY_HANDLE")
BSKY_PASSWORD = os.getenv("BSKY_PASSWORD")

# URLs
NORLI_NEW_BOOKS_URL = "https://www.norli.no/boker/aktuelt-og-anbefalt/manedens-nyheter"

# State management
STATE_FILE = Path("book_state.json")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def get_selenium_driver():
    """Create a headless Selenium Chrome driver"""
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver


def scrape_book_list():
    """Scrape the list of new books from Norli.no using Selenium (JavaScript rendering)"""
    logging.info(f"Fetching book list from {NORLI_NEW_BOOKS_URL}")
    
    driver = None
    try:
        driver = get_selenium_driver()
        driver.get(NORLI_NEW_BOOKS_URL)
        
        # Wait for content to load (adjust selector as needed)
        time.sleep(5)  # Give React time to render
        
        # Get page source after JavaScript execution
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Find all book links
        book_links = []
        
        # Try multiple possible selectors
        for selector in [
            'a[href*="/boker/"]',
            '.product-item a',
            '.book-item a',
            'article a[href*="/boker/"]',
            '[data-testid*="product"] a',
            '.ProductItem a'
        ]:
            elements = soup.select(selector)
            if elements:
                for link in elements:
                    href = link.get('href')
                    if href and '/boker/' in href and '-978' in href:  # ISBN pattern
                        # Make absolute URL
                        if href.startswith('/'):
                            href = f"https://www.norli.no{href}"
                        if href not in book_links:
                            book_links.append(href)
        
        # Remove duplicates
        book_links = list(set(book_links))
        
        logging.info(f"Found {len(book_links)} book URLs")
        return book_links
        
    except Exception as e:
        logging.error(f"Error scraping book list: {e}")
        return []
    finally:
        if driver:
            driver.quit()


def scrape_book_details(book_url):
    """Scrape detailed information about a specific book using Selenium"""
    logging.info(f"Scraping book details from {book_url}")
    
    driver = None
    try:
        driver = get_selenium_driver()
        driver.get(book_url)
        
        # Wait for content to load
        time.sleep(5)  # Give React time to render
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Extract book information (adjust selectors based on actual Norli HTML)
        book_data = {
            'url': book_url,
            'ean': '',
            'title': '',
            'author': '',
            'year': '',
            'language': '',
            'description': '',
            'reviews': '',
            'image_url': ''
        }
        
        # Extract EAN from URL (pattern: -9788202806453)
        import re
        ean_match = re.search(r'-(978\d{10})(?:\?|$)', book_url)
        if ean_match:
            book_data['ean'] = ean_match.group(1)
        else:
            logging.warning(f"Could not extract EAN from URL: {book_url}")
        
        # Try to extract title
        title_selectors = ['h1', '.product-title', '.book-title', 'h1.title', '[data-testid="product-title"]']
        for selector in title_selectors:
            element = soup.select_one(selector)
            if element:
                book_data['title'] = element.get_text(strip=True)
                if book_data['title']:
                    break
        
        # Try to extract author
        author_selectors = [
            '.productFullDetailNorli-authors-cdP a',  # Norli specific
            '.productFullDetailNorli-authors-cdP',    # Norli specific fallback
            'a[href*="/forfatter/"]', 
            '.author', 
            '.product-author', 
            'span[itemprop="author"]', 
            '[data-testid="author"]'
        ]
        for selector in author_selectors:
            element = soup.select_one(selector)
            if element:
                book_data['author'] = element.get_text(strip=True)
                if book_data['author']:
                    break
        
        # Try to extract publication year
        year_selectors = ['.publication-year', '.year', 'span[itemprop="datePublished"]', '[data-testid="year"]']
        for selector in year_selectors:
            element = soup.select_one(selector)
            if element:
                text = element.get_text(strip=True)
                # Extract 4-digit year
                import re
                year_match = re.search(r'\b(20\d{2}|19\d{2})\b', text)
                if year_match:
                    book_data['year'] = year_match.group(1)
                    break
        
        # If no year found, try searching all text
        if not book_data['year']:
            import re
            text = soup.get_text()
            year_match = re.search(r'\b(202[0-9]|201[0-9])\b', text)
            if year_match:
                book_data['year'] = year_match.group(1)
        
        # Try to extract language
        language_selectors = ['.language', 'span[itemprop="inLanguage"]', '[data-testid="language"]']
        for selector in language_selectors:
            element = soup.select_one(selector)
            if element:
                book_data['language'] = element.get_text(strip=True)
                if book_data['language']:
                    break
        
        # Default language if not found
        if not book_data['language']:
            book_data['language'] = 'Norwegian'
        
        # Try to extract description
        desc_selectors = [
            'section[class*="descriptionWrapper"] div[class*="richText"]',  # Norli specific
            '.richText-root-SHY',  # Norli specific
            'section[class*="descriptionWrapper"]',  # Norli specific
            '.description', 
            '.product-description', 
            '[itemprop="description"]', 
            '.book-description', 
            '[data-testid="description"]'
        ]
        for selector in desc_selectors:
            element = soup.select_one(selector)
            if element:
                # Get text from all <p> tags if they exist, otherwise get all text
                paragraphs = element.find_all('p')
                if paragraphs:
                    book_data['description'] = ' '.join([p.get_text(strip=True) for p in paragraphs])
                else:
                    book_data['description'] = element.get_text(strip=True)
                
                if len(book_data['description']) > 50:  # Make sure it's substantial
                    break
        
        # Try to extract customer reviews
        # Look for review sections
        review_keywords = ['anmeldelse', 'reviews', 'omtale']
        for keyword in review_keywords:
            review_sections = soup.find_all(['div', 'section'], string=lambda t: t and keyword.lower() in t.lower())
            if review_sections:
                for section in review_sections:
                    parent = section.find_parent(['div', 'section'])
                    if parent:
                        reviews_text = parent.get_text(separator='\n', strip=True)
                        if len(reviews_text) > 100:  # Has substantial content
                            book_data['reviews'] = reviews_text
                            break
                if book_data['reviews']:
                    break
        
        # Also try direct review selectors
        if not book_data['reviews']:
            review_selectors = ['.reviews', '.customer-reviews', '.anmeldelser', '#reviews', '[data-testid="reviews"]']
            for selector in review_selectors:
                element = soup.select_one(selector)
                if element:
                    book_data['reviews'] = element.get_text(separator='\n', strip=True)
                    if len(book_data['reviews']) > 50:
                        break
        
        # Try to extract book cover image
        image_selectors = [
            '.carouselGallery-image-gHz[alt="image-product"]',  # Norli specific
            'img[alt="image-product"]',
            '.product-image img',
            '[itemprop="image"]',
            '.book-cover img'
        ]
        for selector in image_selectors:
            img_elements = soup.select(selector)
            for img in img_elements:
                src = img.get('src', '')
                # Look for the large image, not the placeholder or preview
                if src and '/media/catalog/product/' in src and 'width=728' in src:
                    # Make absolute URL if needed
                    if src.startswith('/'):
                        book_data['image_url'] = f"https://www.norli.no{src}"
                    else:
                        book_data['image_url'] = src
                    break
            if book_data['image_url']:
                break
        
        logging.info(f"Extracted book: {book_data['title']} by {book_data['author']}")
        if book_data['image_url']:
            logging.info(f"Found book cover image: {book_data['image_url']}")
        return book_data
        
    except Exception as e:
        logging.error(f"Error scraping book details: {e}")
        return None
    finally:
        if driver:
            driver.quit()


def generate_book_review(book_data):
    """Generate a flirty 'book daddy' review using GPT-4o"""
    logging.info(f"Generating review for {book_data['title']}")
    
    if not API_KEY:
        logging.error("API key (KEY_GITHUB_TOKEN) not defined")
        return None
    
    # Build the prompt
    prompt = f"""Write a flirty, sexy, and funny book review in Norwegian as a "book daddy". Maximum 800 characters. Use a playful and seductive tone throughout.

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
        "max_tokens": 300,  # Allow for 3-post thread
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
            # Multiple chunks - take first two, combine rest with book link for post 3
            post1 = chunks[0]
            post2 = chunks[1]
            post3_text = ' '.join(chunks[2:])
            
            # Ensure post 3 fits with book link
            available_space = max_length - book_link_length - 1  # -1 for space
            if len(post3_text) > available_space:
                # Truncate at sentence boundary
                truncate_at = post3_text[:available_space].rfind('. ')
                if truncate_at == -1:
                    truncate_at = post3_text[:available_space].rfind(' ')
                if truncate_at == -1:
                    truncate_at = available_space
                post3_text = post3_text[:truncate_at].strip()
            
            post3 = post3_text + " " + book_link if post3_text else book_link
            chunks = [post1, post2, post3]
        
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
    
    # Get list of books
    book_urls = scrape_book_list()
    
    if not book_urls:
        logging.error("No books found on the monthly new books page!")
        logging.info("Canceling run - no books available")
        exit(78)  # Exit code 78 means "no new books to review"
    
    # Extract EANs from URLs and filter out already reviewed books
    import re
    new_books = []
    for url in book_urls:
        ean_match = re.search(r'-(978\d{10})(?:\?|$)', url)
        if ean_match:
            ean = ean_match.group(1)
            if ean not in reviewed_eans:
                new_books.append(url)
        else:
            # If we can't extract EAN, include it anyway
            new_books.append(url)
    
    if not new_books:
        logging.info("🛑 No new books to review! All books on the page have been reviewed.")
        logging.info("Canceling GitHub Action run - no new books available")
        exit(78)  # Exit code 78 means "no new books to review"
    
    logging.info(f"Found {len(new_books)} new books to review (not yet reviewed by EAN)")
    
    # Pick a random book
    selected_url = random.choice(new_books)
    logging.info(f"📚 Selected: {selected_url}")
    
    # Scrape book details
    book_data = scrape_book_details(selected_url)
    
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
            "norli_url": selected_url,
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