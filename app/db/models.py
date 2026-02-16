from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class GameStatus(str, enum.Enum):
    pending = "pending"
    active = "active"
    finished = "finished"
    cancelled = "cancelled"


class GameType(str, enum.Enum):
    free = "free"
    paid = "paid"


class TxStatus(str, enum.Enum):
    pending = "pending"
    paid = "paid"
    expired = "expired"
    cancelled = "cancelled"


class WithdrawalStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    failed = "failed"
    refunded = "refunded"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    language: Mapped[str] = mapped_column(String(3), default="en")
    referred_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=True)
    balance: Mapped[Decimal] = mapped_column(Numeric(18, 8), default=Decimal("0"))
    total_games: Mapped[int] = mapped_column(Integer, default=0)
    wins: Mapped[int] = mapped_column(Integer, default=0)
    losses: Mapped[int] = mapped_column(Integer, default=0)

    games_as_p1: Mapped[list[Game]] = relationship("Game", foreign_keys="Game.player1_id", back_populates="player1")
    games_as_p2: Mapped[list[Game]] = relationship("Game", foreign_keys="Game.player2_id", back_populates="player2")


class Game(Base):
    __tablename__ = "games"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger)
    player1_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    player2_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    type: Mapped[GameType] = mapped_column(Enum(GameType, native_enum=False, length=16))
    bet: Mapped[Decimal] = mapped_column(Numeric(18, 8), default=Decimal("0"))
    rounds_to_win: Mapped[int] = mapped_column(Integer, default=1)
    player1_score: Mapped[int] = mapped_column(Integer, default=0)
    player2_score: Mapped[int] = mapped_column(Integer, default=0)
    current_turn_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    last_roll_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    last_roll_value: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[GameStatus] = mapped_column(
        Enum(GameStatus, native_enum=False, length=16),
        default=GameStatus.pending,
    )
    funds_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    turn_deadline: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    player1: Mapped[User] = relationship("User", foreign_keys=[player1_id], back_populates="games_as_p1")
    player2: Mapped[User] = relationship("User", foreign_keys=[player2_id], back_populates="games_as_p2")


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 8))
    currency: Mapped[str] = mapped_column(String(10), default="USDT")
    invoice_id: Mapped[int] = mapped_column(Integer, nullable=True)
    status: Mapped[TxStatus] = mapped_column(
        Enum(TxStatus, native_enum=False, length=16),
        default=TxStatus.pending,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped[User] = relationship("User")


class LedgerEntry(Base):
    __tablename__ = "ledger"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 8))
    reason: Mapped[str] = mapped_column(String(32))
    game_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CommissionEntry(Base):
    __tablename__ = "commission_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    game_id: Mapped[int] = mapped_column(Integer)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 8))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Withdrawal(Base):
    __tablename__ = "withdrawals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 8))
    asset: Mapped[str] = mapped_column(String(10), default="USDT")
    spend_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    transfer_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[WithdrawalStatus] = mapped_column(
        Enum(WithdrawalStatus, native_enum=False, length=16),
        default=WithdrawalStatus.pending,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped[User] = relationship("User")


class GameDraft(Base):
    __tablename__ = "game_drafts"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), primary_key=True)
    opponent_username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    opponent_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    game_type: Mapped[GameType | None] = mapped_column(Enum(GameType, native_enum=False, length=16), nullable=True)
    bet: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    rounds_to_win: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class RematchVote(Base):
    __tablename__ = "rematch_votes"
    __table_args__ = (UniqueConstraint("game_id", "user_id", name="uq_rematch_votes_game_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    game_id: Mapped[int] = mapped_column(Integer, ForeignKey("games.id"))
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class UserActionState(Base):
    __tablename__ = "user_action_states"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), primary_key=True)
    action: Mapped[str] = mapped_column(String(32))
    amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
