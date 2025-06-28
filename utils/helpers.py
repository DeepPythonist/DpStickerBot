import os
import string
import random
from PIL import Image
import imageio
from typing import Optional
import config
from database import db

def get_user_text(user_id: int, key: str, **kwargs) -> str:
    user = db.get_user(user_id)
    if not user:
        language = config.DEFAULT_LANGUAGE
    else:
        language = user.get('language', config.DEFAULT_LANGUAGE)
    
    if language == 'fa':
        from locales.fa import TEXTS
    else:
        from locales.en import TEXTS
    
    text = TEXTS.get(key, key)
    if kwargs:
        return text.format(**kwargs)
    return text

def get_button_text(user_id: int, button_key: str) -> list:
    from locales.fa import TEXTS as FA_TEXTS
    from locales.en import TEXTS as EN_TEXTS
    
    fa_text = FA_TEXTS.get(f'button_{button_key}', '')
    en_text = EN_TEXTS.get(f'button_{button_key}', '')
    
    texts = []
    if fa_text:
        texts.append(fa_text)
    if en_text and en_text != fa_text:
        texts.append(en_text)
    
    return texts if texts else [fa_text]

def generate_unique_name(length: int = config.UNIQUE_NAME_LENGTH) -> str:
    characters = string.ascii_lowercase + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

def get_file_extension(filename: str) -> str:
    return os.path.splitext(filename.lower())[1]

def is_supported_image(filename: str) -> bool:
    ext = get_file_extension(filename)
    return ext in config.SUPPORTED_IMAGE_FORMATS

def is_supported_video(filename: str) -> bool:
    ext = get_file_extension(filename)
    return ext in config.SUPPORTED_VIDEO_FORMATS

def is_supported_animation(filename: str) -> bool:
    ext = get_file_extension(filename)
    return ext in config.SUPPORTED_ANIMATION_FORMATS

def is_valid_file(filename: str) -> bool:
    return (is_supported_image(filename) or 
            is_supported_video(filename) or 
            is_supported_animation(filename))

def check_file_size_limit(file_size: int, filename: str = None) -> bool:
    if filename and filename.endswith('.tgs'):
        return file_size <= config.TGS_STICKER_SIZE_LIMIT
    elif filename and filename.endswith(('.webm', '.mp4', '.gif')):
        return file_size <= config.VIDEO_STICKER_SIZE_LIMIT
    else:
        return file_size <= config.STATIC_STICKER_SIZE_LIMIT





def resize_image(input_path: str, output_path: str, size: tuple = (512, 512)) -> bool:
    try:
        with Image.open(input_path) as img:
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            img.thumbnail(size, Image.Resampling.LANCZOS)
            
            new_img = Image.new('RGBA', size, (0, 0, 0, 0))
            x = (size[0] - img.width) // 2
            y = (size[1] - img.height) // 2
            new_img.paste(img, (x, y), img)
            
            quality_levels = [
                {'optimize': True, 'compress_level': 9},
                {'optimize': True, 'compress_level': 6},
                {'optimize': True, 'compress_level': 3}
            ]
            
            for quality in quality_levels:
                try:
                    new_img.save(output_path, 'PNG', **quality)
                    if get_file_size(output_path) <= config.STATIC_STICKER_SIZE_LIMIT:
                        return True
                except:
                    continue
            
            try:
                smaller_img = new_img.resize((480, 480), Image.Resampling.LANCZOS)
                smaller_img.save(output_path, 'PNG', optimize=True, compress_level=9)
                if get_file_size(output_path) <= config.STATIC_STICKER_SIZE_LIMIT:
                    return True
            except:
                pass
            
            try:
                new_img.save(output_path, 'PNG', optimize=True)
                return True
            except:
                return False
            
    except Exception:
        return False

def process_video_to_webm(input_path: str, output_path: str, duration_limit: int = config.ANIMATION_DURATION_LIMIT) -> bool:
    try:
        import subprocess
        
        quality_configs = [
            {
                'crf': '10',
                'b:v': '1M'
            },
            {
                'crf': '20', 
                'b:v': '800k'
            },
            {
                'crf': '30',
                'b:v': '600k'
            },
            {
                'crf': '40',
                'b:v': '400k'
            },
            {
                'crf': '50',
                'b:v': '200k'
            }
        ]
        
        for i, quality in enumerate(quality_configs):
            temp_output = f"{output_path}_temp_{i}.webm"
            
            cmd = [
                'ffmpeg', '-y', 
                '-i', input_path,
                '-t', str(duration_limit),
                '-vf', 'scale=512:512:force_original_aspect_ratio=decrease,pad=512:512:(ow-iw)/2:(oh-ih)/2:color=black@0',
                '-c:v', 'libvpx-vp9',
                '-pix_fmt', 'yuva420p',
                '-crf', quality['crf'],
                '-b:v', quality['b:v'],
                '-an',
                temp_output
            ]
            
            try:
                result = subprocess.run(cmd, 
                                      capture_output=True, 
                                      text=True, 
                                      timeout=30)
                
                if result.returncode == 0 and os.path.exists(temp_output):
                    if get_file_size(temp_output) <= config.VIDEO_STICKER_SIZE_LIMIT:
                        os.rename(temp_output, output_path)
                        return True
                    else:
                        try:
                            os.remove(temp_output)
                        except:
                            pass
            except:
                try:
                    if os.path.exists(temp_output):
                        os.remove(temp_output)
                except:
                    pass
        
        return False
        
    except Exception:
        return False

def get_file_size(file_path: str) -> int:
    try:
        return os.path.getsize(file_path)
    except OSError:
        return 0

def get_video_duration(file_path: str) -> float:
    try:
        import subprocess
        import json
        
        cmd = [
            'ffprobe', '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            file_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            data = json.loads(result.stdout)
            duration = float(data['format']['duration'])
            return duration
        else:
            return 0.0
    except Exception:
        return 0.0

def check_video_duration_limit(file_path: str) -> bool:
    duration = get_video_duration(file_path)
    if duration == 0.0:
        return True
    return duration <= config.ANIMATION_DURATION_LIMIT

def clean_temp_files(user_id: int):
    temp_dir = os.path.join(config.TEMP_DOWNLOAD_PATH, str(user_id))
    if os.path.exists(temp_dir):
        for filename in os.listdir(temp_dir):
            file_path = os.path.join(temp_dir, filename)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)
            except Exception:
                pass
        try:
            os.rmdir(temp_dir)
        except Exception:
            pass

def ensure_user_temp_dir(user_id: int) -> str:
    temp_dir = os.path.join(config.TEMP_DOWNLOAD_PATH, str(user_id))
    os.makedirs(temp_dir, exist_ok=True)
    return temp_dir

def validate_pack_title(title: str) -> bool:
    if not title or len(title) > config.MAX_PACK_TITLE_LENGTH:
        return False
    return True

def is_valid_emoji(text: str) -> bool:
    import re
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  
        "\U0001F300-\U0001F5FF"  
        "\U0001F680-\U0001F6FF"  
        "\U0001F1E0-\U0001F1FF"  
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "\U0001F900-\U0001F9FF"  
        "\U0001FA70-\U0001FAFF"  
        "]+", re.UNICODE
    )
    
    if not text.strip():
        return False
    
    clean_text = text.strip()
    if len(clean_text) > 10:
        return False
    
    return bool(emoji_pattern.match(clean_text)) 