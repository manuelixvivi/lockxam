from app.core.database import Base, engine
import app.models  # load all models

def migrate():
    print("Creating all tables in database...")
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully!")

if __name__ == "__main__":
    migrate()
