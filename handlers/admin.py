from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import db
from utils.helpers import get_user_text, get_button_text
import config
from datetime import datetime, timedelta
import asyncio

router = Router()

class AdminStates(StatesGroup):
    waiting_user_id_for_premium = State()
    waiting_broadcast_message = State()

def is_admin(user_id: int) -> bool:
    return user_id in config.ADMIN_IDS

def get_admin_keyboard(user_id: int):
    builder = ReplyKeyboardBuilder()
    builder.button(text=get_user_text(user_id, 'admin_bot_stats'))
    builder.button(text=get_user_text(user_id, 'admin_make_premium'))
    builder.button(text=get_user_text(user_id, 'admin_broadcast'))
    builder.button(text=get_user_text(user_id, 'admin_users_list'))
    builder.button(text=get_user_text(user_id, 'admin_latest_packs'))
    builder.button(text=get_user_text(user_id, 'admin_main_menu'))
    builder.adjust(2, 2, 2)
    return builder.as_markup(resize_keyboard=True)

def get_cancel_admin_keyboard(user_id: int):
    builder = ReplyKeyboardBuilder()
    builder.button(text=get_user_text(user_id, 'admin_cancel'))
    return builder.as_markup(resize_keyboard=True)

@router.message(Command("admin"))
async def admin_panel(message: Message):
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        await message.answer(get_user_text(user_id, 'admin_access_denied'))
        return
    
    admin_info = get_user_text(user_id, 'admin_panel_welcome').format(
        admin_name=message.from_user.first_name,
        date=datetime.now().strftime('%Y/%m/%d'),
        time=datetime.now().strftime('%H:%M')
    )
    
    await message.answer(
        admin_info,
        reply_markup=get_admin_keyboard(user_id),
        parse_mode='Markdown'
    )

@router.message(F.text.in_(get_button_text(0, 'admin_stats')))
async def bot_stats(message: Message):
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        return
    
    total_users = db.users.count_documents({})
    premium_users = db.users.count_documents({"is_premium": True})
    total_packs = db.sticker_packs.count_documents({})
    
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    new_users_today = db.users.count_documents({"created_at": {"$gte": today}})
    new_packs_today = db.sticker_packs.count_documents({"created_at": {"$gte": today}})
    
    last_week = datetime.now() - timedelta(days=7)
    active_users_week = db.users.count_documents({"last_activity": {"$gte": last_week}})
    
    stats_text = get_user_text(user_id, 'admin_stats_text').format(
        total_users=total_users,
        premium_users=premium_users,
        new_users_today=new_users_today,
        active_users_week=active_users_week,
        total_packs=total_packs,
        new_packs_today=new_packs_today,
        premium_percentage=(premium_users/total_users*100) if total_users > 0 else 0,
        avg_packs=(total_packs/total_users) if total_users > 0 else 0,
        update_time=datetime.now().strftime('%Y/%m/%d %H:%M')
    )
    
    await message.answer(stats_text, parse_mode='Markdown')

@router.message(F.text.in_(get_button_text(0, 'admin_make_premium')))
async def make_user_premium_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        return
    
    await state.set_state(AdminStates.waiting_user_id_for_premium)
    await message.answer(
        get_user_text(user_id, 'admin_enter_user_id'),
        reply_markup=get_cancel_admin_keyboard(user_id)
    )

@router.message(AdminStates.waiting_user_id_for_premium)
async def make_user_premium_process(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    if message.text in [get_user_text(user_id, 'admin_cancel')] + get_button_text(user_id, 'cancel'):
        await state.clear()
        await message.answer(
            get_user_text(user_id, 'admin_operation_cancelled'),
            reply_markup=get_admin_keyboard(user_id)
        )
        return
    
    try:
        target_user_id = int(message.text.strip())
        
        user = db.get_user(target_user_id)
        if not user:
            await message.answer(get_user_text(user_id, 'admin_user_not_found'))
            return
        
        if user.get('is_premium'):
            await message.answer(get_user_text(user_id, 'admin_user_already_premium'))
            return
        
        db.update_user(target_user_id, {"is_premium": True})
        
        await message.answer(
            get_user_text(user_id, 'admin_user_premium_success').format(user_id=target_user_id),
            parse_mode='Markdown',
            reply_markup=get_admin_keyboard(user_id)
        )
        
        try:
            from utils.log_helper import log_admin_action
            await log_admin_action(
                message.bot, 
                user_id, 
                get_user_text(user_id, 'admin_make_premium'), 
                get_user_text(user_id, 'admin_log_user_premium', user_id=target_user_id)
            )
        except:
            pass
        
        try:
            await message.bot.send_message(
                target_user_id,
                get_user_text(target_user_id, 'admin_premium_notification')
            )
        except:
            pass
        
    except ValueError:
        await message.answer(get_user_text(user_id, 'admin_invalid_user_id'))
    except Exception as e:
        await message.answer(get_user_text(user_id, 'admin_error', error=str(e)))
    
    await state.clear()

@router.message(F.text.in_(get_button_text(0, 'admin_broadcast')))
async def broadcast_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        return
    
    await state.set_state(AdminStates.waiting_broadcast_message)
    await message.answer(
        get_user_text(user_id, 'admin_broadcast_request'),
        reply_markup=get_cancel_admin_keyboard(user_id)
    )

@router.message(AdminStates.waiting_broadcast_message)
async def broadcast_process(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    if message.text in [get_user_text(user_id, 'admin_cancel')] + get_button_text(user_id, 'cancel'):
        await state.clear()
        await message.answer(
            get_user_text(user_id, 'admin_operation_cancelled'),
            reply_markup=get_admin_keyboard(user_id)
        )
        return
    
    all_users = list(db.users.find({}, {"user_id": 1}))
    total_users = len(all_users)
    
    if total_users == 0:
        await message.answer(get_user_text(user_id, 'admin_no_users_found'))
        await state.clear()
        return
    

    
    estimated_total_minutes = int((total_users * config.BROADCAST_DELAY_SECONDS) / 60)
    start_text = get_user_text(user_id, 'admin_broadcast_start').format(total_users=total_users)
    start_text += f"\n{get_user_text(user_id, 'broadcast_estimated_time', minutes=estimated_total_minutes)}"
    start_text += f"\n{get_user_text(user_id, 'broadcast_speed', speed=int(60/config.BROADCAST_DELAY_SECONDS))}"
    
    if total_users > 500:
        start_text += f"\n\n{get_user_text(user_id, 'broadcast_large_users_warning')}"
    
    progress_msg = await message.answer(start_text)
    
    success_count = 0
    failed_count = 0
    last_progress_update = 0
    start_time = datetime.now()
    
    for i, user_doc in enumerate(all_users, 1):
        target_user_id = user_doc['user_id']
        
        try:
            await message.copy_to(target_user_id)
            success_count += 1
            await asyncio.sleep(config.BROADCAST_DELAY_SECONDS)
        except:
            failed_count += 1
            await asyncio.sleep(0.1)
        
        if i % config.BROADCAST_PROGRESS_UPDATE_INTERVAL == 0 or i == total_users or (i - last_progress_update) >= config.BROADCAST_PROGRESS_UPDATE_INTERVAL:
            try:
                elapsed_time = (datetime.now() - start_time).total_seconds()
                remaining_users = total_users - i
                estimated_remaining_time = int((remaining_users * config.BROADCAST_DELAY_SECONDS) / 60) if remaining_users > 0 else 0
                
                progress_text = get_user_text(user_id, 'admin_broadcast_progress').format(
                    success=success_count,
                    failed=failed_count,
                    current=i,
                    total=total_users,
                    percentage=(i/total_users*100)
                )
                
                if estimated_remaining_time > 0:
                    progress_text += f"\n{get_user_text(user_id, 'broadcast_remaining_time', minutes=estimated_remaining_time)}"
                
                await progress_msg.edit_text(progress_text)
                last_progress_update = i
                await asyncio.sleep(0.3)
            except:
                pass
    
    end_time = datetime.now()
    total_duration = int((end_time - start_time).total_seconds() / 60)
    
    final_text = get_user_text(user_id, 'admin_broadcast_finished').format(
        total_users=total_users,
        success_count=success_count,
        failed_count=failed_count,
        success_percentage=(success_count/total_users*100) if total_users > 0 else 0,
        finish_time=end_time.strftime('%H:%M')
    )
    
    final_text += f"\n{get_user_text(user_id, 'broadcast_total_duration', minutes=total_duration)}"
    
    await progress_msg.edit_text(final_text, parse_mode='Markdown')
    
    try:
        from utils.log_helper import log_admin_action
        await log_admin_action(
            message.bot,
            user_id,
            get_user_text(user_id, 'admin_broadcast'),
            get_user_text(user_id, 'admin_log_broadcast', total_users=total_users, success_count=success_count)
        )
    except:
        pass
    
    await state.clear()

@router.message(F.text.in_(get_button_text(0, 'admin_users_list')))
async def users_list(message: Message):
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        return
    
    latest_users = list(db.users.find({}).sort("created_at", -1).limit(20))
    
    if not latest_users:
        await message.answer(get_user_text(user_id, 'admin_no_users_found'))
        return
    
    users_text = get_user_text(user_id, 'admin_users_list_title')
    
    for i, user in enumerate(latest_users, 1):
        user_id_val = user.get('user_id', get_user_text(user_id, 'admin_unknown_value'))
        username = user.get('username', get_user_text(user_id, 'admin_no_username'))
        is_premium = "⭐" if user.get('is_premium') else "👤"
        created_date = user.get('created_at', datetime.now()).strftime('%m/%d')
        
        if username and username != get_user_text(user_id, 'admin_no_username'):
            username_display = f"@{username}"
        else:
            username_display = get_user_text(user_id, 'admin_no_username')
        
        users_text += f"{i}. {is_premium} `{user_id_val}` | {username_display} | {created_date}\n"
    
    await message.answer(users_text, parse_mode='Markdown')

@router.message(F.text.in_(get_button_text(0, 'admin_latest_packs')))
async def latest_packs(message: Message):
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        return
    
    latest_packs = list(db.sticker_packs.find({}).sort("created_at", -1).limit(15))
    
    if not latest_packs:
        await message.answer(get_user_text(user_id, 'admin_no_packs_found'))
        return
    
    packs_text = get_user_text(user_id, 'admin_latest_packs_title')
    
    for i, pack in enumerate(latest_packs, 1):
        pack_name = pack.get('pack_name', get_user_text(user_id, 'admin_unknown_value'))
        pack_title = pack.get('pack_title', get_user_text(user_id, 'no_title'))
        creator_id = pack.get('creator_id', get_user_text(user_id, 'admin_unknown_value'))
        sticker_count = pack.get('sticker_count', 0)
        created_date = pack.get('created_at', datetime.now()).strftime('%m/%d')
        
        escaped_title = pack_title.replace('*', '\\*').replace('_', '\\_').replace('[', '\\[').replace(']', '\\]')
        
        packs_text += f"{i}. **{escaped_title}**\n"
        packs_text += f"   👤 `{creator_id}` | 📊 {sticker_count} | 📅 {created_date}\n"
        packs_text += f"   🔗 https://t.me/addstickers/{pack_name}\n\n"
    
    await message.answer(packs_text, parse_mode='Markdown')

@router.message(F.text.in_(get_button_text(0, 'main_menu')))
async def back_to_main_admin(message: Message):
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        return
    
    from handlers.main import get_main_keyboard
    await message.answer(
        get_user_text(user_id, 'admin_back_to_main'),
        reply_markup=get_main_keyboard(user_id)
    ) 