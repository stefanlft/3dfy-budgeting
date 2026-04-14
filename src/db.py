from supabase import create_client, Client
import config
import pandas as pd
import sqlite3
import hashlib


DEBUG = False

DB_FILE = "biz_vault.db"
if not config.DEBUG_MODE:
    supabase: Client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)

def init_db(deb):
    global DEBUG, supabase
    DEBUG = deb

    if DEBUG:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS ledger
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT, type TEXT, category TEXT, description TEXT, amount REAL)''')
        c.execute('''CREATE TABLE IF NOT EXISTS users
                    (username TEXT PRIMARY KEY, password TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS orders
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product TEXT, customer_name TEXT, contact TEXT, price REAL, deadline TEXT, location TEXT, delivery_method TEXT, status TEXT)''')

        # Default User: uses the hash from your .env file
        c.execute("SELECT * FROM users WHERE username='admin'")
        if not c.fetchone():
            # Fallback to a safe string if environment variable is missing
            stored_hash = config.ADMIN_PASSWORD_HASH if config.ADMIN_PASSWORD_HASH else "fallback_secure_hash"
            c.execute("INSERT INTO users VALUES (?, ?)", ("admin", stored_hash))

        conn.commit()
        conn.close()
    else:
        # 2. Check if admin exists
        response = supabase.table("users").select("username").eq("username", "admin").execute()


        # 3. If no admin found, create one
        if not response.data:
            stored_hash = config.ADMIN_PASSWORD_HASH if config.ADMIN_PASSWORD_HASH else "fallback_secure_hash"
            supabase.table("users").insert({
                "username": "admin",
                "password": stored_hash
            }).execute()

def user_add(username, password):
    hashed_pw = hashlib.sha256(password.encode()).hexdigest()
    if DEBUG:
        conn = sqlite3.connect(DB_FILE)
        try:
            conn.execute("INSERT INTO users VALUES (?, ?)", (username, hashed_pw))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()
    else:
        # Supabase Logic
        response = supabase.table("users").insert({"username": username, "password": hashed_pw}).execute()
        return len(response.data) > 0

def user_delete(username):
    if DEBUG:
        conn = sqlite3.connect(DB_FILE)
        conn.execute("DELETE FROM users WHERE username=?", (username,))
        conn.commit()
        conn.close()
    else:
        supabase.table("users").delete().eq("username", username).execute()

def user_check_login(user, pw):
    hashed_pw = hashlib.sha256(pw.encode()).hexdigest()
    if DEBUG:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username=? AND password=?", (user, hashed_pw))
        result = c.fetchone()
        conn.close()
        return result
    else:
        # Supabase Logic
        response = supabase.table("users").select("*").eq("username", user).eq("password", hashed_pw).execute()
        return response.data[0] if response.data else None

def user_update_password(username, new_password):
    hashed_pw = hashlib.sha256(new_password.encode()).hexdigest()
    if DEBUG:
        conn = sqlite3.connect(DB_FILE)
        conn.execute("UPDATE users SET password=? WHERE username=?", (hashed_pw, username))
        conn.commit()
        conn.close()
    else:
        supabase.table("users").update({"password": hashed_pw}).eq("username", username).execute()

def ledger_get_data():
    """Centralized fetch for all ledger entries."""
    if DEBUG:
        conn = sqlite3.connect(DB_FILE)
        df = pd.read_sql_query("SELECT * FROM ledger", conn)
        conn.close()
    else:
        response = supabase.table("ledger").select("*").execute()
        df = pd.DataFrame(response.data)

    if not df.empty:
        df['date'] = pd.to_datetime(df['date'])
    return df

def ledger_get_summary(df):
    """Calculates high-level metrics for the Overview tab."""
    if df.empty:
        return 0.0, 0.0, 0.0, 0.0

    inbound = df[df['type'] == 'Inbound']['amount'].sum()
    outbound = df[df['type'] == 'Outbound']['amount'].sum()
    net = inbound - outbound
    margin = (net / inbound * 100) if inbound > 0 else 0
    return inbound, outbound, net, margin

def ledger_add_entry(date, t_type, category, description, amount):
    """Inserts a new transaction into the ledger."""
    if DEBUG:
        conn = sqlite3.connect(DB_FILE)
        conn.execute(
            "INSERT INTO ledger (date, type, category, description, amount) VALUES (?,?,?,?,?)",
            (date, t_type, category, description, amount)
        )
        conn.commit()
        conn.close()
    else:
        supabase.table("ledger").insert({
            "date": date,
            "type": t_type,
            "category": category,
            "description": description,
            "amount": amount
        }).execute()

def ledger_delete_entry(entry_id):
    """
    Deletes a transaction from the ledger by its unique ID.
    Supports both Local SQLite (Debug) and Supabase (Production).
    """
    if DEBUG:
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM ledger WHERE id = ?", (entry_id,))
            conn.commit()

            # Check if a row was actually deleted
            if cursor.rowcount == 0:
                st.error(f"Entry ID {entry_id} not found in local database.")
                return False

            conn.close()
            return True
        except Exception as e:
            st.error(f"Local Delete Error: {e}")
            return False
    else:
        # Supabase Logic
        try:
            # eq("id", entry_id) targets the specific row
            response = supabase.table("ledger").delete().eq("id", entry_id).execute()

            # Supabase returns the deleted data in response.data
            if not response.data:
                st.error(f"Entry ID {entry_id} not found in Supabase.")
                return False

            return True
        except Exception as e:
            st.error(f"Production Delete Error: {e}")
            return False

def user_get_list():
    """Fetches all registered usernames for the Directory."""
    if DEBUG:
        conn = sqlite3.connect(DB_FILE)
        df = pd.read_sql_query("SELECT username FROM users", conn)
        conn.close()
    else:
        response = supabase.table("users").select("username").execute()
        df = pd.DataFrame(response.data)
    return df

def orders_get_all():
    """Fetches all orders regardless of status."""
    if DEBUG:
        conn = sqlite3.connect(DB_FILE)
        df = pd.read_sql_query("SELECT * FROM orders", conn)
        conn.close()
    else:
        response = supabase.table("orders").select("*").execute()
        df = pd.DataFrame(response.data)
    return df

def orders_get_active():
    """Fetches all orders that are not marked as Completed."""
    if DEBUG:
        conn = sqlite3.connect(DB_FILE)
        df = pd.read_sql_query("SELECT * FROM orders WHERE status != 'Completed'", conn)
        conn.close()
    else:
        response = supabase.table("orders").select("*").neq("status", "Completed").execute()
        df = pd.DataFrame(response.data)
    return df

def orders_add_entry(product, customer_name, contact, price, deadline, location, delivery_method):
    """Registers a new order in the system."""
    if DEBUG:
        conn = sqlite3.connect(DB_FILE)
        conn.execute(
            "INSERT INTO orders (product, customer_name, contact, price, deadline, location, delivery_method, status) VALUES (?,?,?,?,?,?,?,?)",
            (product, customer_name, contact, price, deadline, location, delivery_method, 'Placed')
        )
        conn.commit()
        conn.close()
    else:
        supabase.table("orders").insert({
            "product": product, "customer_name": customer_name,
            "contact": contact, "price": price,
            "deadline": deadline, "location": location,
            "delivery_method": delivery_method, "status": 'Placed'
        }).execute()

def orders_update_status(order_id, new_status):
    """Updates the status of an existing order."""
    if DEBUG:
        conn = sqlite3.connect(DB_FILE)
        conn.execute("UPDATE orders SET status = ? WHERE id = ?", (new_status, order_id))
        conn.commit()
        conn.close()
    else:
        supabase.table("orders").update({"status": new_status}).eq("id", order_id).execute()

def orders_complete_entry(order_id):
    """Marks an order as completed."""
    if DEBUG:
        conn = sqlite3.connect(DB_FILE)
        conn.execute("UPDATE orders SET status = 'Completed' WHERE id = ?", (order_id,))
        conn.commit()
        conn.close()
    else:
        supabase.table("orders").update({"status": "Completed"}).eq("id", order_id).execute()

def orders_delete_entry(order_id):
    """Permanently deletes an order."""
    if DEBUG:
        conn = sqlite3.connect(DB_FILE)
        conn.execute("DELETE FROM orders WHERE id = ?", (order_id,))
        conn.commit()
        conn.close()
    else:
        supabase.table("orders").delete().eq("id", order_id).execute()
