from email_server import send_result_emails

result = {
    "username": "candidate0001",
    "fullname": "John Doe",
    "subject": "Biology",
    "correct": 30,
    "total": 40,
    "score": 75,
    "time_taken": 1250,
    "submitted_at": "2025-10-13 22:45",
    "email": "your_test_email@gmail.com"
}

print(send_result_emails(result))
