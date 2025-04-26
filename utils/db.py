from pymongo import MongoClient

client = MongoClient("mongo")
db = client["CSE312_TileRun"]
users_collection = db["users"]
