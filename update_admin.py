import os
import django
import sys

sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'erp_copilot.settings')
django.setup()

from django.contrib.auth import get_user_model
User = get_user_model()

try:
    user = User.objects.get(username='therapy')
    user.role = 'admin'
    user.is_staff = True # Django admin access requires is_staff often, though custom role system uses 'role' field
    user.is_superuser = True # Give full rights
    user.save()
    print(f"User 'therapy' updated to role: {user.role}")
except User.DoesNotExist:
    print("User 'therapy' does not exist. Creating...")
    User.objects.create_superuser(username='therapy', email='therapy@example.com', password='password123', role='admin')
    print("User 'therapy' created as admin.")

try:
    sup = User.objects.get(username='supervisor')
    sup.role = 'supervisor'
    sup.save()
    print(f"User 'supervisor' checked/updated to role: {sup.role}")
except User.DoesNotExist:
    print("User 'supervisor' not found!")
