import os
import django
import sys

# Setup Django environment
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'erp_copilot.settings')
django.setup()

from django.contrib.auth import get_user_model
User = get_user_model()

print("--- Existing Users ---")
users = User.objects.all()
supervisor_exists = False
for u in users:
    role = getattr(u, 'role', 'N/A')
    print(f"User: {u.username}, Role: {role}, Active: {u.is_active}")
    if role == 'supervisor':
        supervisor_exists = True

if not supervisor_exists:
    print("\nNo supervisor found through script. Creating 'superviseur' / 'password123'...")
    try:
        if not User.objects.filter(username='superviseur').exists():
            User.objects.create_user(username='superviseur', password='password123', role='supervisor', email='sup@test.com')
            print("Successfully created user 'superviseur'")
        else:
            u = User.objects.get(username='superviseur')
            u.role = 'supervisor'
            u.set_password('password123')
            u.save()
            print("Updated existing 'superviseur' user to role 'supervisor'")
    except Exception as e:
        print(f"Error creating user: {e}")
else:
    print("\nSupervisor user already exists.")
