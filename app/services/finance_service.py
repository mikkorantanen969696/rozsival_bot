from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Config
from app.crypto.client import CryptoClient
from app.db import dao
from app.db.models import LedgerEntry, Transaction, TxStatus, User, Withdrawal, WithdrawalStatus


@dataclass
class InvoiceResult:
    invoice_id: int
    pay_url: str


class FinanceService:
    def __init__(self, session_factory, crypto: CryptoClient, config: Config):
        self._session_factory = session_factory
        self._crypto = crypto
        self._config = config
        self._logger = logging.getLogger(__name__)

    async def ensure_user(
        self,
        session: AsyncSession,
        user_id: int,
        username: str | None,
        referred_by: int | None = None,
    ):
        return await dao.get_or_create_user(session, user_id, username, referred_by=referred_by)

    async def get_balance(self, session: AsyncSession, user_id: int) -> Decimal:
        return await dao.get_user_balance(session, user_id)

    async def add_balance(self, session: AsyncSession, user_id: int, amount: Decimal) -> None:
        await session.execute(update(User).where(User.id == user_id).values(balance=User.balance + amount))
        session.add(LedgerEntry(user_id=user_id, amount=amount, reason="deposit", game_id=None))
        await session.commit()

    async def get_app_balance_usdt(self) -> Decimal:
        balances = await self._crypto.get_balance()
        total = Decimal("0")
        for b in balances or []:
            if getattr(b, "currency_code", "") == "USDT":
                total += Decimal(str(getattr(b, "available", 0) or 0))
                total += Decimal(str(getattr(b, "onhold", 0) or 0))
        return total

    async def withdraw_to_cryptobot(self, session: AsyncSession, user_id: int, amount: Decimal) -> tuple[bool, str | None]:
        if amount < self._config.min_withdraw:
            return False, f"Minimum withdrawal is {self._config.min_withdraw:.2f} USDT."
        app_balance = await self.get_app_balance_usdt()
        if amount > app_balance:
            return False, "App balance is insufficient for this withdrawal."

        reserve_stmt = (
            update(User)
            .where(User.id == user_id, User.balance >= amount)
            .values(balance=User.balance - amount)
        )
        reserve_result = await session.execute(reserve_stmt)
        if reserve_result.rowcount != 1:
            await session.rollback()
            return False, "Insufficient balance."

        withdrawal = Withdrawal(user_id=user_id, amount=amount, status=WithdrawalStatus.pending)
        session.add(withdrawal)
        await session.commit()
        await session.refresh(withdrawal)
        spend_id = f"wd:{withdrawal.id}"

        try:
            transfer = await self._crypto.transfer(user_id=user_id, amount=float(amount), asset="USDT", spend_id=spend_id)
        except Exception as exc:
            self._logger.exception("withdraw transfer failed: user=%s amount=%s spend_id=%s", user_id, amount, spend_id)
            await session.execute(update(User).where(User.id == user_id).values(balance=User.balance + amount))
            withdrawal.status = WithdrawalStatus.failed
            withdrawal.processed_at = datetime.utcnow()
            withdrawal.spend_id = spend_id
            withdrawal.error = str(exc)
            session.add(LedgerEntry(user_id=user_id, amount=amount, reason="withdraw_refund", game_id=None))
            await session.commit()
            return False, "Transfer failed. Please open @CryptoBot and try again, or contact support."

        session.add(LedgerEntry(user_id=user_id, amount=-amount, reason="withdraw", game_id=None))
        withdrawal.status = WithdrawalStatus.approved
        withdrawal.processed_at = datetime.utcnow()
        withdrawal.transfer_id = getattr(transfer, "transfer_id", None)
        withdrawal.spend_id = spend_id
        await session.commit()
        return True, None

    async def create_deposit(self, session: AsyncSession, user_id: int, amount: Decimal) -> InvoiceResult:
        invoice = await self._crypto.create_invoice(amount=float(amount), asset="USDT")
        await dao.add_transaction(session, user_id, amount, invoice.invoice_id, TxStatus.pending)
        pay_url = (
            getattr(invoice, "pay_url", None)
            or getattr(invoice, "bot_invoice_url", None)
            or getattr(invoice, "url", None)
        )
        if not pay_url:
            raise RuntimeError("Invoice URL is missing in CryptoPay response.")
        return InvoiceResult(invoice_id=invoice.invoice_id, pay_url=pay_url)

    async def check_deposit(self, session: AsyncSession, invoice_id: int) -> bool:
        invoice = await self._crypto.get_invoice(invoice_id)
        if not invoice:
            return False

        tx = await dao.get_tx_by_invoice(session, invoice_id)
        if not tx:
            return False

        if invoice.status == "paid":
            mark_paid_stmt = (
                update(Transaction)
                .where(Transaction.id == tx.id, Transaction.status == TxStatus.pending)
                .values(status=TxStatus.paid)
            )
            mark_paid_result = await session.execute(mark_paid_stmt)
            if mark_paid_result.rowcount != 1:
                await session.rollback()
                return False
            amount = tx.amount
            await session.execute(update(User).where(User.id == tx.user_id).values(balance=User.balance + amount))
            session.add(LedgerEntry(user_id=tx.user_id, amount=amount, reason="deposit", game_id=None))
            await session.commit()
            return True

        if invoice.status in {"expired", "cancelled"}:
            await session.execute(
                update(Transaction)
                .where(Transaction.id == tx.id, Transaction.status == TxStatus.pending)
                .values(status=TxStatus.expired)
            )
            await session.commit()
        return False

    async def close(self) -> None:
        await self._crypto.close()
