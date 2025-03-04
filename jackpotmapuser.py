import os
import json
import hashlib
import secrets
import argparse

def generate_salt():
    """Generate a random salt for password hashing"""
    return secrets.token_hex(16)

def hash_password(password, salt):
    """Hash a password with a salt using PBKDF2"""
    return hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100000  # 100,000 iterations
    ).hex()

def load_credentials():
    """Load user credentials from a JSON file."""
    try:
        with open("credentials.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        # Create a default admin user if file doesn't exist
        default_salt = generate_salt()
        default_credentials = {
            "admin": {
                "password": hash_password("admin", default_salt),
                "salt": default_salt,
                "role": "admin"
            }
        }
        with open("credentials.json", "w") as f:
            json.dump(default_credentials, f, indent=4)
        print("Created credentials.json with default admin user (username: admin, password: admin)")
        return default_credentials

def save_credentials(credentials):
    """Save user credentials to a JSON file."""
    with open("credentials.json", "w") as f:
        json.dump(credentials, f, indent=4)
    print("Credentials saved successfully.")

def add_user(username, password, role):
    """Add a new user to the credentials file."""
    credentials = load_credentials()

    if username in credentials:
        print(f"Error: User '{username}' already exists.")
        return False

    salt = generate_salt()
    hashed_password = hash_password(password, salt)

    credentials[username] = {
        "password": hashed_password,
        "salt": salt,
        "role": role
    }

    save_credentials(credentials)
    print(f"User '{username}' added successfully with role '{role}'.")
    return True

def remove_user(username):
    """Remove a user from the credentials file."""
    credentials = load_credentials()

    if username not in credentials:
        print(f"Error: User '{username}' not found.")
        return False

    if username == "admin" and len(credentials) == 1:
        print("Error: Cannot remove the last admin user.")
        return False

    del credentials[username]
    save_credentials(credentials)
    print(f"User '{username}' removed successfully.")
    return True

def change_password(username, new_password):
    """Change a user's password."""
    credentials = load_credentials()

    if username not in credentials:
        print(f"Error: User '{username}' not found.")
        return False

    salt = generate_salt()
    hashed_password = hash_password(new_password, salt)

    credentials[username]["password"] = hashed_password
    credentials[username]["salt"] = salt

    save_credentials(credentials)
    print(f"Password for user '{username}' changed successfully.")
    return True

def change_role(username, new_role):
    """Change a user's role."""
    credentials = load_credentials()

    if username not in credentials:
        print(f"Error: User '{username}' not found.")
        return False

    credentials[username]["role"] = new_role
    save_credentials(credentials)
    print(f"Role for user '{username}' changed to '{new_role}' successfully.")
    return True

def list_users():
    """List all users and their roles."""
    credentials = load_credentials()

    print("\nUser List:")
    print("-" * 40)
    print(f"{'Username':<20} {'Role':<10}")
    print("-" * 40)

    for username, data in credentials.items():
        print(f"{username:<20} {data['role']:<10}")

    print("-" * 40)
    print(f"Total users: {len(credentials)}")

def main():
    parser = argparse.ArgumentParser(description="User Management Utility")
    subparsers = parser.add_subparsers(dest="command", help="Command")

    # Add user
    add_parser = subparsers.add_parser("add", help="Add a new user")
    add_parser.add_argument("username", help="Username")
    add_parser.add_argument("password", help="Password")
    add_parser.add_argument("role", choices=["admin", "analyst", "viewer"], help="User role")

    # Remove user
    remove_parser = subparsers.add_parser("remove", help="Remove a user")
    remove_parser.add_argument("username", help="Username")

    # Change password
    password_parser = subparsers.add_parser("password", help="Change a user's password")
    password_parser.add_argument("username", help="Username")
    password_parser.add_argument("new_password", help="New password")

    # Change role
    role_parser = subparsers.add_parser("role", help="Change a user's role")
    role_parser.add_argument("username", help="Username")
    role_parser.add_argument("new_role", choices=["admin", "analyst", "viewer"], help="New role")

    # List users
    subparsers.add_parser("list", help="List all users")

    # Init
    subparsers.add_parser("init", help="Initialize credentials file")

    args = parser.parse_args()

    if args.command == "add":
        add_user(args.username, args.password, args.role)
    elif args.command == "remove":
        remove_user(args.username)
    elif args.command == "password":
        change_password(args.username, args.new_password)
    elif args.command == "role":
        change_role(args.username, args.new_role)
    elif args.command == "list":
        list_users()
    elif args.command == "init":
        load_credentials()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
