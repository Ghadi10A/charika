# charika
# Charika Ecommerce Platform

Charika is an open-source ecommerce platform built with Django. It provides essential features for starting an ecommerce business, including user authentication, social account integration, internationalization, payments via Stripe, and messaging between users. 

## Features

- User authentication with email and password.
- Social account integration with Google and Microsoft for easy login/signup.
- Multi-language support with translation for Arabic, English, Turkish, French, and Spanish.
- Payment processing using Stripe.
- In-app messaging system for communication between users.
- MIT license for free and open-source use.

## Prerequisites

Before you start deploying Charika, ensure you have the following installed:

- Python 3.x
- PostgreSQL
- Redis

## Deployment

### 1. Clone the Repository

```bash
git clone https://github.com/your_username/charika.git
cd charika

2. Install Dependencies
pip install -r requirements.txt

3. Database Setup
Create a PostgreSQL database and update the DATABASES configuration in settings.py with your database credentials.
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': 'your_database_name',
        'USER': 'your_database_user',
        'PASSWORD': 'your_database_password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}

4. Redis Setup

Ensure Redis is running on your system. Update the CACHES configuration in settings.py if needed.
5. Static Files and Media Setup

Run the following commands to collect static files and prepare for media files:
python manage.py collectstatic

6. Apply Migrations

bash

python manage.py migrate

7. Set Up Stripe

Sign up for a Stripe account and obtain your publishable and secret keys. Update settings.py with your keys:
STRIPE_PUBLISHABLE_KEY = 'your_stripe_publishable_key'
STRIPE_SECRET_KEY = 'your_stripe_secret_key'

Contributing

Contributions are welcome! If you find any bugs or have suggestions for improvements, please open an issue or submit a pull request.
License

This project is licensed under the MIT License. See the LICENSE file for details.

