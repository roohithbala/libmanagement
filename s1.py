from app import db

with db.engine.connect() as connection:
    connection.execute("DROP TABLE IF EXISTS book;")
    connection.commit()

print("Book table dropped successfully!")
