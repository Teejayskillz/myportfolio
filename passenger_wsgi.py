import sys
import os

# Step 1: Define project root
project_home = '/home/hypeblog/lagoswebdev.com'
project_name = 'myportfolio'

# Step 2: Add project and app paths to system
sys.path.insert(0, project_home)
sys.path.insert(0, os.path.join(project_home, project_name))

# Step 3: Set settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myportfolio.settings')

# Step 4: Load Django WSGI application
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()

# Set the path to your application's base directory
# This should be the directory containing 'manage.py'
# For your setup, this is '/home/hypeblog/lagoswebdev.com'
sys.path.insert(0, os.path.dirname(__file__))

# Set the path to your virtual environment's Python executable
# This path must match what you see in cPanel's "Setup Python App"
# for your application's virtual environment.
# Based on your previous logs, it's likely:
# /home/hypeblog/virtualenv/lagoswebdev.com/3.9/bin/python3.9
INTERP = "/home/hypeblog/virtualenv/lagoswebdev.com/3.9/bin/python3.9"

# Activate the virtual environment
if sys.executable != INTERP:
    os.execl(INTERP, INTERP, *sys.argv)

# Set the DJANGO_SETTINGS_MODULE environment variable
# Replace 'myportfolio' with the actual name of your Django project's settings folder
# (the one containing settings.py)
os.environ['DJANGO_SETTINGS_MODULE'] = 'myportfolio.settings'
