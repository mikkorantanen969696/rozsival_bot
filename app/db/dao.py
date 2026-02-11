from __future__ import annotations

from datetime import datetime
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    CommissionEntry,
    Game,
    GameStatus,
    GameType,
    LedgerEntry,
    Transaction,
    TxStatus,
    User,
    Withdrawal,
    WithdrawalStatus,
)


async def get_or_create_user(
    session: AsyncSession,
    user_id: int,
    username: str | None,
    referred_by: int | None = None,
) -> User:
    user = await session.get(User, user_id)
    if user is None:
        user = User(id=user_id, username=username, referred_by=referred_by)
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user

    if username and user.username != username:
        user.username = username
    if referred_by and referred_by != user_id and user.referred_by is None:
        user.referred_by = referred_by
    await session.commit()
    return user


async def set_user_language(session: AsyncSession, user_id: int, language: str) -> None:
    stmt = update(User).where(User.id == user_id).values(language=language)
    await session.execute(stmt)
    await session.commit()


async def get_user_language(session: AsyncSession, user_id: int) -> str:
    stmt = select(User.language).where(User.id == user_id)
    result = await session.execute(stmt)
    return (result.scalar_one_or_none() or "en").lower()


async def get_active_games_for_user(session: AsyncSession, user_id: int) -> list[Game]:
    stmt = select(Game).where(
        Game.status.in_([GameStatus.pending, GameStatus.active]),
        (Game.player1_id == user_id) | (Game.player2_id == user_id),
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def create_game(
    session: AsyncSession,
    chat_id: int,
    player1_id: int,
    player2_id: int,
    game_type: GameType,
    bet: int,
    rounds_to_win: int,
) -> Game:
    game = Game(
        chat_id=chat_id,
        player1_id=player1_id,
        player2_id=player2_id,
        type=game_type,
        bet=bet,
        rounds_to_win=rounds_to_win,
        status=GameStatus.pending,
    )
    session.add(game)
    await session.commit()
    await session.refresh(game)
    return game


async def set_game_status(session: AsyncSession, game_id: int, status: GameStatus) -> None:
    stmt = update(Game).where(Game.id == game_id).values(status=status)
    await session.execute(stmt)
    await session.commit()


async def add_transaction(
    session: AsyncSession,
    user_id: int,
    amount: float,
    invoice_id: int | None,
    status: TxStatus,
) -> Transaction:
    tx = Transaction(user_id=user_id, amount=amount, invoice_id=invoice_id, status=status)
    session.add(tx)
    await session.commit()
    await session.refresh(tx)
    return tx


async def get_tx_by_invoice(session: AsyncSession, invoice_id: int) -> Transaction | None:
    stmt = select(Transaction).where(Transaction.invoice_id == invoice_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_pending_txs_by_user(session: AsyncSession, user_id: int) -> list[Transaction]:
    stmt = select(Transaction).where(Transaction.user_id == user_id, Transaction.status == TxStatus.pending)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def set_tx_status(session: AsyncSession, tx_id: int, status: TxStatus) -> None:
    stmt = update(Transaction).where(Transaction.id == tx_id).values(status=status)
    await session.execute(stmt)
    await session.commit()


async def update_user_balance(session: AsyncSession, user_id: int, delta: float) -> None:
    stmt = update(User).where(User.id == user_id).values(balance=User.balance + delta)
    await session.execute(stmt)
    await session.commit()


async def get_user_balance(session: AsyncSession, user_id: int) -> float:
    stmt = select(User.balance).where(User.id == user_id)
    result = await session.execute(stmt)
    return float(result.scalar_one_or_none() or 0)


async def get_avg_bet(session: AsyncSession) -> float:
    stmt = select(func.avg(Game.bet)).where(Game.type == GameType.paid, Game.status == GameStatus.finished)
    result = await session.execute(stmt)
    return float(result.scalar_one_or_none() or 0)


async def get_active_games(session: AsyncSession) -> list[Game]:
    stmt = select(Game).where(Game.status.in_([GameStatus.pending, GameStatus.active]))
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_system_balance_and_users(session: AsyncSession) -> tuple[float, int]:
    balance_stmt = select(func.sum(User.balance))
    count_stmt = select(func.count(User.id))

    balance_result = await session.execute(balance_stmt)
    count_result = await session.execute(count_stmt)

    balance = float(balance_result.scalar_one_or_none() or 0)
    count = int(count_result.scalar_one_or_none() or 0)
    return balance, count


async def add_ledger_entry(
    session: AsyncSession,
    user_id: int,
    amount: float,
    reason: str,
    game_id: int | None = None,
) -> LedgerEntry:
    entry = LedgerEntry(user_id=user_id, amount=amount, reason=reason, game_id=game_id)
    session.add(entry)
    await session.commit()
    await session.refresh(entry)
    return entry


async def get_recent_ledger(session: AsyncSession, limit: int = 20) -> list[LedgerEntry]:
    stmt = select(LedgerEntry).order_by(LedgerEntry.id.desc()).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def add_commission_entry(session: AsyncSession, user_id: int, game_id: int, amount: float) -> CommissionEntry:
    entry = CommissionEntry(user_id=user_id, game_id=game_id, amount=amount)
    session.add(entry)
    await session.commit()
    await session.refresh(entry)
    return entry


async def create_withdrawal(session: AsyncSession, user_id: int, amount: float) -> Withdrawal:
    withdrawal = Withdrawal(user_id=user_id, amount=amount, status=WithdrawalStatus.pending)
    session.add(withdrawal)
    await session.commit()
    await session.refresh(withdrawal)
    return withdrawal


async def get_withdrawal(session: AsyncSession, withdrawal_id: int) -> Withdrawal | None:
    return await session.get(Withdrawal, withdrawal_id)


async def list_pending_withdrawals(session: AsyncSession, limit: int = 20) -> list[Withdrawal]:
    stmt = select(Withdrawal).where(Withdrawal.status == WithdrawalStatus.pending).order_by(Withdrawal.id.desc()).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def list_recent_withdrawals(session: AsyncSession, limit: int = 20) -> list[Withdrawal]:
    stmt = select(Withdrawal).order_by(Withdrawal.id.desc()).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def set_withdrawal_status(
    session: AsyncSession,
    withdrawal_id: int,
    status: WithdrawalStatus,
    processed_at: datetime | None = None,
    transfer_id: int | None = None,
    spend_id: str | None = None,
    error: str | None = None,
) -> None:
    values = {"status": status}
    if processed_at is not None:
        values["processed_at"] = processed_at
    if transfer_id is not None:
        values["transfer_id"] = transfer_id
    if spend_id is not None:
        values["spend_id"] = spend_id
    if error is not None:
        values["error"] = error
    stmt = update(Withdrawal).where(Withdrawal.id == withdrawal_id).values(**values)
    await session.execute(stmt)
    await session.commit()


async def get_total_locked_banks(session: AsyncSession) -> float:
    stmt = select(func.sum(Game.bet * 2)).where(
        Game.type == GameType.paid,
        Game.status == GameStatus.active,
        Game.funds_locked.is_(True),
    )
    result = await session.execute(stmt)
    return float(result.scalar_one_or_none() or 0)


async def get_total_paid_deposits(session: AsyncSession) -> float:
    stmt = select(func.sum(Transaction.amount)).where(Transaction.status == TxStatus.paid)
    result = await session.execute(stmt)
    return float(result.scalar_one_or_none() or 0)


async def get_referred_count(session: AsyncSession, referrer_id: int) -> int:
    stmt = select(func.count(User.id)).where(User.referred_by == referrer_id)
    result = await session.execute(stmt)
    return int(result.scalar_one_or_none() or 0)


async def get_referral_metrics(session: AsyncSession) -> list[tuple[int, str | None, int, float]]:
    referrer = User.__table__.alias("referrer")
    referred = User.__table__.alias("referred")
    commissions = CommissionEntry.__table__.alias("commissions")

    stmt = (
        select(
            referrer.c.id,
            referrer.c.username,
            func.count(func.distinct(referred.c.id)).label("referred_count"),
            func.coalesce(func.sum(commissions.c.amount), 0).label("commission_sum"),
        )
        .select_from(referrer)
        .outerjoin(referred, referred.c.referred_by == referrer.c.id)
        .outerjoin(commissions, commissions.c.user_id == referred.c.id)
        .group_by(referrer.c.id, referrer.c.username)
        .having(func.count(func.distinct(referred.c.id)) > 0)
        .order_by(func.coalesce(func.sum(commissions.c.amount), 0).desc(), func.count(func.distinct(referred.c.id)).desc())
    )

    result = await session.execute(stmt)
    return [
        (int(row.id), row.username, int(row.referred_count or 0), float(row.commission_sum or 0))
        for row in result.all()
    ]


async def get_referral_structure(session: AsyncSession) -> list[tuple[int, str | None, int, str | None, float]]:
    referrer = User.__table__.alias("referrer")
    referred = User.__table__.alias("referred")
    commissions = CommissionEntry.__table__.alias("commissions")

    stmt = (
        select(
            referrer.c.id.label("referrer_id"),
            referrer.c.username.label("referrer_username"),
            referred.c.id.label("referred_id"),
            referred.c.username.label("referred_username"),
            func.coalesce(func.sum(commissions.c.amount), 0).label("commission_sum"),
        )
        .select_from(referrer)
        .join(referred, referred.c.referred_by == referrer.c.id)
        .outerjoin(commissions, commissions.c.user_id == referred.c.id)
        .group_by(referrer.c.id, referrer.c.username, referred.c.id, referred.c.username)
        .order_by(func.coalesce(func.sum(commissions.c.amount), 0).desc(), referrer.c.id.asc(), referred.c.id.asc())
    )
    result = await session.execute(stmt)
    return [
        (
            int(row.referrer_id),
            row.referrer_username,
            int(row.referred_id),
            row.referred_username,
            float(row.commission_sum or 0),
        )
        for row in result.all()
    ]
