import os
from dotenv import load_dotenv
from pymongo import MongoClient
import certifi

load_dotenv()
uri = os.getenv("MONGODB_URI")
print("URI:", uri)
try:
    client = MongoClient(uri, tlsCAFile=certifi.where())
    print(client.list_database_names())
except Exception as e:
    print("Error connecting to MongoDB:", e)