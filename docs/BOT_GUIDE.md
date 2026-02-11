# Gionta Bot Guide

## A) Guide for Buyers (Project Owners)

### What You Buy
- Full Telegram dice game bot project.
- Paid and free game modes.
- Built-in CryptoBot deposits/withdrawals.
- SQLite database (easy deploy, no separate PostgreSQL server required).
- Admin panel with referral analytics.
- RU/ENG language support.

### Included Business Logic
- Funds locking on paid game accept.
- Auto payout to winner with commission deduction.
- Refunds on canceled paid games.
- Ledger and withdrawal tracking.
- Referral link format: `https://t.me/<bot_username>?start=<user_id>`.
- Admin referral metrics:
  - referrer (who invited),
  - invited users count,
  - total commission paid by invited users.

### Deployment Steps
1. Install Python 3.11+.
2. Upload project files to server.
3. Install dependencies:
```bash
pip install -r requirements.txt
```
4. Configure `.env`:
```env
DATABASE_URL=sqlite+aiosqlite:///./data/gionta.db
BOT_TOKEN=...
CRYPTO_TOKEN=...
ADMIN_ID=...
COMMISSION_PERCENT=10
GAME_TIMEOUT_SECONDS=60
MAX_ACTIVE_GAMES_PER_USER=1
MIN_BET=0.1
MAX_BET=1000
MIN_WITHDRAW=1
CLEAR_DB_ON_START=0
```
5. Run:
```bash
python main.py
```
6. Ensure `data/` directory is persistent on hosting.

### Security Notes
- Rotate tokens if they were exposed.
- Never commit `.env` with real tokens.
- Restrict admin access by correct `ADMIN_ID`.

## B) Guide for Bot Users

### Start and Language
1. Open bot in private chat.
2. Send `/start`.
3. Choose language: Russian or English.

### Balance and Deposit
1. Press `Balance`.
2. Press `Deposit`.
3. Pick amount or enter custom amount.
4. Pay invoice in CryptoBot.
5. Press `I paid` to recheck payment status.

### Withdrawal
1. Press `Withdraw`.
2. Enter amount (not below minimum).
3. Confirm withdrawal.

### How to Play in Group
1. Send `/game @username` or reply to player and use `/game`.
2. Choose game type: free or paid.
3. Choose rounds.
4. For paid game: choose bet.
5. Send challenge and wait for accept.
6. Roll dice in turn.

### Referral Program
1. Open `Referrals` in private menu.
2. Copy your referral link.
3. Invite users using this link.
4. Invited users are counted after they start the bot.

### Rules
- Only one active game per user by default.
- Timeout on turn means loss.
- Editing dice message leads to automatic loss.
