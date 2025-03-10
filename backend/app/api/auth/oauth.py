"""
OAuth utilities
"""

from authlib.integrations.starlette_client import OAuth
from starlette.config import Config

from app.postgres.models import User
from app.api.deps import DBSessionDep

# Configuration
# TODO: use settings.py, fix this path.
config = Config(".env")
oauth = OAuth(config)

# Register Google OAuth
oauth.register(
    name="google",
    client_id=config("GOOGLE_CLIENT_ID"),
    client_secret=config("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)


async def get_or_create_user(user_info: dict, db: DBSessionDep) -> User:
    """Get existing user or create a new one from OAuth user info"""
    email = user_info.get("email")

    # Check if user already exists
    user = db.query(User).filter(User.email == email).first()

    if not user:
        # Create new user
        user = User(
            email=email,
            oauth_provider="google",
            oauth_id=user_info.get("sub"),
            is_active=True,
            is_superuser=False,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    return user
