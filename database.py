import sqlite3
import os
import sys
import shutil


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


def ensure_db_and_resources():
    exe_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))

    db_path = os.path.join(exe_dir, "recipes.db")
    resources_dir = os.path.join(exe_dir, "resources")

    if not os.path.exists(db_path):
        print(f"[!] recipes.db не найдена в {exe_dir}, копируем из ресурсов...")
        src_db = resource_path("recipes.db")
        if os.path.exists(src_db):
            shutil.copy2(src_db, db_path)
            print(f"[!] recipes.db скопирована в {db_path}")
        else:
            print(f"[!] recipes.db не найдена в ресурсах: {src_db}")

    if not os.path.exists(resources_dir):
        print(f"[!] Папка resources не найдена в {exe_dir}, копируем из ресурсов...")
        src_resources = resource_path("resources")
        if os.path.exists(src_resources):
            shutil.copytree(src_resources, resources_dir)
            print(f"[!] Папка resources скопирована в {resources_dir}")
        else:
            print(f"[!] Папка resources не найдена в ресурсах: {src_resources}")

    update_image_paths_in_db(resources_dir, exe_dir)


def update_image_paths_in_db(resources_dir, exe_dir):
    conn = sqlite3.connect(os.path.join(exe_dir, "recipes.db"))
    cursor = conn.cursor()
    cursor.execute("SELECT id, image_path FROM recipes WHERE image_path IS NOT NULL")
    rows = cursor.fetchall()

    for recipe_id, old_path in rows:
        if old_path.startswith("resources/"):
            new_path = os.path.join(exe_dir, old_path.replace("resources/", "", 1)).replace('\\', '/')
            if os.path.exists(new_path):
                cursor.execute("UPDATE recipes SET image_path = ? WHERE id = ?", (new_path, recipe_id))
                print(f"[!] Обновлён путь для рецепта {recipe_id}: {old_path} -> {new_path}")
            else:
                print(f"[!] Файл изображения не найден по новому пути: {new_path}")
        elif not os.path.isabs(old_path):
            assumed_path = os.path.join(resources_dir, os.path.basename(old_path))
            if os.path.exists(assumed_path):
                cursor.execute("UPDATE recipes SET image_path = ? WHERE id = ?", (assumed_path, recipe_id))
                print(f"[!] Обновлён путь для рецепта {recipe_id}: {old_path} -> {assumed_path}")
    conn.commit()
    conn.close()

DB_PATH = os.path.join(os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__)), "recipes.db")
INGREDIENTS_FILE = os.path.join(os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__)), "resources", "ingredients.txt")
RECIPES_FILE = os.path.join(os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__)), "resources", "prescription.txt")


def load_ingredients_from_file():
    if not os.path.exists(INGREDIENTS_FILE):
        print(f"[!] Файл {INGREDIENTS_FILE} не найден.")
        return []
    with open(INGREDIENTS_FILE, "r", encoding="utf-8") as f:
        ingredients = [line.strip() for line in f if line.strip()]
    return ingredients


def load_recipes_from_file():
    if not os.path.exists(RECIPES_FILE):
        print(f"Файл {RECIPES_FILE} не найден.")
        return []
    with open(RECIPES_FILE, "r", encoding="utf-8") as f:
        content = f.read().strip()
    raw_recipes = [block.strip() for block in content.split('\n\n') if block.strip()]

    recipes = []
    for block in raw_recipes:
        lines = block.split('\n')
        if len(lines) < 4:
            print(f"Некорректный формат рецепта: {block[:50]}...")
            continue
        name = lines[0].strip()
        ingredients_str = lines[1].strip()
        instructions = '\n'.join(lines[2:-1]).strip()
        image_path = lines[-1].strip()
        ingredients_list = [ing.strip() for ing in ingredients_str.split(',')]
        recipes.append({
            'name': name,
            'instructions': instructions,
            'image_path': image_path,
            'ingredients': ingredients_list
        })
    return recipes


def init_db():
    ensure_db_and_resources() 
    
    if os.path.exists(DB_PATH):
        print(f"База данных {DB_PATH} существует")
        return
    print(f"{DB_PATH} создана")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE recipes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        instructions TEXT,
        image_path TEXT
    )
    """)
    cursor.execute("""
    CREATE TABLE ingredients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL
    )
    """)
    cursor.execute("""
    CREATE TABLE recipe_ingredients (
        recipe_id INTEGER,
        ingredient_id INTEGER,
        FOREIGN KEY(recipe_id) REFERENCES recipes(id) ON DELETE CASCADE,
        FOREIGN KEY(ingredient_id) REFERENCES ingredients(id) ON DELETE CASCADE
    )
    """)

    initial_ingredients = load_ingredients_from_file()
    if not initial_ingredients:
        print(f"[!] Не удалось загрузить ингредиенты из {INGREDIENTS_FILE}. База данных не будет заполнена.")
        conn.close()
        return

    cursor.executemany("INSERT OR IGNORE INTO ingredients (name) VALUES (?)", [(name,) for name in initial_ingredients])
    initial_recipes_data = load_recipes_from_file()
    if not initial_recipes_data:
        print(f"[!] Не удалось загрузить рецепты из {RECIPES_FILE}. База данных не будет заполнена.")
        conn.close()
        return
    cursor.execute("SELECT id, name FROM ingredients")
    ing_map = {name: id for id, name in cursor.fetchall()}

    for recipe_data in initial_recipes_data:
        name = recipe_data['name']
        instructions = recipe_data['instructions']
        image_path = recipe_data['image_path']
        if image_path.startswith("resources/"):
            exe_dir = os.path.dirname(DB_PATH)
            image_path = os.path.join(exe_dir, image_path.replace("resources/", "", 1)).replace('\\', '/')
        cursor.execute("INSERT INTO recipes (name, instructions, image_path) VALUES (?, ?, ?)", (name, instructions, image_path))
        recipe_id = cursor.lastrowid
        for ing_name in recipe_data['ingredients']:
            if ing_name in ing_map:
                cursor.execute(
                    "INSERT INTO recipe_ingredients (recipe_id, ingredient_id) VALUES (?, ?)",
                    (recipe_id, ing_map[ing_name])
                )
            else:
                print(f"[!] Ингредиент '{ing_name}' из рецепта '{name}' не найден в списке ингредиентов.")
    conn.commit()
    conn.close()
    print(f"[!] База данных {DB_PATH} создана и заполнена начальными данными из файлов.")


def get_all_ingredients():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM ingredients ORDER BY name")
    rows = cursor.fetchall()
    conn.close()
    return rows


def get_recipes_by_ingredients(ingredient_ids):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    if not ingredient_ids:
        cursor.execute("SELECT id, name, instructions, image_path FROM recipes")
    else:
        placeholders = ','.join('?' * len(ingredient_ids))
        query = f"""
        SELECT r.id, r.name, r.instructions, r.image_path
        FROM recipes r
        JOIN recipe_ingredients ri ON r.id = ri.recipe_id
        WHERE ri.ingredient_id IN ({placeholders})
        GROUP BY r.id
        HAVING COUNT(DISTINCT ri.ingredient_id) = ?
        """
        cursor.execute(query, ingredient_ids + [len(ingredient_ids)])

    rows = cursor.fetchall()
    conn.close()
    return rows


def add_recipe(name, instructions, image_path, ingredient_ids):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO recipes (name, instructions, image_path) VALUES (?, ?, ?)", (name, instructions, image_path))
    recipe_id = cursor.lastrowid
    for ing_id in ingredient_ids:
        cursor.execute("INSERT INTO recipe_ingredients (recipe_id, ingredient_id) VALUES (?, ?)", (recipe_id, ing_id))
    conn.commit()
    conn.close()


def update_recipe(recipe_id, name, instructions, image_path, ingredient_ids):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE recipes SET name = ?, instructions = ?, image_path = ? WHERE id = ?", (name, instructions, image_path, recipe_id))
    cursor.execute("DELETE FROM recipe_ingredients WHERE recipe_id = ?", (recipe_id,))
    for ing_id in ingredient_ids:
        cursor.execute("INSERT INTO recipe_ingredients (recipe_id, ingredient_id) VALUES (?, ?)", (recipe_id, ing_id))

    conn.commit()
    conn.close()


def delete_recipe(recipe_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM recipes WHERE id = ?", (recipe_id,))
    conn.commit()
    conn.close()


def ensure_ingredient_exists(name):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM ingredients WHERE name = ?", (name,))
    row = cursor.fetchone()
    if row:
        conn.close()
        return row[0]
    cursor.execute("INSERT INTO ingredients (name) VALUES (?)", (name,))
    ing_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return ing_id


def get_recipe_by_id(recipe_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, instructions, image_path FROM recipes WHERE id = ?", (recipe_id,))
    row = cursor.fetchone()
    if row:
        cursor.execute("""
            SELECT i.name FROM ingredients i
            JOIN recipe_ingredients ri ON i.id = ri.ingredient_id
            WHERE ri.recipe_id = ?
        """, (recipe_id,))
        ingredients = [row[0] for row in cursor.fetchall()]
        conn.close()
        return {
            'id': row[0],
            'name': row[1],
            'instructions': row[2],
            'image_path': row[3],
            'ingredients': ingredients
        }
    conn.close()
    return None