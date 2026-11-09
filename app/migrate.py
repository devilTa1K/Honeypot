from . import db
db.migrate(db.database_url()); print("migrations applied")
