# Norli Book Daddy Bot 📚❤️

An automated bot that discovers new books from Norli.no, generates flirty and funny book reviews in Norwegian using GPT-4o, and posts them to Bluesky as your personal "book daddy".

## How It Works

1. **Scrapes Norli.no** for the latest new books from [Månedens nyheter](https://www.norli.no/boker/aktuelt-og-anbefalt/manedens-nyheter)
2. **Selects random book** from the list that hasn't been reviewed yet
3. **Extracts book details**: title, author, year, language, description, and customer reviews
4. **Generates sexy review** using GPT-4o with a flirty "book daddy" persona in Norwegian
5. **Posts to Bluesky** with the entertaining book review

## Features

- **JavaScript rendering**: Uses Selenium WebDriver to handle Norli.no's React-based SPA
- **Smart scraping**: Extracts comprehensive book information including cover images
- **AI-powered reviews**: Uses GPT-4o via Azure OpenAI (GitHub Models) to generate entertaining, flirty reviews in Norwegian
- **Book cover images**: Automatically includes book cover images in Bluesky posts
- **Thread support**: Automatically splits long reviews into Bluesky threads (290 char limit)
- **EAN-based tracking**: Tracks reviewed books by ISBN-13 (EAN) to avoid duplicates
- **Bluesky post links**: Stores links to all posted reviews for reference
- **Daily automation**: Runs automatically via GitHub Actions
- **Smart cancellation**: Exits gracefully when no new books are available
- **Statistics**: Tracks total reviews generated and posted with full history

## Setup

### 1. Repository Structure
```
your-repo/
├── src/
│   └── main.py
├── requirements.txt
├── .github/
│   └── workflows/
│       └── book-daddy-bot.yml
├── book_state.json (auto-generated)
└── README.md
```

### 2. Required Dependencies

**requirements.txt**:
```txt
requests
python-dotenv
atproto
beautifulsoup4
lxml
selenium
webdriver-manager
```

**Note**: ChromeDriver is automatically downloaded and managed by `webdriver-manager`.

### 3. GitHub Secrets

Set up these secrets in your repository (Settings → Secrets and variables → Actions):

- `KEY_GITHUB_TOKEN`: Your GitHub Personal Access Token for Azure OpenAI (GitHub Models) access
- `BSKY_HANDLE`: Your Bluesky handle (e.g., `username.bsky.social`)
- `BSKY_PASSWORD`: Your Bluesky app password (not your main password!)

### 4. Get GitHub Token for Azure OpenAI

1. Go to [GitHub Personal Access Tokens](https://github.com/settings/tokens)
2. Generate a new token (classic) with appropriate scopes
3. This token provides free access to GPT-4o via Azure OpenAI (GitHub Models)
4. Endpoint: `https://models.inference.ai.azure.com/chat/completions`
5. Use this token in the `KEY_GITHUB_TOKEN` secret

**Note**: This uses Azure OpenAI via GitHub Models, which may have different rate limits than OpenAI directly.

### 5. Bluesky App Password

1. Go to Settings → Privacy and Security → App Passwords
2. Create a new app password for this bot
3. Use this password (not your main password) in the `BSKY_PASSWORD` secret

## Configuration

The bot is configured to run daily at 10:00 AM UTC. You can modify the schedule in `.github/workflows/book-daddy-bot.yml`:

```yaml
on:
  schedule:
    - cron: '0 10 * * *'  # Daily at 10:00 AM UTC
```

## Schedule

The bot runs **once per day**:
- 10:00 AM UTC (11:00 AM CET, 12:00 PM CEST)

Each run:
- Fetches the latest book list from Norli.no
- Selects one random unreviewed book
- Generates a flirty review
- Posts to Bluesky

## How the Review Generation Works

**Prompt Template**:
```
write a book review as a "book daddy" in a flirty tone, very sexy and funny, in norwegian

Book title: [title]
Author: [author]
Year: [year]
Language: [language]
Description: [description]
Customer reviews: [reviews]
```

**GPT-4o Settings**:
- Model: `gpt-4o`
- Max tokens: 500
- Temperature: 0.9 (for creative, varied output)

## Example Review

For the book "Ufred - Russland fra innsiden" by Åsne Seierstad, the bot might generate something like:

> Å, kjære leser! 🔥 Åsne Seierstad tar deg med på en reise som er mer spennende enn en date med en mystisk fremmed. "Ufred" er som en forbudt affære - du vet du burde slappe av, men du klarer ikke å legge den fra deg! 
>
> Med sitt skarpe blikk og sexy intellekt tar vår førstedame av sakprosa deg med inn i Russlands hemmeligste hjørner...

## Statistics

The bot tracks:
- Total books reviewed (all-time)
- Books successfully posted to Bluesky
- Book EAN (ISBN-13) numbers to avoid duplicate reviews
- Bluesky post links for all reviews
- Review timestamps

Statistics are stored in `book_state.json`:

```json
{
  "reviewed_books": [
    {
      "ean": "9788202806453",
      "title": "Ufred",
      "author": "Åsne Seierstad",
      "norli_url": "https://www.norli.no/boker/.../ufred-3-9788202806453",
      "bluesky_post": "https://bsky.app/profile/username.bsky.social/post/...",
      "reviewed_at": "2025-12-17T10:30:45.123456+00:00"
    }
  ],
  "stats": {
    "total_reviews": 42,
    "total_posted": 42
  }
}
```

## Troubleshooting

### Common Issues

**"No books found" or "No new books to review"**:
- All books on the monthly page have been reviewed (bot exits with code 78)
- Wait for Norli.no to add new books to [Månedens nyheter](https://www.norli.no/boker/aktuelt-og-anbefalt/manedens-nyheter)
- Norli.no might have changed their HTML structure
- Check the CSS selectors in `scrape_book_list()` and `scrape_book_details()`
- Enable debug logging to see what's being scraped

**"Azure OpenAI API error"**:
- Check your `KEY_GITHUB_TOKEN` is valid
- Verify the token has appropriate permissions
- Check GitHub Models API status
- Ensure GPT-4o model is available

**"ChromeDriver issues"**:
- WebDriver Manager should auto-download ChromeDriver
- On GitHub Actions, Chrome is pre-installed
- Locally, ensure Chrome/Chromium is installed
- Check firewall isn't blocking driver downloads

**"Could not extract book details"**:
- Book page HTML might vary
- The scraper tries multiple CSS selectors
- Some books may have incomplete information

**"Bluesky posting failed"**:
- Check credentials are correct
- Verify app password (not main password)
- Check Bluesky API status

### Manual Testing

Trigger a manual run:
1. Go to Actions tab
2. Select "Norli Book Daddy Bot"
3. Click "Run workflow"

### Local Testing

```bash
# Set environment variables
export KEY_GITHUB_TOKEN="your-github-token-here"
export BSKY_HANDLE="your-handle.bsky.social"
export BSKY_PASSWORD="your-app-password"

# Install dependencies
pip install -r requirements.txt

# Run the bot
python src/main.py
```

**Note**: Make sure Chrome or Chromium browser is installed for Selenium WebDriver.

## Web Scraping Notes

- **Selenium WebDriver**: Required because Norli.no is a React-based Single Page Application (SPA)
- **Headless Chrome**: Runs in headless mode for automation (no GUI)
- **JavaScript rendering**: Waits 5 seconds for React to load content before scraping
- **BeautifulSoup + lxml**: Parses the rendered HTML after JavaScript execution
- **Multiple selectors**: Tries various CSS selectors as fallbacks for robustness
- **Proper User-Agent**: Mimics real browser to avoid blocking
- **EAN extraction**: Extracts ISBN-13 from URL patterns like `-9788202806453`
- **Book cover images**: Extracts high-resolution images (728px width) from carousel gallery

## File Descriptions

- **`src/main.py`**: Main bot logic (scraping, AI, Bluesky posting)
- **`requirements.txt`**: Python dependencies
- **`.github/workflows/book-daddy-bot.yml`**: GitHub Actions workflow
- **`book_state.json`**: Persistent state (auto-generated, tracked in git)

## Privacy & Ethics

- Only scrapes publicly available book information
- Respects Norli.no's terms of service
- Reviews are clearly AI-generated entertainment
- No personal data collected or stored
- Respects API rate limits

## Customization

### Change Review Style

Modify the prompt in `generate_book_review()`:

```python
prompt = f"""write a book review as a "book daddy" in a flirty tone, very sexy and funny, in norwegian
...
```

### Change Posting Frequency

Edit the cron schedule in `.github/workflows/book-daddy-bot.yml`:

```yaml
- cron: '0 10 * * *'  # Once daily
- cron: '0 */6 * * *'  # Every 6 hours
- cron: '0 0 * * 0'   # Weekly on Sunday
```

### Change Character Limit

Bluesky posts have a 300 character limit. The bot uses 290 to leave margin:

```python
max_length = 290  # Leave some margin
```

### Add More Book Sources

Add additional scraping functions in `main.py` to pull from other bookstores or sources. Note that sites using JavaScript rendering will require Selenium.

## Contributing

Feel free to:
- Improve the web scraping selectors
- Enhance the review prompt
- Add support for other bookstores
- Improve error handling
- Add support for multiple images per post
- Optimize Selenium wait times for faster execution

## License

This project is for educational and entertainment purposes. Please respect:
- Website terms of service
- API rate limits and quotas
- Bluesky community guidelines
- Copyright and attribution for book information

---

**God lesing, kjære! 📚❤️**
