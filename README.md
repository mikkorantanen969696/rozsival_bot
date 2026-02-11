# Gionta Dice Bot

Telegram bot for dice battles in group chats with paid matches, deposits/withdrawals via CryptoBot, admin panel, RU/ENG language switch, and referral analytics.

## Stack
- Python 3.11
- aiogram 3.x
- SQLAlchemy async
- SQLite (`sqlite+aiosqlite`)
- CryptoBot Pay API

## Main Features
- Group game flow (`/game @username` or reply challenge).
- Free and paid games.
- Deposits and withdrawals in private chat.
- Turn timeout and anti-cheat for edited dice.
- Admin panel: active games, balances, ledger, withdrawals.
- Language selection: RU/ENG.
- Referral program with admin metrics:
  - who invited users,
  - how many users were invited,
  - how much commission invited users paid.

## Environment Variables
Use `.env`:

| Variable | Description | Example |
|---|---|---|
| `DATABASE_URL` | SQLite async URL | `sqlite+aiosqlite:///./data/gionta.db` |
| `BOT_TOKEN` | Telegram bot token | `123456:ABC` |
| `CRYPTO_TOKEN` | CryptoBot API token | `token` |
| `ADMIN_ID` | Telegram user ID of admin | `123456789` |
| `COMMISSION_PERCENT` | Commission from paid game prize (%) | `10` |
| `GAME_TIMEOUT_SECONDS` | Turn timeout in seconds | `60` |
| `MAX_ACTIVE_GAMES_PER_USER` | Max simultaneous games per user | `1` |
| `MIN_BET` | Minimum bet | `0.1` |
| `MAX_BET` | Maximum bet | `1000` |
| `MIN_WITHDRAW` | Minimum withdrawal | `1` |
| `CLEAR_DB_ON_START` | Clear DB on startup (`0/1`) | `0` |

## Run
```bash
pip install -r requirements.txt
python main.py
```

## Hosting
Project is ready to run on hosting with a local SQLite file:
- DB file will be created at `./data/gionta.db`.
- Ensure persistent storage is enabled on host for `data/`.
- Keep secrets only in environment variables.

## Docs
- Product and end-user instructions: `docs/BOT_GUIDE.md`.
