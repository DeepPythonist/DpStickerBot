from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from database import db
from utils.helpers import get_user_text, get_button_text
import config
import asyncio

router = Router()

async def check_sponsor_membership(bot, user_id: int) -> bool:
    if not config.SPONSOR_CHANNELS:
        return True
    
    for channel in config.SPONSOR_CHANNELS:
        try:
            member = await bot.get_chat_member(channel, user_id)
            if member.status in ['left', 'kicked', 'restricted']:
                return False
        except Exception:
            return False
    return True

def get_sponsor_keyboard(user_id: int):
    builder = InlineKeyboardBuilder()
    
    for channel in config.SPONSOR_CHANNELS:
        channel_name = channel.replace('@', '')
        builder.button(
            text=f"📢 {channel_name}",
            url=f"https://t.me/{channel_name}"
        )
    
    builder.button(
        text=get_user_text(user_id, 'check_membership'),
        callback_data="check_membership"
    )
    builder.adjust(1)
    return builder.as_markup()

def get_main_keyboard(user_id: int):
    builder = ReplyKeyboardBuilder()
    builder.button(text=get_user_text(user_id, 'button_create_pack'))
    builder.button(text=get_user_text(user_id, 'button_my_packs'))
    builder.button(text=get_user_text(user_id, 'button_settings'))
    builder.button(text=get_user_text(user_id, 'button_help'))
    builder.adjust(2, 2)
    return builder.as_markup(resize_keyboard=True)

def get_settings_keyboard(user_id: int):
    builder = ReplyKeyboardBuilder()
    builder.button(text=get_user_text(user_id, 'button_language'))
    builder.button(text=get_user_text(user_id, 'button_back'))
    builder.adjust(1, 1)
    return builder.as_markup(resize_keyboard=True)

def get_language_keyboard(user_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text="🇮🇷 فارسی", callback_data="lang_fa")
    builder.button(text="🇺🇸 English", callback_data="lang_en")
    builder.button(text=get_user_text(user_id, 'back'), callback_data="back_to_settings")
    builder.adjust(2, 1)
    return builder.as_markup()

def get_initial_language_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="🇮🇷 فارسی", callback_data="initial_lang_fa")
    builder.button(text="🇺🇸 English", callback_data="initial_lang_en")
    builder.adjust(2)
    return builder.as_markup()

def get_cancel_keyboard(user_id: int):
    builder = ReplyKeyboardBuilder()
    builder.button(text=get_user_text(user_id, 'cancel'))
    return builder.as_markup(resize_keyboard=True)

@router.message(Command("start"))
async def start_handler(message: Message):
    user_id = message.from_user.id
    
    if not await check_sponsor_membership(message.bot, user_id):
        await message.answer(
            get_user_text(user_id, 'sponsor_check_failed'),
            reply_markup=get_sponsor_keyboard(user_id)
        )
        return
    
    user = db.get_user(user_id)
    if not user:
        await message.answer(
            get_user_text(user_id, 'choose_language'),
            reply_markup=get_initial_language_keyboard()
        )
        return
    
    await message.answer(
        get_user_text(user_id, 'start_message'),
        reply_markup=get_main_keyboard(user_id)
    )

@router.message(F.text.in_(get_button_text(0, 'main_menu') + get_button_text(0, 'back')))
async def main_menu_handler(message: Message):
    user_id = message.from_user.id
    
    if not await check_sponsor_membership(message.bot, user_id):
        await message.answer(
            get_user_text(user_id, 'sponsor_check_failed'),
            reply_markup=get_sponsor_keyboard(user_id)
        )
        return
    
    await message.answer(
        get_user_text(user_id, 'main_menu'),
        reply_markup=get_main_keyboard(user_id)
    )

@router.message(F.text.in_(get_button_text(0, 'settings')))
async def settings_handler(message: Message):
    user_id = message.from_user.id
    
    await message.answer(
        get_user_text(user_id, 'settings_menu'),
        reply_markup=get_settings_keyboard(user_id)
    )

@router.message(F.text.in_(get_button_text(0, 'language')))
async def language_handler(message: Message):
    user_id = message.from_user.id
    
    await message.answer(
        get_user_text(user_id, 'language'),
        reply_markup=get_language_keyboard(user_id)
    )

@router.callback_query(F.data.startswith("initial_lang_"))
async def initial_language_callback_handler(callback: CallbackQuery):
    user_id = callback.from_user.id
    language = callback.data.split("_")[2]
    
    if language in config.LANGUAGES:
        db.create_user(
            user_id=user_id,
            username=callback.from_user.username,
            language=language
        )
        
        await callback.message.edit_text(
            get_user_text(user_id, 'start_message'),
            reply_markup=None
        )
        await callback.message.answer(
            get_user_text(user_id, 'main_menu'),
            reply_markup=get_main_keyboard(user_id)
        )
    
    await callback.answer()

@router.callback_query(F.data.startswith("lang_"))
async def language_callback_handler(callback: CallbackQuery):
    user_id = callback.from_user.id
    language = callback.data.split("_")[1]
    
    if language in config.LANGUAGES:
        db.set_user_language(user_id, language)
        await callback.message.edit_text(
            get_user_text(user_id, 'language_changed'),
            reply_markup=None
        )
        await callback.message.answer(
            get_user_text(user_id, 'main_menu'),
            reply_markup=get_main_keyboard(user_id)
        )
    
    await callback.answer()

@router.callback_query(F.data == "back_to_settings")
async def back_to_settings_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    await callback.message.edit_text(
        get_user_text(user_id, 'settings_menu'),
        reply_markup=None
    )
    await callback.message.answer(
        get_user_text(user_id, 'settings_menu'),
        reply_markup=get_settings_keyboard(user_id)
    )
    await callback.answer()

@router.message(F.text.in_(get_button_text(0, 'help')))
async def help_handler(message: Message):
    user_id = message.from_user.id
    
    await message.answer(
        get_user_text(user_id, 'help_text'),
        reply_markup=get_main_keyboard(user_id)
    )

@router.callback_query(F.data == "check_membership")
async def check_membership_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    checking_msg = await callback.message.edit_text(
        get_user_text(user_id, 'checking_membership')
    )
    
    await asyncio.sleep(1)
    
    if await check_sponsor_membership(callback.message.bot, user_id):
        user = db.get_user(user_id)
        
        await checking_msg.edit_text(
            get_user_text(user_id, 'membership_confirmed')
        )
        
        if not user:
            await callback.message.answer(
                get_user_text(user_id, 'choose_language'),
                reply_markup=get_initial_language_keyboard()
            )
        else:
            await callback.message.answer(
                get_user_text(user_id, 'start_message'),
                reply_markup=get_main_keyboard(user_id)
            )
    else:
        await checking_msg.edit_text(
            get_user_text(user_id, 'membership_failed'),
            reply_markup=get_sponsor_keyboard(user_id)
        )
    
    await callback.answer() 