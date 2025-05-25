# /home/hypeblog/lagoswebdev.com/passenger_wsgi.py

import os
import sys

# IMPORTANT: Path to your virtual environment's Python executable.
# This MUST EXACTLY match what's in cPanel's "Setup Python App".
INTERP = "/home/hypeblog/virtualenv/lagoswebdev.com/3.9/bin/python3.9"

# If the current Python interpreter isn't from the virtual environment,
# restart the process using the virtual environment's interpreter.
# This ensures all subsequent code runs within the activated environment.
if sys.executable != INTERP:
    os.execl(INTERP, INTERP, *sys.argv)

# Add your project's base directory to the Python path.
# This is the directory containing 'manage.py' and your 'myportfolio' app.
sys.path.insert(0, os.path.dirname(__file__))

# Set the DJANGO_SETTINGS_MODULE environment variable.
# 'myportfolio' should be the name of your main Django project folder
# (the one containing settings.py, urls.py, wsgi.py, etc.).
os.environ['DJANGO_SETTINGS_MODULE'] = 'myportfolio.settings'

# Import and get the Django WSGI application.
# This must be the final step after all environment setup.
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()