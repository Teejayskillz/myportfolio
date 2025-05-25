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
