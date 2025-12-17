import os
import django
import sys

sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'erp_copilot.settings')
django.setup()

from django.contrib.auth import get_user_model
from dashboard.models import Order

User = get_user_model()

try:
    sup = User.objects.get(username='supervisor')
    print(f"User: {sup.username}, Role: '{sup.role}'")
except User.DoesNotExist:
    print("User 'supervisor' not found")

print("\n--- Recent Orders ---")
orders = Order.objects.all().order_by('-created_at')[:5]
for o in orders:
    print(f"Order: {o.order_number}, Status: '{o.status}'")

print("\n--- Status Explanations ---")
print("draft: Should show 'Confirmer'")
print("confirmed: Should show 'Démarrer production'")
print("in_production: Should show 'Expédier'")
print("shipped: Should show 'Livrer'")
print("delivered: NO BUTTONS SHOWN (except Cancel if allowed?) -> Actually code says no buttons for delivered")
print("cancelled: NO BUTTONS SHOWN")
