from pymongo import MongoClient

client = MongoClient("mongo")
db = client["CSE312_TileFall"]
users_collection = db["users"]
