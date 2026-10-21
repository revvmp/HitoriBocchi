from database import schema
from database.connection import connect
from utils.password_hasher import hash_password


DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_EMAIL = "admin"
DEFAULT_ADMIN_PASSWORD = "admin"


def init_db():
    """
    Creates or migrates the database and seeds a default admin account when none exists.
    Change the default admin password after the first sign-in.
    """
    print("Initializing database...")
    schema.migrate()
    conn = connect()

    try:
        admin_exists = conn.execute("SELECT id FROM users WHERE is_admin = 1").fetchone()

        if admin_exists:
            print("Admin account already exists.")
        else:
            conn.execute("INSERT INTO users (username, email, password, is_admin) VALUES (?, ?, ?, ?)", (DEFAULT_ADMIN_USERNAME, DEFAULT_ADMIN_EMAIL, hash_password(DEFAULT_ADMIN_PASSWORD), 1))
            conn.commit()
            print("Created admin account!")
    finally:
        conn.close()

    print("Database initialization complete.")


if __name__ == "__main__":
    init_db()
