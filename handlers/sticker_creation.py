from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import os
import asyncio
from database import db
from utils.helpers import (
    get_user_text, generate_unique_name, is_valid_file,
    get_file_size, resize_image, process_video_to_webm,
    clean_temp_files, ensure_user_temp_dir, validate_pack_title, is_valid_emoji,
    check_file_size_limit, get_button_text, get_video_duration
)
import config

router = Router()

class StickerCreationStates(StatesGroup):
    entering_pack_title = State()
    collecting_stickers = State()
    confirming_file = State()
    entering_emoji = State()
    entering_custom_emoji = State()



def get_title_keyboard(user_id: int):
    builder = ReplyKeyboardBuilder()
    builder.button(text=get_user_text(user_id, 'button_skip'))
    builder.button(text=get_user_text(user_id, 'button_cancel'))
    builder.adjust(1, 1)
    return builder.as_markup(resize_keyboard=True)

def get_collection_keyboard(user_id: int):
    builder = ReplyKeyboardBuilder()
    builder.button(text=get_user_text(user_id, 'button_done'))
    builder.button(text=get_user_text(user_id, 'button_cancel'))
    builder.adjust(1, 1)
    return builder.as_markup(resize_keyboard=True)

def get_confirm_keyboard(user_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text=get_user_text(user_id, 'yes'), callback_data="confirm_file_yes")
    builder.button(text=get_user_text(user_id, 'no'), callback_data="confirm_file_no")
    builder.button(text=get_user_text(user_id, 'cancel'), callback_data="confirm_file_cancel")
    builder.adjust(2, 1)
    return builder.as_markup()

def get_emoji_keyboard(user_id: int):
    builder = InlineKeyboardBuilder()
    emojis = ['😊', '😂', '😍', '🥰', '😎', '😭', '😡', '🤔', '😴', '🤤', '🔥', '💯', '👍', '👎', '❤️', '🎉', '⭐', '🌟', '💎', '🚀']
    for emoji in emojis:
        builder.button(text=emoji, callback_data=f"emoji_{emoji}")
    builder.button(text=get_user_text(user_id, 'custom_emoji'), callback_data="emoji_custom")
    builder.button(text=get_user_text(user_id, 'skip'), callback_data="emoji_skip")
    builder.button(text=get_user_text(user_id, 'cancel'), callback_data="emoji_cancel")
    builder.adjust(5, 5, 5, 5, 3)
    return builder.as_markup()

def get_custom_emoji_keyboard(user_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text=get_user_text(user_id, 'back'), callback_data="emoji_back")
    builder.button(text=get_user_text(user_id, 'cancel'), callback_data="emoji_cancel")
    builder.adjust(2)
    return builder.as_markup()

@router.message(F.text.in_(get_button_text(0, 'cancel')))
async def cancel_operation_handler(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    await state.clear()
    clean_temp_files(user_id)
    
    from handlers.main import get_main_keyboard
    await message.answer(
        get_user_text(user_id, 'operation_cancelled'),
        reply_markup=get_main_keyboard(user_id)
    )

@router.message(F.text.in_(get_button_text(0, 'create_pack')))
async def start_pack_creation(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    from handlers.main import check_sponsor_membership, get_sponsor_keyboard
    if not await check_sponsor_membership(message.bot, user_id):
        await message.answer(
            get_user_text(user_id, 'sponsor_check_failed'),
            reply_markup=get_sponsor_keyboard(user_id)
        )
        return
    
    clean_temp_files(user_id)
    ensure_user_temp_dir(user_id)
    

    
    user = db.get_user(user_id)
    if user and user.get('is_premium'):
        await state.set_state(StickerCreationStates.entering_pack_title)
        await message.answer(
            get_user_text(user_id, 'pack_title_request'),
            reply_markup=get_title_keyboard(user_id)
        )
    else:
        await state.update_data(pack_title=None)
        await state.set_state(StickerCreationStates.collecting_stickers)
        await message.answer(
            get_user_text(user_id, 'send_sticker_request'),
            reply_markup=get_collection_keyboard(user_id)
        )



@router.message(StickerCreationStates.entering_pack_title)
async def enter_pack_title(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    if message.text in [get_user_text(user_id, 'skip')] + get_button_text(user_id, 'skip'):
        await state.update_data(pack_title=None)
    else:
        if not validate_pack_title(message.text):
            await message.answer(get_user_text(user_id, 'pack_title_too_long'))
            return
        await state.update_data(pack_title=message.text)
    
    await state.set_state(StickerCreationStates.collecting_stickers)
    await message.answer(
        get_user_text(user_id, 'send_sticker_request'),
        reply_markup=get_collection_keyboard(user_id)
    )

@router.message(StickerCreationStates.collecting_stickers, F.text.in_(get_button_text(0, 'done')))
async def finish_collection(message: Message, state: FSMContext):
    user_id = message.from_user.id
    data = await state.get_data()
    
    if not data.get('sticker_files'):
        await message.answer(get_user_text(user_id, 'need_at_least_one_sticker'))
        return
    
    processing_msg = await message.answer(get_user_text(user_id, 'creating_pack'))
    
    try:
        success = await create_sticker_pack(message.bot, user_id, data)
        
        try:
            await processing_msg.delete()
        except:
            pass
        
        if success:
            pack_name = data.get('pack_name')
            pack_title = data.get('pack_title')
            sticker_count = len(data.get('sticker_files', []))
            
            user = db.get_user(user_id)
            user_lang = user.get('language', config.DEFAULT_LANGUAGE) if user else config.DEFAULT_LANGUAGE
            
            if not pack_title:
                pack_title = config.DEFAULT_PACK_TITLE[user_lang]
            
            success_text = get_user_text(user_id, 'sticker_pack_success').format(
                pack_title=pack_title,
                sticker_count=sticker_count,
                pack_name=pack_name
            )
            
            from aiogram.utils.keyboard import InlineKeyboardBuilder
            builder = InlineKeyboardBuilder()
            builder.button(
                text=get_user_text(user_id, 'view_pack_button'),
                url=f"https://t.me/addstickers/{pack_name}"
            )
            builder.button(
                text=get_user_text(user_id, 'share_pack_button'),
                url=f"https://t.me/share/url?url=https://t.me/addstickers/{pack_name}&text={get_user_text(user_id, 'share_text')}"
            )
            builder.adjust(1)
            
            await message.answer(
                success_text,
                parse_mode='Markdown',
                reply_markup=builder.as_markup()
            )
            
            try:
                from utils.log_helper import log_new_sticker_pack
                pack_data = {
                    'pack_name': pack_name,
                    'pack_title': pack_title,
                    'sticker_count': sticker_count,
                    'creator_id': user_id
                }
                await log_new_sticker_pack(message.bot, pack_data, user)
            except:
                pass
        else:
            await message.answer(get_user_text(user_id, 'pack_creation_error'))
    except Exception:
        try:
            await processing_msg.delete()
        except:
            pass
        await message.answer(get_user_text(user_id, 'pack_creation_error'))
    finally:
        await state.clear()
        clean_temp_files(user_id)
        from handlers.main import get_main_keyboard
        await message.answer(
            get_user_text(user_id, 'main_menu'),
            reply_markup=get_main_keyboard(user_id)
        )



@router.message(StickerCreationStates.collecting_stickers)
async def collect_sticker_file(message: Message, state: FSMContext):
    user_id = message.from_user.id
    data = await state.get_data()
    
    sticker_count = len(data.get('sticker_files', []))
    if sticker_count >= config.STICKERS_PER_PACK_LIMIT:
        await message.answer(get_user_text(user_id, 'pack_limit_reached'))
        return
    
    file_obj = None
    file_name = None
    
    if message.document:
        file_obj = message.document
        mime_type = file_obj.mime_type or ""
        
        if mime_type.startswith('image/gif') or (file_obj.file_name and file_obj.file_name.lower().endswith('.gif')):
            file_name = f"sticker_{sticker_count + 1}.gif"
        elif mime_type.startswith('video/mp4') or (file_obj.file_name and file_obj.file_name.lower().endswith('.mp4')):
            file_name = f"sticker_{sticker_count + 1}.mp4"
        elif mime_type.startswith('video/webm') or (file_obj.file_name and file_obj.file_name.lower().endswith('.webm')):
            file_name = f"sticker_{sticker_count + 1}.webm"
        elif mime_type.startswith('image/') or (file_obj.file_name and any(file_obj.file_name.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.webp'])):
            original_ext = os.path.splitext(file_obj.file_name or "")[1].lower()
            if original_ext in ['.png', '.jpg', '.jpeg', '.webp']:
                file_name = f"sticker_{sticker_count + 1}{original_ext}"
            else:
                file_name = f"sticker_{sticker_count + 1}.png"
        elif file_obj.file_name and file_obj.file_name.lower().endswith('.tgs'):
            file_name = f"sticker_{sticker_count + 1}.tgs"
        else:
            file_name = file_obj.file_name or f"sticker_{sticker_count + 1}"
    elif message.photo:
        file_obj = message.photo[-1]
        file_name = f"sticker_{sticker_count + 1}.jpg"
    elif message.sticker:
        file_obj = message.sticker
        file_name = f"sticker_{sticker_count + 1}"
        if message.sticker.is_animated:
            file_name += ".tgs"
        elif message.sticker.is_video:
            file_name += ".webm"
        else:
            file_name += ".webp"
    elif message.video:
        file_obj = message.video
        file_name = f"sticker_{sticker_count + 1}.mp4"
    elif message.animation:
        file_obj = message.animation
        file_name = f"sticker_{sticker_count + 1}.gif"
    
    if not file_obj:
        await message.answer(get_user_text(user_id, 'invalid_file_type'))
        return
    
    if not is_valid_file(file_name):
        await message.answer(get_user_text(user_id, 'invalid_file_type'))
        return
    
    if file_obj.file_size == 0:
        await message.answer(get_user_text(user_id, 'invalid_file_type'))
        return
    
    if not check_file_size_limit(file_obj.file_size, file_name):
        file_size_mb = file_obj.file_size / (1024 * 1024)
        await message.answer(
            get_user_text(user_id, 'file_too_large_before_processing', file_size_mb=file_size_mb)
        )
        return
    
    if file_name.endswith(('.mp4', '.gif', '.webm')):
        temp_dir = ensure_user_temp_dir(user_id)
        temp_file_path = os.path.join(temp_dir, f"temp_check_{file_name}")
        
        await message.bot.download(file_obj, temp_file_path)
        
        duration = get_video_duration(temp_file_path)
        
        try:
            os.remove(temp_file_path)
        except:
            pass
        
        if duration > config.ANIMATION_DURATION_LIMIT:
            await message.answer(
                get_user_text(user_id, 'video_too_long', 
                            max_duration=config.ANIMATION_DURATION_LIMIT,
                            actual_duration=duration)
            )
            return
    
    await state.update_data(temp_file={'file_obj': file_obj, 'file_name': file_name})
    await state.set_state(StickerCreationStates.confirming_file)
    
    await message.answer(
        get_user_text(user_id, 'file_confirm'),
        reply_markup=get_confirm_keyboard(user_id)
    )

@router.callback_query(F.data == "confirm_file_yes", StickerCreationStates.confirming_file)
async def confirm_file_yes(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    data = await state.get_data()
    temp_file = data.get('temp_file')
    
    if not temp_file:
        await callback.answer()
        return
    
    processing_msg = await callback.message.edit_text(
        get_user_text(user_id, 'processing_file')
    )
    
    try:
        file_path = await download_and_process_file(
            callback.message.bot, 
            temp_file['file_obj'], 
            temp_file['file_name'], 
            user_id, 
            processing_msg
        )
        
        if file_path:
            await state.update_data(current_file_path=file_path)
            try:
                await processing_msg.edit_text(
                    get_user_text(user_id, 'select_emoji'),
                    reply_markup=get_emoji_keyboard(user_id)
                )
            except:
                pass
            await state.set_state(StickerCreationStates.entering_emoji)
        else:
            try:
                await processing_msg.edit_text(get_user_text(user_id, 'processed_file_too_large'))
            except:
                pass
            await asyncio.sleep(3)
            try:
                await processing_msg.edit_text(
                    get_user_text(user_id, 'send_sticker_request'),
                    reply_markup=get_collection_keyboard(user_id)
                )
            except:
                await callback.message.answer(
                    get_user_text(user_id, 'send_sticker_request'),
                    reply_markup=get_collection_keyboard(user_id)
                )
            await state.set_state(StickerCreationStates.collecting_stickers)
    except Exception:
        try:
            await processing_msg.edit_text(get_user_text(user_id, 'file_processing_error'))
        except:
            pass
        await state.set_state(StickerCreationStates.collecting_stickers)
    
    await callback.answer()

@router.callback_query(F.data == "confirm_file_no", StickerCreationStates.confirming_file)
async def confirm_file_no(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    
    await callback.message.edit_text(get_user_text(user_id, 'file_rejected'))
    await callback.message.answer(
        get_user_text(user_id, 'send_sticker_request'),
        reply_markup=get_collection_keyboard(user_id)
    )
    await state.set_state(StickerCreationStates.collecting_stickers)
    await callback.answer()

@router.callback_query(F.data == "confirm_file_cancel", StickerCreationStates.confirming_file)
async def confirm_file_cancel(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    await state.clear()
    clean_temp_files(user_id)
    
    from handlers.main import get_main_keyboard
    await callback.message.edit_text(get_user_text(user_id, 'operation_cancelled'))
    await callback.message.answer(
        get_user_text(user_id, 'main_menu'),
        reply_markup=get_main_keyboard(user_id)
    )
    await callback.answer()

@router.callback_query(F.data == "emoji_cancel", StickerCreationStates.entering_emoji)
async def cancel_emoji_selection(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    data = await state.get_data()
    current_file_path = data.get('current_file_path')
    
    if current_file_path and os.path.exists(current_file_path):
        try:
            os.remove(current_file_path)
        except:
            pass
    
    await state.clear()
    clean_temp_files(user_id)
    
    from handlers.main import get_main_keyboard
    await callback.message.edit_text(get_user_text(user_id, 'operation_cancelled'))
    await callback.message.answer(
        get_user_text(user_id, 'main_menu'),
        reply_markup=get_main_keyboard(user_id)
    )
    await callback.answer()

@router.callback_query(F.data == "emoji_custom", StickerCreationStates.entering_emoji)
async def custom_emoji_callback(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    
    await callback.message.edit_text(
        get_user_text(user_id, 'enter_custom_emoji'),
        reply_markup=get_custom_emoji_keyboard(user_id)
    )
    await state.set_state(StickerCreationStates.entering_custom_emoji)
    await callback.answer()

@router.callback_query(F.data == "emoji_back", StickerCreationStates.entering_custom_emoji)
async def emoji_back_callback(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    
    await callback.message.edit_text(
        get_user_text(user_id, 'select_emoji'),
        reply_markup=get_emoji_keyboard(user_id)
    )
    await state.set_state(StickerCreationStates.entering_emoji)
    await callback.answer()

@router.callback_query(F.data == "emoji_cancel", StickerCreationStates.entering_custom_emoji)
async def cancel_custom_emoji_selection(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    data = await state.get_data()
    current_file_path = data.get('current_file_path')
    
    if current_file_path and os.path.exists(current_file_path):
        try:
            os.remove(current_file_path)
        except:
            pass
    
    await state.clear()
    clean_temp_files(user_id)
    
    from handlers.main import get_main_keyboard
    await callback.message.edit_text(get_user_text(user_id, 'operation_cancelled'))
    await callback.message.answer(
        get_user_text(user_id, 'main_menu'),
        reply_markup=get_main_keyboard(user_id)
    )
    await callback.answer()

@router.message(StickerCreationStates.entering_custom_emoji)
async def process_custom_emoji(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    if not message.text or not message.text.strip():
        await message.answer(get_user_text(user_id, 'invalid_emoji'))
        return
    
    if not is_valid_emoji(message.text):
        await message.answer(get_user_text(user_id, 'invalid_emoji'))
        return
    
    data = await state.get_data()
    current_file_path = data.get('current_file_path')
    
    if not current_file_path:
        await message.answer(get_user_text(user_id, 'error_occurred'))
        return
    
    selected_emoji = message.text.strip()
    
    sticker_files = data.get('sticker_files', [])
    sticker_emojis = data.get('sticker_emojis', [])
    
    sticker_files.append(current_file_path)
    sticker_emojis.append(selected_emoji)
    
    await state.update_data(
        sticker_files=sticker_files,
        sticker_emojis=sticker_emojis,
        current_file_path=None
    )
    
    await message.answer(
        get_user_text(user_id, 'file_added_with_emoji', emoji=selected_emoji)
    )
    await message.answer(
        get_user_text(user_id, 'send_sticker_request'),
        reply_markup=get_collection_keyboard(user_id)
    )
    await state.set_state(StickerCreationStates.collecting_stickers)

@router.callback_query(F.data.startswith("emoji_"), StickerCreationStates.entering_emoji)
async def select_emoji_callback(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    data = await state.get_data()
    current_file_path = data.get('current_file_path')
    
    if not current_file_path:
        await callback.answer()
        return
    
    if callback.data == "emoji_skip":
        selected_emoji = "😊"
    else:
        selected_emoji = callback.data.split("_", 1)[1]
    
    sticker_files = data.get('sticker_files', [])
    sticker_emojis = data.get('sticker_emojis', [])
    
    sticker_files.append(current_file_path)
    sticker_emojis.append(selected_emoji)
    
    await state.update_data(
        sticker_files=sticker_files,
        sticker_emojis=sticker_emojis,
        current_file_path=None
    )
    
    await callback.message.edit_text(
        get_user_text(user_id, 'file_added_with_emoji', emoji=selected_emoji)
    )
    await callback.message.answer(
        get_user_text(user_id, 'send_sticker_request'),
        reply_markup=get_collection_keyboard(user_id)
    )
    await state.set_state(StickerCreationStates.collecting_stickers)
    await callback.answer()

async def download_and_process_file(bot, file_obj, file_name: str, user_id: int, processing_message=None) -> str:
    try:
        temp_dir = ensure_user_temp_dir(user_id)
        file_path = os.path.join(temp_dir, file_name)
        
        await bot.download(file_obj, file_path)
        
        if file_name.endswith(('.jpg', '.jpeg', '.png', '.webp')):
            if processing_message:
                try:
                    await processing_message.edit_text(get_user_text(user_id, 'optimizing_file'))
                except:
                    pass
            
            processed_path = os.path.join(temp_dir, f"processed_{file_name}.png")
            if resize_image(file_path, processed_path):
                os.remove(file_path)
                return processed_path
        
        elif file_name.endswith(('.mp4', '.gif')):
            if processing_message:
                try:
                    await processing_message.edit_text(get_user_text(user_id, 'optimizing_file'))
                except:
                    pass
            
            processed_path = os.path.join(temp_dir, f"processed_{file_name}.webm")
            if process_video_to_webm(file_path, processed_path):
                os.remove(file_path)
                return processed_path
        
        elif file_name.endswith('.tgs'):
            file_size = get_file_size(file_path)
            if file_size <= config.TGS_STICKER_SIZE_LIMIT:
                return file_path
        
        elif file_name.endswith('.webm'):
            file_size = get_file_size(file_path)
            if file_size <= config.VIDEO_STICKER_SIZE_LIMIT:
                return file_path
        
        try:
            os.remove(file_path)
        except:
            pass
        return None
    except Exception:
        return None

async def create_sticker_pack(bot, user_id: int, data: dict) -> bool:
    from aiogram.types import InputFile, BufferedInputFile
    
    try:
        user = db.get_user(user_id)
        bot_info = await bot.get_me()
        bot_username = bot_info.username
        pack_name = f"pack_{generate_unique_name()}_{user_id}_by_{bot_username}"
        
        pack_title = data.get('pack_title')
        if not pack_title:
            user_lang = user.get('language', config.DEFAULT_LANGUAGE) if user else config.DEFAULT_LANGUAGE
            pack_title = config.DEFAULT_PACK_TITLE[user_lang]
        
        sticker_files = data.get('sticker_files', [])
        sticker_emojis = data.get('sticker_emojis', [])
        
        if not sticker_files:
            return False
        
        first_sticker_path = sticker_files[0]
        first_emoji = sticker_emojis[0] if sticker_emojis else '😊'
        
        file_size = get_file_size(first_sticker_path)
        if file_size == 0:
            return False
        
        with open(first_sticker_path, 'rb') as file:
            file_data = file.read()
        
        input_file = BufferedInputFile(file_data, filename=os.path.basename(first_sticker_path))
        
        if first_sticker_path.endswith('.tgs'):
            sticker_format = "animated"
        elif first_sticker_path.endswith('.webm'):
            sticker_format = "video"
        else:
            sticker_format = "static"
        
        await bot.create_new_sticker_set(
            user_id=user_id,
            name=pack_name,
            title=pack_title,
            stickers=[{
                'sticker': input_file,
                'emoji_list': [first_emoji],
                'format': sticker_format
            }]
        )
        
        for i, sticker_path in enumerate(sticker_files[1:], 1):
            try:
                file_size = get_file_size(sticker_path)
                if file_size == 0:
                    continue
                
                with open(sticker_path, 'rb') as file:
                    file_data = file.read()
                
                input_file = BufferedInputFile(file_data, filename=os.path.basename(sticker_path))
                
                if sticker_path.endswith('.tgs'):
                    sticker_format = "animated"
                elif sticker_path.endswith('.webm'):
                    sticker_format = "video"
                else:
                    sticker_format = "static"
                
                emoji = sticker_emojis[i] if i < len(sticker_emojis) else '😊'
                
                await bot.add_sticker_to_set(
                    user_id=user_id,
                    name=pack_name,
                    sticker={
                        'sticker': input_file,
                        'emoji_list': [emoji],
                        'format': sticker_format
                    }
                )
            except Exception:
                continue
        
        pack_data = {
            'creator_id': user_id,
            'pack_name': pack_name,
            'pack_title': pack_title,
            'sticker_count': len(sticker_files),
            'is_active': True
        }
        
        db.create_sticker_pack(pack_data)
        db.increment_user_packs(user_id)
        
        data['pack_name'] = pack_name
        return True
        
    except Exception as e:
        print(f"Error creating sticker pack: {e}")
        return False

@router.message(F.content_type.in_(['document', 'photo', 'sticker', 'video', 'animation']))
async def handle_add_sticker_to_pack(message: Message):
    user_id = message.from_user.id
    
    session = db.get_temp_session(user_id)
    if not session or session.get('action') != 'add_sticker_to_pack':
        return
    
    pack_id = session.get('pack_id')
    pack_name = session.get('pack_name')
    pack_title = session.get('pack_title')
    
    if not pack_id or not pack_name:
        await message.answer(get_user_text(user_id, 'error_occurred'))
        db.delete_temp_session(user_id)
        return
    
    try:
        from bson import ObjectId
        pack = db.get_sticker_pack(ObjectId(pack_id))
        
        if not pack or pack.get('creator_id') != user_id:
            await message.answer(get_user_text(user_id, 'error_occurred'))
            db.delete_temp_session(user_id)
            return
        
        current_count = pack.get('sticker_count', 0)
        if current_count >= config.STICKERS_PER_PACK_LIMIT:
            await message.answer(
                get_user_text(user_id, 'pack_is_full', max_stickers=config.STICKERS_PER_PACK_LIMIT)
            )
            db.delete_temp_session(user_id)
            return
        
        file_obj = None
        file_name = None
        
        if message.document:
            file_obj = message.document
            mime_type = file_obj.mime_type or ""
            
            if mime_type.startswith('image/gif') or (file_obj.file_name and file_obj.file_name.lower().endswith('.gif')):
                file_name = f"new_sticker_{current_count + 1}.gif"
            elif mime_type.startswith('video/mp4') or (file_obj.file_name and file_obj.file_name.lower().endswith('.mp4')):
                file_name = f"new_sticker_{current_count + 1}.mp4"
            elif mime_type.startswith('video/webm') or (file_obj.file_name and file_obj.file_name.lower().endswith('.webm')):
                file_name = f"new_sticker_{current_count + 1}.webm"
            elif mime_type.startswith('image/') or (file_obj.file_name and any(file_obj.file_name.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.webp'])):
                original_ext = os.path.splitext(file_obj.file_name or "")[1].lower()
                if original_ext in ['.png', '.jpg', '.jpeg', '.webp']:
                    file_name = f"new_sticker_{current_count + 1}{original_ext}"
                else:
                    file_name = f"new_sticker_{current_count + 1}.png"
            elif file_obj.file_name and file_obj.file_name.lower().endswith('.tgs'):
                file_name = f"new_sticker_{current_count + 1}.tgs"
            else:
                file_name = file_obj.file_name or f"new_sticker_{current_count + 1}"
        elif message.photo:
            file_obj = message.photo[-1]
            file_name = f"new_sticker_{current_count + 1}.jpg"
        elif message.sticker:
            file_obj = message.sticker
            file_name = f"new_sticker_{current_count + 1}"
            if message.sticker.is_animated:
                file_name += ".tgs"
            elif message.sticker.is_video:
                file_name += ".webm"
            else:
                file_name += ".webp"
        elif message.video:
            file_obj = message.video
            file_name = f"new_sticker_{current_count + 1}.mp4"
        elif message.animation:
            file_obj = message.animation
            file_name = f"new_sticker_{current_count + 1}.gif"
        
        if not file_obj:
            await message.answer(get_user_text(user_id, 'invalid_file_type'))
            return
        
        if not is_valid_file(file_name):
            await message.answer(get_user_text(user_id, 'invalid_file_type'))
            return
        
        if file_obj.file_size == 0:
            await message.answer(get_user_text(user_id, 'invalid_file_type'))
            return
        
        if not check_file_size_limit(file_obj.file_size, file_name):
            file_size_mb = file_obj.file_size / (1024 * 1024)
            await message.answer(
                get_user_text(user_id, 'file_too_large_before_processing', file_size_mb=file_size_mb)
            )
            return
        
        if file_name.endswith(('.mp4', '.gif', '.webm')):
            temp_dir = ensure_user_temp_dir(user_id)
            temp_file_path = os.path.join(temp_dir, f"temp_check_{file_name}")
            
            await message.bot.download(file_obj, temp_file_path)
            
            duration = get_video_duration(temp_file_path)
            
            try:
                os.remove(temp_file_path)
            except:
                pass
            
            if duration > config.ANIMATION_DURATION_LIMIT:
                await message.answer(
                    get_user_text(user_id, 'video_too_long', 
                                max_duration=config.ANIMATION_DURATION_LIMIT,
                                actual_duration=duration)
                )
                db.delete_temp_session(user_id)
                return
        
        processing_msg = await message.answer(get_user_text(user_id, 'processing_file'))
        
        try:
            file_path = await download_and_process_file(
                message.bot, 
                file_obj, 
                file_name, 
                user_id, 
                processing_msg
            )
            
            if not file_path:
                await processing_msg.edit_text(get_user_text(user_id, 'processed_file_too_large'))
                return
            
            from aiogram.types import BufferedInputFile
            
            with open(file_path, 'rb') as file:
                file_data = file.read()
            
            input_file = BufferedInputFile(file_data, filename=os.path.basename(file_path))
            
            if file_path.endswith('.tgs'):
                sticker_format = "animated"
            elif file_path.endswith('.webm'):
                sticker_format = "video"
            else:
                sticker_format = "static"
            
            try:
                await processing_msg.edit_text("🔄 در حال اضافه کردن استیکر...")
                
                await message.bot.add_sticker_to_set(
                    user_id=user_id,
                    name=pack_name,
                    sticker={
                        'sticker': input_file,
                        'emoji_list': ['😊'],
                        'format': sticker_format
                    }
                )
                
                new_count = current_count + 1
                db.update_sticker_pack(ObjectId(pack_id), {'sticker_count': new_count})
                
                await processing_msg.edit_text(
                    get_user_text(user_id, 'sticker_added_to_pack', 
                                current_count=new_count, pack_title=pack_title),
                    reply_markup=InlineKeyboardBuilder().button(
                        text=get_user_text(user_id, 'back_to_pack_management'),
                        callback_data=f"manage_pack_{pack_id}"
                    ).as_markup()
                )
                
                db.delete_temp_session(user_id)
                
            except Exception as e:
                print(f"Error adding sticker to pack: {e}")
                await processing_msg.edit_text(
                    get_user_text(user_id, 'sticker_management_error'),
                    reply_markup=InlineKeyboardBuilder().button(
                        text=get_user_text(user_id, 'back_to_pack_management'),
                        callback_data=f"manage_pack_{pack_id}"
                    ).as_markup()
                )
                db.delete_temp_session(user_id)
            
            try:
                if file_path and os.path.exists(file_path):
                    os.remove(file_path)
            except:
                pass
                
        except Exception as e:
            print(f"Error processing file for pack addition: {e}")
            await processing_msg.edit_text(
                get_user_text(user_id, 'file_processing_error'),
                reply_markup=InlineKeyboardBuilder().button(
                    text=get_user_text(user_id, 'back_to_pack_management'),
                    callback_data=f"manage_pack_{pack_id}"
                ).as_markup()
            )
            db.delete_temp_session(user_id)
        
    except Exception as e:
        print(f"Error in add sticker handler: {e}")
        await message.answer(get_user_text(user_id, 'error_occurred'))
        db.delete_temp_session(user_id)

 