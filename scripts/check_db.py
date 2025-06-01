from utils.database import check_connection

if __name__ == "__main__":
    if check_connection():
        print("✅ Successfully connected to MongoDB")
    else:
        print("❌ Failed to connect to MongoDB") 