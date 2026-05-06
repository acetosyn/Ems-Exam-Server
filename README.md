# EMIS Exam Portal

A modern, responsive exam portal built for Epitome Model Islamic Schools (EMIS) using Flask templates and Tailwind CSS.

## Features

- **Modern UI**: Clean, professional design with sky blue and navy color scheme
- **Responsive Design**: Mobile-first approach that works on all devices
- **Interactive Exam System**: Timer, navigation, question flagging, and progress tracking
- **Anti-cheat Features**: Tab switch detection, fullscreen mode, disabled right-click
- **Admin Dashboard**: Generate candidate credentials and manage exams
- **Offline Support**: Graceful handling of network issues
- **Keyboard Shortcuts**: Quick navigation and answer selection

## Project Structure

\`\`\`
emis_exam_portal_flask/
├── app.py                 # Flask application
├── README.md             # This file
├── templates/            # HTML templates
│   ├── base.html        # Base template with header/footer
│   ├── login.html       # Login page
│   ├── admin.html       # Admin dashboard
│   ├── exam.html        # Exam interface
│   └── result.html      # Results page
└── static/              # Static assets
    ├── css/             # Stylesheets
    │   ├── base.css     # Base styles
    │   └── exam.css     # Exam-specific styles
    ├── js/              # JavaScript files
    │   ├── utils.js     # Utility functions
    │   ├── admin.js     # Admin functionality
    │   ├── exam.js      # Exam logic
    │   └── mail.js      # Email functionality
    ├── images/          # Images and icons
    │   └── logo-placeholder.svg
    └── data/            # JSON data files
        └── exam.json    # Exam questions
\`\`\`

## Local Development

1. **Create virtual environment:**
   \`\`\`bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   \`\`\`

2. **Install dependencies:**
   \`\`\`bash
   pip install flask
   \`\`\`

3. **Run the application:**
   \`\`\`bash
   flask run
   \`\`\`

4. **Open in browser:**
   Navigate to `http://localhost:5000`

## Usage

1. **Login**: Use the login page to access the system
2. **Admin**: Generate candidate credentials and manage exams
3. **Exam**: Take exams with timer, navigation, and anti-cheat features
4. **Results**: View exam results with score and time taken

## Technical Details

- **Backend**: Flask (Python)
- **Frontend**: HTML templates with Tailwind CSS
- **JavaScript**: Vanilla JS for interactivity
- **Data**: JSON files for exam questions (loaded dynamically)
- **Storage**: localStorage and sessionStorage for client-side data

## Exam Features

- Dynamic question loading from `static/data/exam.json`
- Randomized answer options
- Auto-save answers in sessionStorage
- Timer with visual countdown
- Question flagging and review
- Progress tracking
- Anti-cheat measures (tab switching, fullscreen, disabled shortcuts)
- Keyboard shortcuts for navigation

## Browser Support

Modern browsers with ES6+ support recommended. Tested on:
- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

## License

© 2025 EMIS - Epitome Model Islamic Schools. All rights reserved.
