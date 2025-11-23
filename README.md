# Property Management System

A comprehensive property management system built with Flask, MySQL, and TailwindCSS that supports:
- Properties for Sale
- Properties for Rent
- AirBnB Listings

## Features

- ✅ Post properties (Sale, Rent, AirBnB)
- ✅ Browse and filter properties
- ✅ Property detail pages with image galleries
- ✅ Search functionality
- ✅ Price filtering
- ✅ Multiple image uploads
- ✅ Independent templates (no base.html)
- ✅ Responsive design with TailwindCSS

## Tech Stack

- **Backend**: Python Flask
- **Database**: MySQL
- **Frontend**: HTML, JavaScript, TailwindCSS (CDN)
- **File Storage**: Local file system

## Setup Instructions

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Database Configuration

Update the database credentials in `app.py` if needed:
```python
DB_CONFIG = {
    'host': 'localhost',
    'database': 'Real estate',
    'user': 'root',
    'password': '',  # Update with your MySQL password
    'port': 3306
}
```

### 3. Database Setup

1. Make sure MySQL is installed and running
2. Create the database and tables:

```bash
python init_db.py
```

Or manually using SQL:
```bash
mysql -u root -p < database_schema.sql
```

### 4. Run the Application

```bash
python app.py
```

The application will run on `http://localhost:5000`

## Project Structure

```
House property/
├── app.py                 # Main Flask application (contains DB config)
├── requirements.txt       # Python dependencies
├── database_schema.sql    # Database schema
├── init_db.py             # Database initialization script
├── templates/             # HTML templates
│   ├── index.html         # Home page
│   ├── properties.html    # Properties listing page
│   ├── property_detail.html  # Property detail page
│   └── post_property.html # Post property form
└── static/                # Static files
    ├── uploads/           # Uploaded property images
    ├── css/               # CSS files (if needed)
    └── js/                # JavaScript files (if needed)
```

## Usage

1. **Home Page** (`/`): View featured properties
2. **Properties** (`/properties`): Browse all properties with filters
3. **Property Detail** (`/property/<id>`): View detailed property information
4. **Post Property** (`/post-property`): Add a new property listing

## Filter Options

- Property Type: All, Sale, Rent, AirBnB
- Search: By location, title, or description
- Price Range: Min and max price filters

## Notes

- All templates are independent (no base.html)
- TailwindCSS is loaded via CDN
- Images are stored in `static/uploads/`
- Maximum file upload size: 16MB
- Supported image formats: PNG, JPG, JPEG, GIF, WEBP

