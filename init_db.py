from dotenv import load_dotenv
load_dotenv()

from question_banks.v2.repository import Base, QbankV2Repository

def init_db():
    repo = QbankV2Repository()
    repo._ensure_engine()
    print(f"Creating tables in {repo._database_url}...")
    Base.metadata.create_all(repo._engine)
    print("Tables created successfully.")

if __name__ == "__main__":
    init_db()
