from datetime import datetime, timedelta
import bcrypt
from jose import jwt

# Konfiguracja
SECRET_KEY = "twoj_bardzo_tajny_klucz_zmien_mnie_pozniej"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

def get_password_hash(password: str) -> str:
    """Szyfruje (haszuje) hasło przed zapisaniem do bazy za pomocą bcrypt."""
    # Konwertujemy hasło na bajty, generujemy sól i tworzymy hash
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password=pwd_bytes, salt=salt)
    # Zwracamy jako zwykły tekst, by móc zapisać w bazie
    return hashed_password.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Sprawdza, czy wpisane hasło podczas logowania pasuje do hasha w bazie."""
    password_byte_enc = plain_password.encode('utf-8')
    hashed_password_byte_enc = hashed_password.encode('utf-8')
    return bcrypt.checkpw(password=password_byte_enc, hashed_password=hashed_password_byte_enc)

def create_access_token(data: dict) -> str:
    """Generuje token JWT, który aplikacja wyśle do użytkownika po zalogowaniu."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt