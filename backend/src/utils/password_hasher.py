import bcrypt

def hash_password(password: str) -> str:
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password_bytes, salt)

    return hashed_password.hex()

def verify_password(password: str, hashed_password: str) -> bool:
    password_bytes = password.encode('utf-8')
    hashed_password_bytes = bytes.fromhex(hashed_password)

    return bcrypt.checkpw(password_bytes, hashed_password_bytes)