from pymongo import MongoClient
from datetime import datetime
import config

class Database:
    def __init__(self):
        self.client = MongoClient(config.MONGO_URI)
        self.db = self.client[config.DATABASE_NAME]
        self.users = self.db.users
        self.sticker_packs = self.db.sticker_packs
        self.temp_sessions = self.db.temp_sessions
        
    def get_user(self, user_id):
        return self.users.find_one({"user_id": user_id})
    
    def create_user(self, user_id, username=None, language=config.DEFAULT_LANGUAGE):
        user_data = {
            "user_id": user_id,
            "username": username,
            "language": language,
            "is_premium": False,
            "created_at": datetime.now(),
            "packs_created": 0,
            "last_activity": datetime.now()
        }
        return self.users.insert_one(user_data)
    
    def update_user(self, user_id, update_data):
        return self.users.update_one(
            {"user_id": user_id},
            {"$set": update_data}
        )
    
    def set_user_language(self, user_id, language):
        return self.update_user(user_id, {"language": language, "last_activity": datetime.now()})
    
    def get_user_packs(self, user_id):
        return list(self.sticker_packs.find({"creator_id": user_id}))
    
    def create_sticker_pack(self, pack_data):
        pack_data["created_at"] = datetime.now()
        pack_data["updated_at"] = datetime.now()
        return self.sticker_packs.insert_one(pack_data)
    
    def get_sticker_pack(self, pack_id):
        return self.sticker_packs.find_one({"_id": pack_id})
    
    def update_sticker_pack(self, pack_id, update_data):
        update_data["updated_at"] = datetime.now()
        return self.sticker_packs.update_one(
            {"_id": pack_id},
            {"$set": update_data}
        )
    
    def delete_sticker_pack(self, pack_id):
        return self.sticker_packs.delete_one({"_id": pack_id})
    
    def save_temp_session(self, user_id, session_data):
        session_data["user_id"] = user_id
        session_data["created_at"] = datetime.now()
        return self.temp_sessions.replace_one(
            {"user_id": user_id},
            session_data,
            upsert=True
        )
    
    def get_temp_session(self, user_id):
        return self.temp_sessions.find_one({"user_id": user_id})
    
    def delete_temp_session(self, user_id):
        return self.temp_sessions.delete_one({"user_id": user_id})
    
    def increment_user_packs(self, user_id):
        return self.users.update_one(
            {"user_id": user_id},
            {"$inc": {"packs_created": 1}, "$set": {"last_activity": datetime.now()}}
        )

db = Database() 