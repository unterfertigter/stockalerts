# Stock Alert Service

This service checks multiple stock values at regular intervals using real-time data from Tradegate Exchange and sends an email alert when a threshold is reached.

## Configuration

Set the following environment variables in an `.env` file (see `.env.example`) or pass them directly in the `docker run` command with `--env key=value`:

- `CHECK_INTERVAL`: Check interval in seconds (default: 60)
- `EMAIL_TO`: Recipient email address
- `EMAIL_FROM`: Sender email address
- `CONFIG_PATH`: Path to the JSON config file which lists all stock ISINs to be checked (default: `config.json`)
- `MAX_FAIL_COUNT`: Maximum allowed consecutive failures to retrieve a stock price before stopping the service (default: 3)

Create a `config.json` file in the same directory with a list of ISIN/threshold pairs:

```json
[
  {"isin": "US69608A1088", "upper_threshold": 129.87, "lower_threshold": 112.21},
  {"isin": "US4581401001", "upper_threshold": 17.87, "lower_threshold": 17.65}
]
```

- `upper_threshold` (optional): Alert if price is greater than or equal to this value.
- `lower_threshold` (optional): Alert if price is less than or equal this value.

## How it works

- The script scrapes the real-time price from the Tradegate order book page for each ISIN in the config file.
- If the stock price meets or exceeds the upper threshold, or meets or falls below the lower threshold, you receive an email alert for that stock and further alerts will be deactivated for that stock.

## Build and Run with Docker

```bash
docker build -t stock-alert .

docker run --env-file .env stock-alert
```

## Notes

- No API key is required; the script uses web scraping for real-time prices.
- Web scraping may break if Tradegate changes their website layout.
- The service uses the local `sendmail` command for sending emails. No SMTP configuration is required.
