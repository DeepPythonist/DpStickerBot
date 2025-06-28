from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime
import config
from utils.helpers import get_user_text

async def log_new_sticker_pack(bot, pack_data: dict, user_data: dict):
    if not config.LOG_CHANNEL_ID:
        return
    
    try:
        from locales.fa import TEXTS as fa_texts
        from locales.en import TEXTS as en_texts
        
        pack_name = pack_data.get('pack_name', fa_texts['unknown_value'])
        pack_title = pack_data.get('pack_title', fa_texts['no_title'])
        sticker_count = pack_data.get('sticker_count', 0)
        creator_id = pack_data.get('creator_id', fa_texts['unknown_value'])
        
        username = user_data.get('username')
        if username:
            username = f"@{username}"
        else:
            username = fa_texts['no_username']
        
        full_name = user_data.get('first_name', '')
        if user_data.get('last_name'):
            full_name += f" {user_data.get('last_name')}"
        if not full_name:
            full_name = fa_texts['unknown_value']
        
        user_status_fa = fa_texts['premium_user'] if user_data.get('is_premium') else fa_texts['regular_user']
        user_status_en = en_texts['premium_user'] if user_data.get('is_premium') else en_texts['regular_user']
        
        fa_log_text = fa_texts['log_new_pack'].format(
            pack_name=pack_name,
            pack_title=pack_title,
            sticker_count=sticker_count,
            creator_id=creator_id,
            username=username,
            full_name=full_name,
            user_status=user_status_fa,
            date=datetime.now().strftime('%Y/%m/%d'),
            time=datetime.now().strftime('%H:%M')
        )
        
        en_log_text = en_texts['log_new_pack'].format(
            pack_name=pack_name,
            pack_title=pack_title,
            sticker_count=sticker_count,
            creator_id=creator_id,
            username=username,
            full_name=full_name,
            user_status=user_status_en,
            date=datetime.now().strftime('%Y/%m/%d'),
            time=datetime.now().strftime('%H:%M')
        )
        
        log_text = f"{fa_log_text}\n\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n{en_log_text}"
        
        builder = InlineKeyboardBuilder()
        builder.button(
            text=fa_texts['log_view_pack_button'],
            url=f"https://t.me/addstickers/{pack_name}"
        )
        
        await bot.send_message(
            chat_id=config.LOG_CHANNEL_ID,
            text=log_text,
            reply_markup=builder.as_markup()
        )
        
    except Exception as e:
        print(f"Error logging to channel: {e}")

async def log_admin_action(bot, admin_id: int, action: str, details: str = ""):
    if not config.LOG_CHANNEL_ID:
        return
    
    try:
        from locales.fa import TEXTS as fa_texts
        from locales.en import TEXTS as en_texts
        
        fa_log_text = fa_texts['log_admin_action'].format(
            admin_id=admin_id,
            action=action,
            details=details,
            timestamp=datetime.now().strftime('%Y/%m/%d %H:%M')
        )
        
        en_log_text = en_texts['log_admin_action'].format(
            admin_id=admin_id,
            action=action,
            details=details,
            timestamp=datetime.now().strftime('%Y/%m/%d %H:%M')
        )
        
        log_text = f"{fa_log_text}\n\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n{en_log_text}"
        
        await bot.send_message(
            chat_id=config.LOG_CHANNEL_ID,
            text=log_text
        )
        
    except Exception as e:
        print(f"Error logging admin action: {e}") 