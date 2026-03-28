import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()
from accounts.models import CustomUser
admin = CustomUser.objects.filter(username='admin').first()
if admin:
    print(f"User exists: {admin.username}")
    print(f"Role: {admin.role}")
    print(f"Is approved: {admin.is_approved}")
    print(f"Password set: {bool(admin.password)}")
else:
    print("User 'admin' DOES NOT EXIST.")
