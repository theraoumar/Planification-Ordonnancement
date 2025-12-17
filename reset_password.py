import os
import django
import sys

# Setup Django environment
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'erp_copilot.settings')
django.setup()

from django.contrib.auth import get_user_model
User = get_user_model()

try:
    u = User.objects.get(username='supervisor')
    u.set_password('password123')
    u.save()
    print("Password for user 'supervisor' has been reset to: password123")
except User.DoesNotExist:
    print("User 'supervisor' not found.")
