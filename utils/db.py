from pymongo import MongoClient

client = MongoClient("mongo")
db = client["CSE312_Spleef"]
users_collection = db["users"]
