#!/usr/bin/env python3
import argparse
import os
import sys

# Add project root to sys.path so we can import app modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.init_db import initialize_database
from app.db.session import SessionLocal
from app.models.user import User
from app.core.auth import hash_password


def main():
    parser = argparse.ArgumentParser(description="Create a new Admin user for SentinelVision.")
    parser.add_argument("--username", type=str, help="Username for the admin user.")
    parser.add_argument("--password", type=str, help="Password for the admin user.")
    args = parser.parse_args()

    # Initialize the database to ensure the users table exists
    print("Ensuring database tables are initialized...")
    initialize_database()

    username = args.username
    password = args.password

    # Prompt if not provided via arguments
    if not username:
        username = input("Enter admin username: ").strip()
    if not password:
        import getpass
        password = getpass.getpass("Enter admin password: ").strip()

    if not username or not password:
        print("Error: Username and password cannot be empty.")
        sys.exit(1)

    db = SessionLocal()
    try:
        # Check if the username already exists
        existing_user = db.query(User).filter(User.username == username).first()
        if existing_user:
            print(f"Error: User with username '{username}' already exists.")
            sys.exit(1)

        # Hash password and create user
        hashed = hash_password(password)
        new_admin = User(username=username, hashed_password=hashed, role="admin")
        db.add(new_admin)
        db.commit()
        print(f"Success: Admin user '{username}' created successfully!")
    except Exception as e:
        db.rollback()
        print(f"Error: Failed to create admin user: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
