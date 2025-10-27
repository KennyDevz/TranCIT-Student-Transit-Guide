# 🚌 TranCIT - Student Transit Guide

**TranCIT - Student Transit Guide** is a mobile-responsive web application designed to revolutionize the commuting experience for students in Cebu City. It specifically targets freshmen, transferees, and non-local students who are often unfamiliar with the local Public Utility Jeepney (PUJ) system. Our mission is to transform a typically complex and anxiety-inducing daily task into a straightforward, efficient, and stress-free journey.

## 🎯 Problem Solved

Navigating Cebu's jeepney system presents significant challenges due to:
- **Alphanumeric route codes** (e.g., 13C, 04L)
- **Reliance on informal landmark-based directions**
- **Scarcity of comprehensive, accurate digital mapping tools**

This results in:
- Students getting lost
- Taking inefficient routes
- Overpaying for fares
- Experiencing undue stress and safety concerns

## ✨ Key Features

The Student Transit Guide provides a robust set of tools to address these issues:
- **Route Finder**: Generates clear, step-by-step jeepney commute instructions between any specified origin and destination within Cebu City
- **Jeepney Code Translator**: A searchable database that deciphers local jeepney route shorthand, explaining what codes like "13C" signify
- **Fare Estimator**: An automated calculator providing accurate estimated jeepney fares based on the generated route and distance
- **Landmark-Based Navigation**: Integrates prominent city landmarks into directions for intuitive and easier wayfinding
- **Newbie Mode**: Offers a simplified interface with more detailed, beginner-friendly instructions, perfect for first-time commuters
- **Offline Route Saving**: Allows users to save generated routes for access even without an active internet connection

## 🌐 Tech Stack Used

### Frontend:
- **HTML** – Defines the structure and layout of the web pages
- **CSS** – Styles the user interface to ensure a clean and responsive design
- **JavaScript** – Adds interactivity and dynamic behavior to the frontend
- **Folium** – Python library for creating interactive maps and visualizations

### Backend:
- **Django** – Python web framework handling server-side logic, database interactions, and authentication
- **Supabase** – Provides PostgreSQL database with session pooler for efficient connection management

### Services:
- **OpenRouteService API** – Provides routing and geocoding capabilities

### Version Control:
- **Git & GitHub** – Used for source code management, version control, and team collaboration

## 📄 Setup & Run Instructions

### Prerequisites
- Python 3.8+

### Installation Steps

1. **Clone the repository**
   ```bash
   git clone https://github.com/DanDalapo/TranCIT-Student-Transit-Guide.git
   ```

2. **Change directory to the cloned project**
   ```bash
   cd TranCIT-Student-Transit-Guide
   ```

3. **Create the virtual environment**
   ```bash
   python -m venv env
   ```

4. **Activate the virtual environment**
   ```bash
   # Windows:
   env\Scripts\activate
   # MacOS/Linux:
   source env/bin/activate
   ```

5. **Install the required packages**
   ```bash
   # Install base environment dependencies
   pip install -r requirements.txt
   
   # Install project-specific dependencies
   pip install -r TranCIT/requirements.txt

6. **Create .env file to store environment-specific variables.**
   ```bash
   # Please contact developers for the database url and ors key
   # Supabase PostgreSQL (Session Pooler)
   DATABASE_URL=postgresql://username:password@host:port/database?sslmode=require

   # ORS Key
   ORS_API_KEY=ors_api_key_here
   ```

7. **Run database migrations**
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

8. **Run the server**
   ```bash
   python manage.py runserver
   ```

## 🆘 Getting Help

For database credentials and API keys, please contact:
- Developer 1 - danerik.dalapo@cit.edu
- Developer 2 - johnandrew.cauban@cit.edu
- Developer 3 - johnkenneth.devibar@cit.edu

