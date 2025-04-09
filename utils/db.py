from pymongo import MongoClient

client = MongoClient("mongodb://root:example@localhost:27017/")
db = client["CSE312_Spleef"]
users_collection = db["users"]
