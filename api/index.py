
import sys
import os

# Add the parent directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import app

# This is required for Vercel
application = app

# For Vercel serverless functions
def handler(request, context):
    return app(request.environ, context)

if __name__ == "__main__":
    app.run()
