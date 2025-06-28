from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database import db
from utils.helpers import get_user_text, get_button_text

router = Router()

def get_packs_keyboard(user_id: int, packs: list, page: int = 0, packs_per_page: int = 8):
    builder = InlineKeyboardBuilder()
    
    start = page * packs_per_page
    end = start + packs_per_page
    page_packs = packs[start:end]
    
    for index, pack in enumerate(page_packs, start + 1):
        builder.button(
            text=str(index),
            callback_data=f"manage_pack_{pack['_id']}"
        )
    
    builder.adjust(4)
    
    total_pages = (len(packs) + packs_per_page - 1) // packs_per_page
    
    if total_pages > 1:
        nav_row = []
        if page > 0:
            nav_row.append({"text": "⬅️", "callback_data": f"packs_page_{page - 1}"})
        
        nav_row.append({"text": f"{page + 1}/{total_pages}", "callback_data": "ignore"})
        
        if page < total_pages - 1:
            nav_row.append({"text": "➡️", "callback_data": f"packs_page_{page + 1}"})
        
        for btn_data in nav_row:
            builder.button(text=btn_data["text"], callback_data=btn_data["callback_data"])
        
        builder.adjust(4, len(nav_row))
    
    return builder.as_markup()



def get_pack_management_keyboard(user_id: int, pack_id: str, pack_name: str):
    builder = InlineKeyboardBuilder()
    builder.button(
        text=get_user_text(user_id, 'pack_link'),
        url=f"https://t.me/addstickers/{pack_name}"
    )
    builder.button(
        text=get_user_text(user_id, 'pack_add_sticker'),
        callback_data=f"pack_add_sticker_{pack_id}"
    )
    builder.button(
        text=get_user_text(user_id, 'pack_remove_sticker'),
        callback_data=f"pack_remove_sticker_{pack_id}"
    )
    builder.button(
        text=get_user_text(user_id, 'pack_delete'),
        callback_data=f"pack_delete_{pack_id}"
    )
    builder.button(
        text=get_user_text(user_id, 'back'),
        callback_data="back_to_packs"
    )
    builder.adjust(1)
    return builder.as_markup()

def get_delete_confirm_keyboard(user_id: int, pack_id: str):
    builder = InlineKeyboardBuilder()
    builder.button(
        text=get_user_text(user_id, 'yes'),
        callback_data=f"delete_confirm_{pack_id}"
    )
    builder.button(
        text=get_user_text(user_id, 'no'),
        callback_data=f"manage_pack_{pack_id}"
    )
    builder.adjust(2)
    return builder.as_markup()

@router.message(F.text.in_(get_button_text(0, 'my_packs')))
async def my_packs_handler(message: Message):
    user_id = message.from_user.id
    
    from handlers.main import check_sponsor_membership, get_sponsor_keyboard
    if not await check_sponsor_membership(message.bot, user_id):
        await message.answer(
            get_user_text(user_id, 'sponsor_check_failed'),
            reply_markup=get_sponsor_keyboard(user_id)
        )
        return
    
    packs = db.get_user_packs(user_id)
    
    if not packs:
        await message.answer(get_user_text(user_id, 'my_packs_empty'))
        return
    
    await message.answer(
        get_user_text(user_id, 'my_packs_list'),
        reply_markup=get_packs_keyboard(user_id, packs)
    )

@router.callback_query(F.data.startswith("manage_pack_"))
async def manage_pack_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    pack_id = callback.data.split("_", 2)[2]
    
    try:
        from bson import ObjectId
        pack = db.get_sticker_pack(ObjectId(pack_id))
    except:
        await callback.answer(get_user_text(user_id, 'error_occurred'))
        return
    
    if not pack or pack.get('creator_id') != user_id:
        await callback.answer(get_user_text(user_id, 'error_occurred'))
        return
    
    pack_name = pack.get('pack_name', '')
    pack_title = pack.get('pack_title', get_user_text(user_id, 'default_pack_title'))
    sticker_count = pack.get('sticker_count', 0)
    created_at = pack.get('created_at', '')
    
    if created_at:
        try:
            from datetime import datetime
            if isinstance(created_at, datetime):
                date_str = created_at.strftime('%Y/%m/%d')
            else:
                date_str = str(created_at).split(' ')[0]
        except:
            date_str = get_user_text(user_id, 'unknown_value')
    else:
        date_str = get_user_text(user_id, 'unknown_value')
    
    pack_info = get_user_text(user_id, 'pack_full_info',
        pack_name=pack_name,
        pack_title=pack_title,
        sticker_count=sticker_count,
        created_date=date_str
    )
    
    await callback.message.edit_text(
        pack_info,
        reply_markup=get_pack_management_keyboard(user_id, pack_id, pack_name)
    )
    await callback.answer()



@router.callback_query(F.data.startswith("pack_delete_"))
async def pack_delete_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    pack_id = callback.data.split("_", 2)[2]
    
    try:
        from bson import ObjectId
        pack = db.get_sticker_pack(ObjectId(pack_id))
    except:
        await callback.answer(get_user_text(user_id, 'error_occurred'))
        return
    
    if not pack or pack.get('creator_id') != user_id:
        await callback.answer(get_user_text(user_id, 'error_occurred'))
        return
    
    await callback.message.edit_text(
        get_user_text(user_id, 'pack_delete_confirm'),
        reply_markup=get_delete_confirm_keyboard(user_id, pack_id)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("delete_confirm_"))
async def delete_confirm_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    pack_id = callback.data.split("_", 2)[2]
    
    try:
        from bson import ObjectId
        pack = db.get_sticker_pack(ObjectId(pack_id))
        
        if pack and pack.get('creator_id') == user_id:
            pack_name = pack.get('pack_name')
            
            try:
                deleting_msg = await callback.message.edit_text(
                    get_user_text(user_id, 'deleting_pack')
                )
            except:
                deleting_msg = None
            
            try:
                await callback.message.bot.delete_sticker_set(name=pack_name)
            except Exception as e:
                print(f"Warning: Could not delete sticker set from Telegram: {e}")
            
            db.delete_sticker_pack(ObjectId(pack_id))
            
            if deleting_msg:
                try:
                    await deleting_msg.edit_text(get_user_text(user_id, 'pack_deleted'))
                except:
                    await callback.message.answer(get_user_text(user_id, 'pack_deleted'))
            else:
                await callback.message.answer(get_user_text(user_id, 'pack_deleted'))
        else:
            await callback.message.edit_text(get_user_text(user_id, 'error_occurred'))
    except Exception as e:
        print(f"Error deleting pack: {e}")
        await callback.message.edit_text(get_user_text(user_id, 'error_occurred'))
    
    await callback.answer()

@router.callback_query(F.data == "back_to_packs")
async def back_to_packs_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    packs = db.get_user_packs(user_id)
    
    if not packs:
        await callback.message.edit_text(get_user_text(user_id, 'my_packs_empty'))
        return
    
    await callback.message.edit_text(
        get_user_text(user_id, 'my_packs_list'),
        reply_markup=get_packs_keyboard(user_id, packs, 0)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("packs_page_"))
async def packs_page_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    page = int(callback.data.split("_")[2])
    
    packs = db.get_user_packs(user_id)
    
    if not packs:
        await callback.message.edit_text(get_user_text(user_id, 'my_packs_empty'))
        return
    
    await callback.message.edit_text(
        get_user_text(user_id, 'my_packs_list'),
        reply_markup=get_packs_keyboard(user_id, packs, page)
    )
    await callback.answer()

@router.callback_query(F.data == "ignore")
async def ignore_callback(callback: CallbackQuery):
    await callback.answer()

@router.callback_query(F.data.startswith("back_to_mgmt_"))
async def back_to_mgmt_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    pack_id_suffix = callback.data.split("_")[3]
    
    packs = db.get_user_packs(user_id)
    pack_id = None
    for pack in packs:
        if str(pack['_id'])[-8:] == pack_id_suffix:
            pack_id = str(pack['_id'])
            break
    
    if not pack_id:
        await callback.answer(get_user_text(user_id, 'error_occurred'))
        return
    
    try:
        from bson import ObjectId
        pack = db.get_sticker_pack(ObjectId(pack_id))
        
        if not pack or pack.get('creator_id') != user_id:
            await callback.answer(get_user_text(user_id, 'error_occurred'))
            return
        
        pack_name = pack.get('pack_name', '')
        pack_title = pack.get('pack_title', get_user_text(user_id, 'default_pack_title'))
        sticker_count = pack.get('sticker_count', 0)
        created_at = pack.get('created_at', '')
        
        if created_at:
            try:
                from datetime import datetime
                if isinstance(created_at, datetime):
                    date_str = created_at.strftime('%Y/%m/%d')
                else:
                    date_str = str(created_at).split(' ')[0]
            except:
                date_str = get_user_text(user_id, 'unknown_value')
        else:
            date_str = get_user_text(user_id, 'unknown_value')
        
        pack_info = get_user_text(user_id, 'pack_full_info',
            pack_name=pack_name,
            pack_title=pack_title,
            sticker_count=sticker_count,
            created_date=date_str
        )
        
        try:
            await callback.message.delete()
        except:
            pass
        
        await callback.message.answer(
            pack_info,
            reply_markup=get_pack_management_keyboard(user_id, pack_id, pack_name)
        )
        await callback.answer()
        
    except Exception as e:
        print(f"Error in back to management: {e}")
        await callback.answer(get_user_text(user_id, 'error_occurred'))

@router.callback_query(F.data.startswith("pack_add_sticker_"))
async def pack_add_sticker_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    pack_id = callback.data.split("_", 3)[3]
    
    try:
        from bson import ObjectId
        pack = db.get_sticker_pack(ObjectId(pack_id))
    except:
        await callback.answer(get_user_text(user_id, 'error_occurred'))
        return
    
    if not pack or pack.get('creator_id') != user_id:
        await callback.answer(get_user_text(user_id, 'error_occurred'))
        return
    
    current_count = pack.get('sticker_count', 0)
    from config import STICKERS_PER_PACK_LIMIT
    
    if current_count >= STICKERS_PER_PACK_LIMIT:
        await callback.message.edit_text(
            get_user_text(user_id, 'pack_is_full', max_stickers=STICKERS_PER_PACK_LIMIT),
            reply_markup=InlineKeyboardBuilder().button(
                text=get_user_text(user_id, 'back_to_pack_management'),
                callback_data=f"manage_pack_{pack_id}"
            ).as_markup()
        )
        await callback.answer()
        return
    
    db.save_temp_session(user_id, {
        'action': 'add_sticker_to_pack',
        'pack_id': pack_id,
        'pack_name': pack.get('pack_name'),
        'pack_title': pack.get('pack_title', get_user_text(user_id, 'default_pack_title'))
    })
    
    await callback.message.edit_text(
        get_user_text(user_id, 'add_sticker_instruction'),
        reply_markup=InlineKeyboardBuilder().button(
            text=get_user_text(user_id, 'cancel'),
            callback_data=f"manage_pack_{pack_id}"
        ).as_markup()
    )
    await callback.answer()

@router.callback_query(F.data.startswith("pack_remove_sticker_"))
async def pack_remove_sticker_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    pack_id = callback.data.split("_", 3)[3]
    
    try:
        from bson import ObjectId
        pack = db.get_sticker_pack(ObjectId(pack_id))
    except:
        await callback.answer(get_user_text(user_id, 'error_occurred'))
        return
    
    if not pack or pack.get('creator_id') != user_id:
        await callback.answer(get_user_text(user_id, 'error_occurred'))
        return
    
    current_count = pack.get('sticker_count', 0)
    if current_count == 0:
        await callback.message.edit_text(
            get_user_text(user_id, 'pack_has_no_stickers'),
            reply_markup=InlineKeyboardBuilder().button(
                text=get_user_text(user_id, 'back_to_pack_management'),
                callback_data=f"manage_pack_{pack_id}"
            ).as_markup()
        )
        await callback.answer()
        return
    
    try:
        pack_name = pack.get('pack_name')
        sticker_set = await callback.message.bot.get_sticker_set(pack_name)
        stickers = sticker_set.stickers
        
        if not stickers:
            await callback.message.edit_text(
                get_user_text(user_id, 'pack_has_no_stickers'),
                reply_markup=InlineKeyboardBuilder().button(
                    text=get_user_text(user_id, 'back_to_pack_management'),
                    callback_data=f"manage_pack_{pack_id}"
                ).as_markup()
            )
            await callback.answer()
            return
        
        await show_sticker_for_removal(callback.message, user_id, pack_id, stickers, 0)
        await callback.answer()
        
    except Exception as e:
        print(f"Error getting sticker set: {e}")
        await callback.message.edit_text(
            get_user_text(user_id, 'sticker_management_error'),
            reply_markup=InlineKeyboardBuilder().button(
                text=get_user_text(user_id, 'back_to_pack_management'),
                callback_data=f"manage_pack_{pack_id}"
            ).as_markup()
        )
        await callback.answer()

async def show_sticker_for_removal(message, user_id: int, pack_id: str, stickers: list, page: int = 0):
    if page >= len(stickers):
        page = 0
    
    sticker = stickers[page]
    total_pages = len(stickers)
    
    builder = InlineKeyboardBuilder()
    
    builder.button(
        text=f"🗑️ {get_user_text(user_id, 'delete_this_sticker')}",
        callback_data=f"rm_stk_{pack_id[-8:]}_{page}"
    )
    
    nav_buttons = []
    if total_pages > 1:
        if page > 0:
            nav_buttons.append("⬅️")
            builder.button(
                text="⬅️",
                callback_data=f"stk_pg_{pack_id[-8:]}_{page - 1}"
            )
        
        nav_buttons.append(f"{page + 1}/{total_pages}")
        builder.button(
            text=f"{page + 1}/{total_pages}",
            callback_data="ignore"
        )
        
        if page < total_pages - 1:
            nav_buttons.append("➡️")
            builder.button(
                text="➡️",
                callback_data=f"stk_pg_{pack_id[-8:]}_{page + 1}"
            )
    
    builder.button(
        text=get_user_text(user_id, 'back_to_pack_management'),
        callback_data=f"back_to_mgmt_{pack_id[-8:]}"
    )
    
    if nav_buttons:
        builder.adjust(1, len(nav_buttons), 1)
    else:
        builder.adjust(1, 1)
    
    try:
        await message.delete()
    except:
        pass
    
    await message.answer_sticker(
        sticker=sticker.file_id,
        reply_markup=builder.as_markup()
    )

def get_sticker_removal_keyboard(user_id: int, pack_id: str, stickers: list, page: int = 0):
    builder = InlineKeyboardBuilder()
    
    builder.button(
        text=f"🗑️ {get_user_text(user_id, 'delete_this_sticker')}",
        callback_data=f"rm_stk_{pack_id[-8:]}_{page}"
    )
    
    total_pages = len(stickers)
    nav_buttons = []
    
    if total_pages > 1:
        if page > 0:
            nav_buttons.append("⬅️")
            builder.button(
                text="⬅️",
                callback_data=f"stk_pg_{pack_id[-8:]}_{page - 1}"
            )
        
        nav_buttons.append(f"{page + 1}/{total_pages}")
        builder.button(
            text=f"{page + 1}/{total_pages}",
            callback_data="ignore"
        )
        
        if page < total_pages - 1:
            nav_buttons.append("➡️")
            builder.button(
                text="➡️",
                callback_data=f"stk_pg_{pack_id[-8:]}_{page + 1}"
            )
    
    builder.button(
        text=get_user_text(user_id, 'back_to_pack_management'),
        callback_data=f"back_to_mgmt_{pack_id[-8:]}"
    )
    
    if nav_buttons:
        builder.adjust(1, len(nav_buttons), 1)
    else:
        builder.adjust(1, 1)
    
    return builder.as_markup()

@router.callback_query(F.data.startswith("stk_pg_"))
async def sticker_page_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    parts = callback.data.split("_")
    pack_id_suffix = parts[2]
    page = int(parts[3])
    
    packs = db.get_user_packs(user_id)
    pack_id = None
    for pack in packs:
        if str(pack['_id'])[-8:] == pack_id_suffix:
            pack_id = str(pack['_id'])
            break
    
    if not pack_id:
        await callback.answer(get_user_text(user_id, 'error_occurred'))
        return
    
    try:
        from bson import ObjectId
        pack = db.get_sticker_pack(ObjectId(pack_id))
        
        if not pack or pack.get('creator_id') != user_id:
            await callback.answer(get_user_text(user_id, 'error_occurred'))
            return
        
        pack_name = pack.get('pack_name')
        sticker_set = await callback.message.bot.get_sticker_set(pack_name)
        stickers = sticker_set.stickers
        
        await show_sticker_for_removal(callback.message, user_id, pack_id, stickers, page)
        await callback.answer()
        
    except Exception as e:
        print(f"Error in sticker page: {e}")
        await callback.answer(get_user_text(user_id, 'error_occurred'))

@router.callback_query(F.data.startswith("rm_stk_"))
async def remove_sticker_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    parts = callback.data.split("_", 3)
    pack_id_suffix = parts[2]
    sticker_index = int(parts[3])
    
    packs = db.get_user_packs(user_id)
    pack_id = None
    for pack in packs:
        if str(pack['_id'])[-8:] == pack_id_suffix:
            pack_id = str(pack['_id'])
            break
    
    if not pack_id:
        await callback.answer(get_user_text(user_id, 'error_occurred'))
        return
    
    try:
        from bson import ObjectId
        pack = db.get_sticker_pack(ObjectId(pack_id))
        
        if not pack or pack.get('creator_id') != user_id:
            await callback.answer(get_user_text(user_id, 'error_occurred'))
            return
        
        pack_name = pack.get('pack_name')
        sticker_set = await callback.message.bot.get_sticker_set(pack_name)
        stickers = sticker_set.stickers
        
        if sticker_index >= len(stickers):
            await callback.answer(get_user_text(user_id, 'error_occurred'))
            return
        
        sticker_id = stickers[sticker_index].file_id
        
        builder = InlineKeyboardBuilder()
        builder.button(
            text=get_user_text(user_id, 'yes'),
            callback_data=f"conf_rm_{pack_id[-8:]}_{sticker_index}"
        )
        builder.button(
            text=get_user_text(user_id, 'no'),
            callback_data=f"pack_remove_sticker_{pack_id}"
        )
        builder.adjust(2)
        
        await callback.message.edit_text(
            get_user_text(user_id, 'confirm_remove_sticker'),
            reply_markup=builder.as_markup()
        )
        await callback.answer()
        
    except Exception as e:
        print(f"Error in remove sticker: {e}")
        await callback.answer(get_user_text(user_id, 'error_occurred'))

@router.callback_query(F.data.startswith("conf_rm_"))
async def confirm_remove_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    parts = callback.data.split("_", 3)
    pack_id_suffix = parts[2]
    sticker_index = int(parts[3])
    
    packs = db.get_user_packs(user_id)
    pack_id = None
    for pack in packs:
        if str(pack['_id'])[-8:] == pack_id_suffix:
            pack_id = str(pack['_id'])
            break
    
    if not pack_id:
        await callback.answer(get_user_text(user_id, 'error_occurred'))
        return
    
    try:
        from bson import ObjectId
        pack = db.get_sticker_pack(ObjectId(pack_id))
        
        if not pack or pack.get('creator_id') != user_id:
            await callback.answer(get_user_text(user_id, 'error_occurred'))
            return
        
        pack_name = pack.get('pack_name')
        pack_title = pack.get('pack_title', get_user_text(user_id, 'default_pack_title'))
        current_count = pack.get('sticker_count', 0)
        
        sticker_set = await callback.message.bot.get_sticker_set(pack_name)
        stickers = sticker_set.stickers
        
        if sticker_index >= len(stickers):
            await callback.answer(get_user_text(user_id, 'error_occurred'))
            return
        
        sticker_id = stickers[sticker_index].file_id
        
        processing_msg = await callback.message.edit_text("🔄 در حال حذف استیکر...")
        
        try:
            await callback.message.bot.delete_sticker_from_set(sticker_id)
            
            new_count = current_count - 1
            
            if new_count <= 0:
                try:
                    await callback.message.bot.delete_sticker_set(name=pack_name)
                except:
                    pass
                
                db.delete_sticker_pack(ObjectId(pack_id))
                
                try:
                    await processing_msg.delete()
                except:
                    pass
                
                await callback.message.answer(
                    get_user_text(user_id, 'pack_deleted_no_stickers'),
                    reply_markup=InlineKeyboardBuilder().button(
                        text=get_user_text(user_id, 'back'),
                        callback_data="back_to_packs"
                    ).as_markup()
                )
                return
            
            db.update_sticker_pack(ObjectId(pack_id), {'sticker_count': new_count})
            
            try:
                await processing_msg.delete()
            except:
                pass
            
            await callback.message.answer(
                get_user_text(user_id, 'sticker_removed_from_pack', 
                            current_count=new_count, pack_title=pack_title),
                reply_markup=InlineKeyboardBuilder().button(
                    text=get_user_text(user_id, 'back_to_pack_management'),
                    callback_data=f"back_to_mgmt_{pack_id[-8:]}"
                ).as_markup()
            )
            
        except Exception as e:
            print(f"Error removing sticker from Telegram: {e}")
            try:
                await processing_msg.delete()
            except:
                pass
            
            await callback.message.answer(
                get_user_text(user_id, 'sticker_management_error'),
                reply_markup=InlineKeyboardBuilder().button(
                    text=get_user_text(user_id, 'back_to_pack_management'),
                    callback_data=f"back_to_mgmt_{pack_id[-8:]}"
                ).as_markup()
            )
        
        await callback.answer()
        
    except Exception as e:
        print(f"Error in confirm remove: {e}")
        await callback.answer(get_user_text(user_id, 'error_occurred')) 