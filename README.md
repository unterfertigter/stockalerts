# Stock Alert Service

This service checks multiple stock values at regular intervals using real-time data from Tradegate Exchange and sends an email alert when a threshold is reached.

## Configuration

Set the following environment variables (see `.env.example`):

- `CHECK_INTERVAL`: Check interval in seconds (default: 300)
- `EMAIL_TO`: Recipient email address
- `EMAIL_FROM`: Sender email address (must be able to send via SMTP)
- `EMAIL_PASSWORD`: Password for sender email
- `SMTP_SERVER`: SMTP server (default: smtp.gmail.com)
- `SMTP_PORT`: SMTP port (default: 587)
- `CONFIG_PATH`: Path to the JSON config file (default: config.json)
- `MAX_FAIL_COUNT`: Maximum allowed consecutive failures before stopping (default: 3)

Create a `config.json` file in the same directory with a list of ISIN/threshold pairs:

```json
[
  {"isin": "US69608A1088", "upper_threshold": 114, "lower_threshold": 110},
  {"isin": "US4581401001", "upper_threshold": 18, "lower_threshold": 15}
]
```

- `upper_threshold` (optional): Alert if price is greater than or equal to this value.
- `lower_threshold` (optional): Alert if price is less than this value.

## How it works

- The script scrapes the real-time price from the Tradegate order book page for each ISIN in the config file.
- If the price meets or exceeds the upper threshold, or falls below the lower threshold, you receive an email alert.

## Build and Run with Docker

```bash
docker build -t stock-alert .

docker run --env-file .env stock-alert
```

## Notes

- No API key is required; the script uses web scraping for real-time prices.
- For Gmail, you may need to use an App Password.
- Web scraping may break if Tradegate changes their website layout.
