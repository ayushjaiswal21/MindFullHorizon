import requests
from bs4 import BeautifulSoup

# Start a session
session = requests.Session()

# Get the login page to get the CSRF token (if any)
login_url = 'http://127.0.0.1:5000/login'
response = session.get(login_url)
soup = BeautifulSoup(response.text, 'html.parser')

# Prepare login data
login_data = {
    'email': 'patient@example.com',
    'password': 'password',
    'role': 'patient'
}

# Perform login
response = session.post(login_url, data=login_data, allow_redirects=True)

# Now try to access the progress page
progress_url = 'http://127.0.0.1:5000/progress'
response = session.get(progress_url)

print(f"Status Code: {response.status_code}")
print(f"Page Title: {BeautifulSoup(response.text, 'html.parser').title.string}")

# Save the response to a file for inspection
with open('progress_page.html', 'w', encoding='utf-8') as f:
    f.write(response.text)

print("Progress page saved to progress_page.html")
