from django.urls import path
from django.contrib.auth.views import LoginView, LogoutView
from . import views

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),
    
    # Commandes - TOUT regrouper ici
    # Clients
    path('customers/', views.customer_list, name='customer_list'),
    path('customers/new/', views.create_customer, name='create_customer'),

    path('orders/', views.order_list, name='order_list'),
    path('orders/new/', views.create_order, name='create_order'),
    path('orders/<int:order_id>/', views.order_detail, name='order_detail'),
    path('orders/<int:order_id>/edit/', views.edit_order, name='edit_order'),
    path('orders/<int:order_id>/delete/', views.delete_order, name='delete_order'),
    path('orders/<int:order_id>/update-status/', views.update_order_status, name='update_order_status'),
    
    # Produits & Stock - TOUT regrouper ici
    path('products/', views.product_list, name='product_list'),
    path('products/new/', views.create_product, name='create_product'),
    path('products/<int:product_id>/edit/', views.edit_product, name='edit_product'),
    path('products/<int:product_id>/delete/', views.delete_product, name='delete_product'),
    path('products/<int:product_id>/adjust-stock/', views.adjust_stock, name='adjust_stock'),
    path('stock/movements/', views.stock_movements, name='stock_movements'),
    
    # Planning
    path('planning/', views.planning_dashboard, name='planning_dashboard'),
    path('planning/add-event/', views.add_planning_event, name='add_planning_event'),
    
   # Assistant IA
   path('assistant/', views.ai_assistant, name='ai_assistant'),
   path('assistant/ask/', views.ask_ai_assistant, name='ask_ai_assistant'),
   path('assistant/analyze/', views.run_ai_analysis, name='run_ai_analysis'),
    
    # Auth
    path('accounts/login/', LoginView.as_view(template_name='dashboard/login.html'), name='login'),
    path('accounts/logout/', LogoutView.as_view(next_page='login'), name='logout'),
]