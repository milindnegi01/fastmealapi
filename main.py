from fastapi import FastAPI, HTTPException
import requests
import os
import psycopg2
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware

# Load environment variables
load_dotenv()

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allow all headers
)

# Supabase Database Credentials
SUPABASE_DB_URL = os.getenv("SUPABASE_DB_URL")
MEALDB_API_KEY = "1"  # Default public API key
MEALDB_API_URL = f"https://www.themealdb.com/api/json/v1/{MEALDB_API_KEY}/search.php?s="

# Function to get a database connection
def get_db_connection():
    try:
        conn = psycopg2.connect(SUPABASE_DB_URL)
        return conn
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database connection error: {str(e)}")

# API Endpoint to fetch meal details
@app.get("/meals/{meal_name}")
async def get_meal(meal_name: str):
    # Step 1: Check in MealDB
    mealdb_response = requests.get(f"{MEALDB_API_URL}{meal_name}")
    if mealdb_response.status_code == 200:
        mealdb_data = mealdb_response.json()
        if mealdb_data["meals"]:
            return {"source": "MealDB", "data": mealdb_data["meals"]}

    # Step 2: Check in Supabase Database
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM extra_meals WHERE LOWER(name) LIKE LOWER(%s)", (f"%{meal_name}%",))
        meal = cur.fetchone()
        conn.close()

        if meal:
            formatted_meal = {
                "idMeal": meal[0],  # Adjust indexes based on your table structure
                "strMeal": meal[1],
                "strCategory": meal[2],
                "strArea": meal[3],
                "strInstructions": meal[4].split("', '"),
                "strIngredients": meal[5], 
            }
            return {"source": "Supabase DB", "data": formatted_meal}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    raise HTTPException(status_code=404, detail="Meal not found in MealDB or Supabase database.")

# API Endpoint to add a meal to the database
@app.post("/add_meal/")
async def add_meal(name: str, category: str, area: str, instructions: str, ingredients: str, image: str):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO extra_meals (name, category, area, instructions, ingredients, image) VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (name) DO NOTHING",
            (name, category, area, instructions, ingredients, image)
        )
        conn.commit()
        conn.close()
        return {"message": "Meal added successfully"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
