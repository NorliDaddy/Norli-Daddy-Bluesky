# Norli Book Daddy Bot 📚❤️

An automated bot that discovers new books from Norli.no, generates flirty and funny book reviews in Norwegian using GPT-4o, and posts them to Bluesky as your personal "book daddy".

## How It Works

1. **Fetches book list** from Norli's GraphQL API for [Månedens nyheter](https://www.norli.no/boker/aktuelt-og-anbefalt/manedens-nyheter)

1. **Filters for suitable books** by checking target group (adults) and categories (fiction, not crime/non-fiction)

1. **Extracts book details** via GraphQL API: title, description, categories, and book cover image

1. **Transforms image URLs** from checkout.norli.no to [www.norli.no](http://www.norli.no) format for external embedding

1. **Generates sexy review** using GPT-4o with a flirty "book daddy" persona in Norwegian

1. **Posts to Bluesky** with book cover image and entertaining review thread

## Features

- **GraphQL API integration**: Fast and reliable book data fetching from Norli's API

- **Smart filtering**: Checks target group (adult) and categories to select suitable books for flirty reviews

- **Image URL transformation**: Converts internal image URLs to external-embeddable format

- **AI-powered reviews**: Uses GPT-4o via Azure OpenAI (GitHub Models) to generate entertaining, flirty reviews in Norwegian

- **Book cover images**: Automatically includes high-quality book cover images in Bluesky posts

- **Thread support**: Automatically splits long reviews into Bluesky threads (290 char limit)

- **EAN-based tracking**: Tracks reviewed books by ISBN-13 (EAN) to avoid duplicates

- **Bluesky post links**: Stores links to all posted reviews for reference

- **Daily automation**: Runs automatically via GitHub Actions

- **Smart cancellation**: Exits gracefully when no suitable books are available

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

```
requests
python-dotenv
atproto
beautifulsoup4
lxml
```

**Note**: The bot primarily uses Norli's GraphQL API for data fetching. BeautifulSoup is used for parsing HTML descriptions and optional page scraping fallbacks.

### 3. GitHub Secrets

Set up these secrets in your repository (Settings → Secrets and variables → Actions):

- `KEY_GITHUB_TOKEN`: Your GitHub Personal Access Token for Azure OpenAI (GitHub Models) access

- `BSKY_HANDLE`: Your Bluesky handle (e.g., `username.bsky.social`)

- `BSKY_PASSWORD`: Your Bluesky app password (not your main password!)

### 4. Get GitHub Token for Azure OpenAI

1. Go to [GitHub Personal Access Tokens](https://github.com/settings/tokens)

1. Generate a new token (classic) with appropriate scopes

1. This token provides free access to GPT-4o via Azure OpenAI (GitHub Models)

1. Endpoint: `https://models.inference.ai.azure.com/chat/completions`

1. Use this token in the `KEY_GITHUB_TOKEN` secret

**Note**: This uses Azure OpenAI via GitHub Models, which may have different rate limits than OpenAI directly.

### 5. Bluesky App Password

1. Go to Settings → Privacy and Security → App Passwords

1. Create a new app password for this bot

1. Use this password (not your main password ) in the `BSKY_PASSWORD` secret

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

**GitHub Models Settings**:

- Model: `auto` (selects an eligible model for Copilot Free accounts)

- Max tokens: 500

- Temperature: 0.9 (for creative, varied output)

## Example Review

For the book "Ufred - Russland fra innsiden" by Åsne Seierstad, the bot might generate something like:

> Å, kjære leser! 🔥 Åsne Seierstad tar deg med på en reise som er mer spennende enn en date med en mystisk fremmed. "Ufred" er som en forbudt affære - du vet du burde slappe av, men du klarer ikke å legge den fra deg! 
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

- All books on the monthly page have been reviewed (bot exits with code 78 )

- Wait for Norli.no to add new books to [Månedens nyheter](https://www.norli.no/boker/aktuelt-og-anbefalt/manedens-nyheter)

- Norli.no might have changed their GraphQL API structure

- Check the GraphQL query in `scrape_book_list()` and `scrape_book_details()`

- Verify API endpoint is still `https://www.norli.no/graphql`

- Enable debug logging to see API responses

**"Azure OpenAI API error"**:

- Check your `KEY_GITHUB_TOKEN` is valid

- Verify the token has appropriate permissions

- Check GitHub Models API status

- Ensure GPT-4o model is available

**"Could not extract book details"**:

- GraphQL API response structure might have changed

- Check that media_gallery and small_image fields are still available

- Image URL transformation may need adjustment if Norli changes URL patterns

- Some books may have incomplete information in API

**"Bluesky posting failed"**:

- Check credentials are correct

- Verify app password (not main password )

- Check Bluesky API status

### Manual Testing

Trigger a manual run:

1. Go to Actions tab

1. Select "Norli Book Daddy Bot"

1. Click "Run workflow"

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

## API & Data Extraction Notes

- **GraphQL API**: Primary data source for book lists, details, and images from Norli.no

- **Image URL transformation**: Converts checkout.norli.no URLs to [www.norli.no](http://www.norli.no) format for external embedding

- **Cache path removal**: Strips `/cache/{hash}/` from image URLs to match working format

- **BeautifulSoup + lxml**: Used for parsing HTML descriptions and optional page scraping

- **Multiple fallbacks**: Tries media_gallery → small_image → page scraping for images

- **EAN extraction**: Extracts ISBN-13 from URL patterns like `-9788202869885`

- **Category filtering**: Queries GraphQL for book categories to determine suitability

- **Target group validation**: Ensures books are for adults ("Voksen") before reviewing

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