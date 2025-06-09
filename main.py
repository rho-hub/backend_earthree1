import os
import uuid
from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime
from dotenv import load_dotenv
from fastapi.staticfiles import StaticFiles
import shutil

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MongoDB connection
client = MongoClient(os.getenv("MONGODB_URI"))
db = client["document_management"]

# Configure upload directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Serve static files with directory listings disabled
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

@app.get("/clients")
async def get_clients(search: str = ""):
    query = {
        "$or": [
            {"name": {"$regex": search, "$options": "i"}},
            {"idNumber": {"$regex": search, "$options": "i"}}
        ]
    } if search else {}
    clients = list(db.clients.find(query))
    for c in clients:
        c["_id"] = str(c["_id"])
    return clients

@app.post("/clients")
async def add_client(client: dict):
    client["documents"] = {
        "id": {"uploaded": False},
        "titleDeed": {"uploaded": False},
        "landAgreement": {"uploaded": False},
        "consentForm": {"uploaded": False},
        "annexIII": {"uploaded": False},
        "bonusForm": {"uploaded": False},
    }
    result = db.clients.insert_one(client)
    return {"success": True, "clientId": str(result.inserted_id)}

@app.post("/documents/upload/{client_id}")
async def upload_document(
    client_id: str,
    doc_type: str = Form(...),
    file: UploadFile = File(...)
):
    valid_doc_types = ["id", "titleDeed", "landAgreement", "consentForm", "annexIII", "bonusForm"]
    if doc_type not in valid_doc_types:
        raise HTTPException(status_code=400, detail="Invalid document type")

    try:
        # Create client-specific directory
        client_dir = os.path.join(UPLOAD_DIR, client_id)
        os.makedirs(client_dir, exist_ok=True)

        # Generate unique filename with original extension
        file_ext = os.path.splitext(file.filename)[1]
        filename = f"{uuid.uuid4()}{file_ext}"
        file_path = os.path.join(client_dir, filename)

        # Save the file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Create URL path
        file_url = f"/uploads/{client_id}/{filename}"

        # Update database
        db.clients.update_one(
            {"_id": ObjectId(client_id)},
            {"$set": {
                f"documents.{doc_type}": {
                    "uploaded": True,
                    "url": file_url,
                    "filename": filename,
                    "originalName": file.filename,
                    "uploadedAt": datetime.now(),
                    "filePath": file_path
                }
            }}
        )

        return {"success": True, "url": file_url}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Add this endpoint to verify file serving
@app.get("/verify-file/{client_id}/{filename}")
async def verify_file(client_id: str, filename: str):
    file_path = os.path.join(UPLOAD_DIR, client_id, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return {"exists": True, "path": file_path}

# Add these endpoints to your existing main.py

@app.post("/clients/checkout/{client_id}")
async def checkout_client(
    client_id: str,
    checkout_to: str = Form(...),
    purpose: str = Form(None),
    expected_return: str = Form(None)
):
    try:
        update_data = {
            "status": "checked-out",
            "checkedOutTo": checkout_to,
            "checkedOutDate": datetime.now().isoformat(),
            "checkedOutPurpose": purpose,
        }
        
        if expected_return:
            update_data["expectedReturn"] = expected_return

        result = db.clients.update_one(
            {"_id": ObjectId(client_id)},
            {"$set": update_data}
        )
        
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Client not found")
            
        return {"success": True}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/clients/checkin/{client_id}")
async def checkin_client(client_id: str):
    try:
        result = db.clients.update_one(
            {"_id": ObjectId(client_id)},
            {"$set": {
                "status": "available",
                "checkedOutTo": None,
                "checkedOutDate": None,
                "checkedOutPurpose": None,
                "expectedReturn": None
            }}
        )
        
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Client not found")
            
        return {"success": True}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))