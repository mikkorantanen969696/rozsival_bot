from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def draft_type_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Free 🎲", callback_data="draft:type:free"),
            InlineKeyboardButton(text="Paid 💰", callback_data="draft:type:paid"),
        ],
    ])


def draft_rounds_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="First to 1 🏁", callback_data="draft:rounds:1"),
            InlineKeyboardButton(text="First to 3 🏁", callback_data="draft:rounds:3"),
        ],
    ])


def draft_bet_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="0.1", callback_data="draft:bet:0.1"),
            InlineKeyboardButton(text="0.25", callback_data="draft:bet:0.25"),
            InlineKeyboardButton(text="0.5", callback_data="draft:bet:0.5"),
            InlineKeyboardButton(text="1", callback_data="draft:bet:1"),
        ],
        [
            InlineKeyboardButton(text="2", callback_data="draft:bet:2"),
            InlineKeyboardButton(text="5", callback_data="draft:bet:5"),
            InlineKeyboardButton(text="10", callback_data="draft:bet:10"),
            InlineKeyboardButton(text="15", callback_data="draft:bet:15"),
        ],
        [
            InlineKeyboardButton(text="20", callback_data="draft:bet:20"),
            InlineKeyboardButton(text="25", callback_data="draft:bet:25"),
            InlineKeyboardButton(text="30", callback_data="draft:bet:30"),
            InlineKeyboardButton(text="40", callback_data="draft:bet:40"),
        ],
        [
            InlineKeyboardButton(text="50", callback_data="draft:bet:50"),
            InlineKeyboardButton(text="75", callback_data="draft:bet:75"),
            InlineKeyboardButton(text="100", callback_data="draft:bet:100"),
            InlineKeyboardButton(text="150", callback_data="draft:bet:150"),
        ],
        [
            InlineKeyboardButton(text="200", callback_data="draft:bet:200"),
            InlineKeyboardButton(text="300", callback_data="draft:bet:300"),
            InlineKeyboardButton(text="400", callback_data="draft:bet:400"),
            InlineKeyboardButton(text="500", callback_data="draft:bet:500"),
        ],
    ])


def draft_confirm_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Send challenge 🚀", callback_data="draft:send")],
        [InlineKeyboardButton(text="Cancel ❌", callback_data="draft:cancel")],
    ])


def challenge_keyboard(game_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Accept ✅", callback_data=f"game:accept:{game_id}"),
            InlineKeyboardButton(text="Decline ❌", callback_data=f"game:decline:{game_id}"),
        ]
    ])


def game_rematch_keyboard(game_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Rematch 🔁", callback_data=f"game:rematch:{game_id}")]
    ])


def cancel_existing_game_keyboard(game_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Cancel current game 🧹", callback_data=f"game:cancel:{game_id}")]
    ])
