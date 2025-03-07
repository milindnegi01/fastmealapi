from fastapi import FastAPI, HTTPException, Depends
import requests
import sqlite3
import os
import pandas as pd
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = FastAPI()

MEALDB_API_URL = "https://www.themealdb.com/api/json/v1/1/search.php?s="
SPOONACULAR_API_URL = "https://api.spoonacular.com/recipes/complexSearch"
SPOONACULAR_API_KEY = os.getenv("SPOONACULAR_API_KEY")  # Fetch from .env

# Database setup
def get_db_connection():
    conn = sqlite3.connect("meals.db")
    conn.row_factory = sqlite3.Row
    return conn

# Create table for extra cuisines and dataset meals
def create_table():
    conn = get_db_connection()
    conn.execute('''CREATE TABLE IF NOT EXISTS extra_meals (
                        id INTEGER PRIMARY KEY,
                        name TEXT UNIQUE,
                        category TEXT DEFAULT 'Unknown',
                        area TEXT DEFAULT 'Unknown',
                        instructions TEXT,
                        ingredients TEXT,
                        image TEXT
                    )''')
    conn.commit()
    conn.close()

create_table()

# Load CSV dataset into SQLite
def load_csv_to_db(csv_file):
    df = pd.read_csv(csv_file)

    # Replace missing category and area values with "Unknown"
    df["category"] = df["category"].fillna("Unknown")
    df["area"] = df["area"].fillna("Unknown")

    conn = get_db_connection()
    for _, row in df.iterrows():
        conn.execute("INSERT OR IGNORE INTO extra_meals (name, category, area, instructions, ingredients, image) VALUES (?, ?, ?, ?, ?, ?)",
                     (row["name"], row["category"], row["area"], row["instructions"], row["ingredients"], ""))  # No image available
    conn.commit()
    conn.close()

# Call this function once to load data (provide your CSV file path)
load_csv_to_db("rr.csv")  # Load CSV data into the database

# Helper function to store meals in the database
def store_meal(name, category, area, instructions, ingredients, image):
    conn = get_db_connection()
    conn.execute("INSERT OR IGNORE INTO extra_meals (name, category, area, instructions, ingredients, image) VALUES (?, ?, ?, ?, ?, ?)",
                 (name, category, area, instructions, ingredients, image))
    conn.commit()
    conn.close()

@app.get("/meals/{meal_name}")
def get_meal(meal_name: str):
    # Step 1: Check in MealDB
    mealdb_response = requests.get(f"{MEALDB_API_URL}{meal_name}")  # No API key needed
    if mealdb_response.status_code == 200:
        mealdb_data = mealdb_response.json()
        if mealdb_data["meals"]:
            return {"source": "MealDB", "data": mealdb_data["meals"]}
    
    # Step 2: Check in Spoonacular API
    params = {"query": meal_name, "apiKey": SPOONACULAR_API_KEY}
    spoonacular_response = requests.get(SPOONACULAR_API_URL, params=params)
    if spoonacular_response.status_code == 200:
        spoonacular_data = spoonacular_response.json()
        if "results" in spoonacular_data and spoonacular_data["results"]:
            # Store in SQLite for future queries
            for meal in spoonacular_data["results"]:
                store_meal(
                    name=meal.get("title", "Unknown"),
                    category="Unknown",
                    area="Unknown",
                    instructions="No instructions available",
                    ingredients="Unknown",
                    image=meal.get("image", "")
                )
            return {"source": "Spoonacular", "data": spoonacular_data["results"]}
    
    # Step 3: Check in Custom Database (Kaggle Dataset)
    conn = get_db_connection()
    meal = conn.execute("SELECT * FROM extra_meals WHERE LOWER(name) LIKE LOWER(?)", (f"%{meal_name}%",)).fetchone()
    conn.close()
    if meal:
        meal_dict = dict(meal)
        formatted_meal = {
            "idMeal": meal_dict["id"],
            "strMeal": meal_dict["name"],
            "strCategory": meal_dict["category"],
            "strArea": meal_dict["area"],
            "strInstructions": meal_dict["instructions"].split("', '"),
            "strMealThumb": meal_dict["image"],
            "strIngredients": meal_dict["ingredients"].strip("[]").replace("'", "").split(", ") if meal_dict["ingredients"] else [],
        }
        return {"source": "Custom DB", "data": formatted_meal}
    
    raise HTTPException(status_code=404, detail="Meal not found in MealDB, Spoonacular, or custom database.")

@app.post("/add_meal/")
def add_meal(name: str, category: str, area: str, instructions: str, ingredients: str, image: str):
    try:
        store_meal(name, category, area, instructions, ingredients, image)
        return {"message": "Meal added successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
