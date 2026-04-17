# Repro & Reservation Orchestrator (RRO)

A centralized platform for managing reproduction workgroups, engineering assignments, and release coordination.

## 📋 Prerequisites

- **Python 3.8** or higher
- **MySQL Server** 5.7+ or **MariaDB**
- **pip** (Python package manager)

## 🛠️ Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd Repro_and_Reservation_Orchestrator
```

### 2. Create Virtual Environment (Recommended)

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

**macOS/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Database Setup

Create a MySQL database:

```sql
CREATE DATABASE rro_database CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

Update the database configuration in `.env` file (see next section).

### 5. Environment Configuration

Create a `.env` file in the root directory with the following variables:

```env
# Flask Configuration
SECRET_KEY=your-secret-key-here
FLASK_ENV=development
DEBUG=True

# Database Configuration
DATABASE_HOST=localhost
DATABASE_PORT=3306
DATABASE_NAME=rro_database
DATABASE_USER=your_mysql_username
DATABASE_PASSWORD=your_mysql_password

# Email Configuration (for password reset)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-email-password
MAIL_DEFAULT_SENDER=your-email@gmail.com

# Bugzilla Integration (required for live bug ingestion)
# Contact your team lead for the service account credentials.
BUGZ_USER=service-account@hpe.com
BUGZ_PASSWORD=your-bugzilla-password

# ChatHPE Integration (required for AI analysis)
# Obtain these from https://api.chathpe.it.hpe.com — do NOT share or commit.
CHATHPE_CLIENT_ID=your-client-id-uuid
CHATHPE_JWT_TOKEN=Bearer eyJ0eXAiOiJKV1Q...
CHATHPE_USER_ID=your-user-id-uuid
CHATHPE_USERNAME=YourDisplayName
```

> **⚠️ Security — Read This First:**
> - **Never commit `.env` to git.** It is gitignored.
> - **Never commit `chathpe_creds.json`.** It is gitignored.
> - The Bugzilla and ChatHPE credentials are company-internal data. They must not be stored in any file that could be pushed to a public or shared repository.
> - All credentials are loaded exclusively from environment variables at runtime and held only in process memory.

**Ingestion behaviour:**
When a manager creates a workgroup or changes a workgroup's build version / engineer list, the app automatically fetches the real bugs for that build version from Bugzilla in a background thread and stores them in the local database. ChatHPE analysis is then generated for any new bugs. Poll `GET /api/workgroups/<id>/ingest_status` to check progress.

**For local development without real credentials**, the mock scripts are still available:
```bash
# Start mock API (Bugzilla + ChatHPE simulators)
python mock_api_server.py --port 5001

# Ingest mock bug data
python ingest_mock_bugs.py
```

### 6. Initialize Database

Run the Flask migrations:

```bash
flask db upgrade
```

Or use the initialization script:

```bash
python init_db.py
```

This will create all tables with proper schema, foreign keys, and indexes.

If you encounter any issues, you can also create tables manually:

```bash
flask shell
```

Then in the Python shell:
```python
from app import db
db.create_all()
```

**Note:** See `DATABASE_SCHEMA.md` for complete schema documentation.

## ▶️ Running the Application

### Development Mode

```bash
python run.py
```

Or using Flask CLI:

```bash
flask run
```

The application will be available at: `http://127.0.0.1:5000/`

## 🔧 Configuration

### Database Options

The application uses PyMySQL as the MySQL driver. You can configure the database connection in your `.env` file.

**Connection String Format:**
```
mysql+pymysql://username:password@host:port/database_name
```

### Email Setup

For password reset functionality, configure SMTP settings in `.env`:

**Gmail Example:**
1. Enable 2FA on your Gmail account
2. Generate an App Password: https://myaccount.google.com/apppasswords
3. Use the App Password in `MAIL_PASSWORD`


## 🐛 Troubleshooting

### Database Connection Error
```
pymysql.err.OperationalError: (2003, "Can't connect to MySQL server")
```
**Solution:** Ensure MySQL server is running and credentials in `.env` are correct.

### Module Not Found Error
```
ModuleNotFoundError: No module named 'app'
```
**Solution:** Make sure you're in the project root directory and virtual environment is activated.

### Port Already in Use
```
OSError: [WinError 10048] Only one usage of each socket address
```
**Solution:** Change port in `run.py` or stop other applications using port 5000.

### Email Not Sending
```
SMTPAuthenticationError
```
**Solution:** Use App Password for Gmail, not regular password. Enable less secure apps if using other providers.


## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

This project is proprietary software. All rights reserved.

**Built with Flask ❤️**
