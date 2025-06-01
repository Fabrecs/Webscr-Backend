# Backend

## 🚀 Installation

1. Clone the repo:
   git clone <your-repo-url>
   cd <repo-folder>

2. Set up environment variables:
   Create a `.env` file with the following variables:
   ```
   MONGO_URL=mongodb://your-mongodb-connection-string
   AWS_ACCESS_KEY_ID=your-access-key
   AWS_SECRET_ACCESS_KEY=your-secret-key
   AWS_REGION=your-region
   S3_BUCKET_NAME=your-bucket-name
   ```

3. Commands to start your project:

   python -m pip install -r requirements.txt

   uvicorn main:app --reload

## 📚 Database 
The application uses MongoDB as its database. A global connection is established on server startup via `utils/database.py` and is available throughout the application.
