from datetime import datetime, timedelta, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import DESCENDING

from database.models import Session


class SessionManager:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db["sessions"]

    async def start_session(
        self,
        created_by: str,
        channel_name: str,
        channel_id: int,
        creator_metadata: dict | None = None,
    ) -> Session:
        session = Session(
            created_by=created_by,
            channel_name=channel_name,
            channel_id=channel_id,
            creator_metadata=creator_metadata or {},
        )

        await self.collection.insert_one(session.model_dump(by_alias=True))
        return session

    async def update_session(self, channel_id: int) -> bool:
        result = await self.collection.update_one(
            {"channel_id": channel_id, "is_ended": False},
            {"$set": {"updated_at": datetime.now(timezone.utc)}},
        )
        return result.modified_count > 0

    async def update_and_end_session(self, channel_id: int) -> bool:
        now = datetime.now(timezone.utc)
        session_data = await self.collection.find_one({"channel_id": channel_id, "is_ended": False})
        if not session_data:
            return False

        created_at = session_data["created_at"]
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)

        duration = int((now - created_at).total_seconds())

        result = await self.collection.update_one(
            {"channel_id": channel_id, "is_ended": False},
            {"$set": {"is_ended": True, "updated_at": now, "duration": duration}},
        )
        return result.modified_count > 0
        
    async def get_active_sessions(self) -> list[dict]:
        cursor = self.collection.find({"is_ended": False})
        return [
            {"session": Session(**s), "created_by": s.get("created_by", "")}
            async for s in cursor
        ]

    async def delete_session(self, channel_id: int) -> bool:
        result = await self.collection.delete_one({"channel_id": channel_id, "is_ended": False})
        return result.deleted_count > 0

    async def update_channel_name(self, channel_id: int, new_name: str) -> bool:
        result = await self.collection.update_one(
            {"channel_id": channel_id, "is_ended": False},
            {
                "$set": {
                    "channel_name": new_name,
                    "updated_at": datetime.now(timezone.utc)
                }
            },
        )
        return result.modified_count > 0

    async def longest_sessions_all_time(self, limit: int = 10) -> list[Session]:
        cursor = self.collection.find({"duration": {"$ne": None}}).sort("duration", DESCENDING).limit(limit)
        return [Session(**s) async for s in cursor]

    async def longest_sessions_this_week(self, limit: int = 10) -> list[Session]:
        week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        cursor = self.collection.find({
            "duration": {"$exists": True},
            "created_at": {"$gte": week_ago}
        }).sort("duration", -1).limit(limit)
        return [Session(**s) async for s in cursor]

    async def clean_up_short_sessions(self, treshhold: int = 600) -> int:
        query_filter = {"duration": {"$lte": treshhold}}
        result = await self.collection.delete_many(query_filter, comment=f"Cleaning up all sessions shorter than {treshhold}seconds")
        return result.deleted_count
