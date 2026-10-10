# LearnSphere - E-Learning Course Management System

A Flask + SQLite web app where instructors create courses and students enroll,
track progress and win partner vouchers on course completion.

## Features
- Register / login (student or instructor), hashed passwords
- Instructors: create and delete courses with lessons
- Students: browse, search, filter, enroll, mark lessons done, progress bars
- Reward voucher (Flipkart, Amazon, Swiggy...) on completing a course (demo codes)

## Run
    pip install -r requirements.txt
    python app.py
Open http://127.0.0.1:5000  (demo instructor: teacher@demo.com / teacher123)

## Structure
    app.py            backend (routes, database, logic)
    templates/        HTML (Jinja2) pages
    static/style.css  styling
