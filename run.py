from app import create_app
from app.extensions import db

app = create_app()

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    # use_reloader=False: prevents the watchdog from killing background ingestion
    # threads when torch/sentence-transformers load their model files.
    # Debug error pages are still active (debug=True).
    app.run(debug=True, use_reloader=False)