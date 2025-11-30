# ✈️ AirFlow - Prototype Demo

**Interactive passenger flow visualization for Dublin Airport Terminal 1**

## About This Prototype

This is a **proof-of-concept prototype** demonstrating passenger flow visualization at Dublin Airport using interactive heatmaps.

**Current Status:** Functional demo with simulated Terminal 1 passenger data

**What It Does:**
- Displays real-time passenger density heatmap
- Shows color-coded flow (Blue = low, Yellow = medium, Red = high)
- Interactive controls for adjusting visualization
- Live statistics dashboard

**What It's NOT:**
- Not using real flight data (uses simulated data)
- Not production-ready (proof of concept only)

---

## Quick Start

### Prerequisites

Before running, ensure you have:

- **Python 3.10+** installed
- **PostgreSQL 14+** installed and running
- **PostGIS extension** enabled
- **GDAL library** installed (for GeoDjango)

---

### Step 1: Clone or Download

```bash
git clone https://github.com/yourusername/airflow.git
cd airflow
```

Or download ZIP and extract.

---

### Step 2: Set Up Virtual Environment

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

---

### Step 3: Install Python Dependencies

```bash
pip install Django==4.2.7
pip install psycopg2-binary==2.9.9
```

**Windows users** may also need:
```bash
pip install djangorestframework
```

---

### Step 4: Set Up PostgreSQL Database

**Create Database:**
```sql
-- Open psql or pgAdmin
CREATE DATABASE airflow_db;

-- Connect to database
\c airflow_db

-- Enable PostGIS extension
CREATE EXTENSION postgis;
```

**Update Database Settings:**

Edit `airflow_project/settings.py`:

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': 'airflow_db',
        'USER': 'your_postgres_username',      # Change this
        'PASSWORD': 'your_postgres_password',  # Change this
        'HOST': 'localhost',
        'PORT': '5432',                    
    }
}
```

**Windows Users Only - Add GDAL Paths:**

Add to `settings.py` (adjust paths to match your GDAL installation):

```python
import os
GDAL_LIBRARY_PATH = r'C:\Program Files\PostgreSQL\14\bin\gdal304.dll'
GEOS_LIBRARY_PATH = r'C:\Program Files\PostgreSQL\14\bin\geos_c.dll'
```

---

### Step 5: Run Database Migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

**Expected Output:**
```
Running migrations:
  Applying core.0001_initial... OK
  Applying core.0002_passengerheatmapdata... OK
```

---

### Step 6: Load Demo Data

```bash
python manage.py load_mock_data
```
---

### Step 7: Run the Development Server

```bash
python manage.py runserver
```

**Expected Output:**
```
Starting development server at http://127.0.0.1:8000/
Quit the server with CTRL-BREAK.
```

---

### Step 8: Open in Browser

Navigate to: **http://localhost:8000**

You should see:
- Professional navbar with AirFlow branding
- Left control panel with statistics
- Interactive map centered on Dublin Airport
- Colorful heatmap overlay showing passenger density

---
