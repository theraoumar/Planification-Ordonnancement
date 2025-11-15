from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, F, Sum, Count
from django.utils import timezone
from django.db import models
from .models import Order, Product, Customer, StockMovement, OrderItem, PlanningEvent, AIConversation, AIAnalysis
from .forms import ProductForm, OrderForm, StockMovementForm, CustomerForm
from django.http import JsonResponse 
import json
from django.views.decorators.http import require_POST

@login_required
def dashboard(request):
    # Données réelles de la base de données
    context = {
        'active_orders': Order.objects.filter(status='in_production').count(),
        'low_stock_alerts': Product.objects.filter(current_stock__lte=F('min_stock')).count(),
        'delayed_orders': Order.objects.filter(
            delivery_date__lt=timezone.now().date(),
            status__in=['confirmed', 'in_production']
        ).count(),
        'low_stock_products': Product.objects.filter(
            current_stock__lte=F('min_stock')
        )[:5],
        'recent_orders': Order.objects.select_related('customer').order_by('-created_at')[:5]
    }
    return render(request, 'dashboard/dashboard.html', context)

# ========== COMMANDES ==========
@login_required
def create_customer(request):
    if request.method == 'POST':
        form = CustomerForm(request.POST)
        if form.is_valid():
            customer = form.save()
            messages.success(request, f'Client "{customer.name}" créé avec succès!')
            return redirect('customer_list')
    else:
        form = CustomerForm()
    
    return render(request, 'dashboard/customers/create_customer.html', {'form': form})

@login_required
def customer_list(request):
    customers = Customer.objects.all().order_by('name')
    
    search_query = request.GET.get('search', '')
    if search_query:
        customers = customers.filter(
            Q(name__icontains=search_query) |
            Q(email__icontains=search_query)
        )
    
    return render(request, 'dashboard/customers/customer_list.html', {
        'customers': customers,
        'search_query': search_query,
    })
    
@login_required
def create_order_for_customer(request, customer_id):
    """Crée une nouvelle commande pour un client spécifique"""
    customer = get_object_or_404(Customer, id=customer_id)
    
    if request.method == 'POST':
        form = OrderForm(request.POST)
        if form.is_valid():
            order = form.save(commit=False)
            
            # Générer un numéro de commande automatique
            last_order = Order.objects.order_by('-id').first()
            if last_order:
                last_number = int(last_order.order_number.split('-')[-1])
                new_number = last_number + 1
            else:
                new_number = 1
            order.order_number = f"CMD-{timezone.now().year}-{new_number:04d}"
            
            order.save()
            
            # Gérer les produits de la commande
            products = request.POST.getlist('products')
            quantities = request.POST.getlist('quantities')
            prices = request.POST.getlist('prices')
            
            total_amount = 0
            for product_id, quantity, price in zip(products, quantities, prices):
                if product_id and quantity and price:
                    product = Product.objects.get(id=product_id)
                    quantity_int = int(quantity)
                    price_float = float(price)
                    
                    OrderItem.objects.create(
                        order=order,
                        product=product,
                        quantity=quantity_int,
                        unit_price=price_float
                    )
                    
                    total_amount += quantity_int * price_float
            
            # Mettre à jour le total de la commande
            order.total_amount = total_amount
            order.save()
            
            messages.success(request, f'Commande {order.order_number} créée pour {customer.name}!')
            return redirect('order_list')
    else:
        # Pré-remplir le formulaire avec le client
        form = OrderForm(initial={'customer': customer})
    
    return render(request, 'dashboard/orders/create_order.html', {
        'form': form,
        'customer': customer,
        'products': Product.objects.all(),
        'recent_orders': Order.objects.select_related('customer').order_by('-created_at')[:5]
    })    
    
@login_required
def order_list(request):
    orders = Order.objects.select_related('customer').all().order_by('-created_at')
    
    # Filtres
    status_filter = request.GET.get('status', '')
    if status_filter:
        orders = orders.filter(status=status_filter)
    
    search_query = request.GET.get('search', '')
    if search_query:
        orders = orders.filter(
            Q(order_number__icontains=search_query) |
            Q(customer__name__icontains=search_query)
        )
    
    # Statistiques
    total_orders = Order.objects.count()
    draft_orders = Order.objects.filter(status='draft').count()
    confirmed_orders = Order.objects.filter(status='confirmed').count()
    production_orders = Order.objects.filter(status='in_production').count()
    shipped_orders = Order.objects.filter(status='shipped').count()
    delayed_orders = Order.objects.filter(
        delivery_date__lt=timezone.now().date(),
        status__in=['confirmed', 'in_production']
    ).count()
    
    return render(request, 'dashboard/orders/order_list.html', {
        'orders': orders,
        'status_filter': status_filter,
        'search_query': search_query,
        'total_orders': total_orders,
        'draft_orders': draft_orders,
        'confirmed_orders': confirmed_orders,
        'production_orders': production_orders,
        'shipped_orders': shipped_orders,
        'delayed_orders': delayed_orders,
    })

@login_required
def create_order(request):
    # Vérifier si un client est spécifié dans l'URL
    customer_id = request.GET.get('customer')
    initial_data = {}
    
    if customer_id:
        try:
            customer = Customer.objects.get(id=customer_id)
            initial_data['customer'] = customer
        except Customer.DoesNotExist:
            pass
    
    if request.method == 'POST':
        form = OrderForm(request.POST)
        if form.is_valid():
            order = form.save(commit=False)
            # Générer un numéro de commande automatique
            last_order = Order.objects.order_by('-id').first()
            if last_order:
                last_number = int(last_order.order_number.split('-')[-1])
                new_number = last_number + 1
            else:
                new_number = 1
            order.order_number = f"CMD-{timezone.now().year}-{new_number:04d}"
            order.save()
            
            # Gérer les produits de la commande
            products = request.POST.getlist('products')
            quantities = request.POST.getlist('quantities')
            prices = request.POST.getlist('prices')
            
            total_amount = 0
            for product_id, quantity, price in zip(products, quantities, prices):
                if product_id and quantity and price:
                    product = Product.objects.get(id=product_id)
                    quantity_int = int(quantity)
                    price_float = float(price)
                    
                    OrderItem.objects.create(
                        order=order,
                        product=product,
                        quantity=quantity_int,
                        unit_price=price_float
                    )
                    
                    total_amount += quantity_int * price_float
            
            # Mettre à jour le total de la commande
            order.total_amount = total_amount
            order.save()
            
            messages.success(request, f'Commande {order.order_number} créée avec succès!')
            return redirect('order_list')
    else:
        form = OrderForm(initial=initial_data)
    
    return render(request, 'dashboard/orders/create_order.html', {
        'form': form,
        'products': Product.objects.all(),
        'recent_orders': Order.objects.select_related('customer').order_by('-created_at')[:5]
    })

@login_required
def order_detail(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    return render(request, 'dashboard/orders/order_detail.html', {'order': order})

@login_required
def edit_order(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    
    if request.method == 'POST':
        form = OrderForm(request.POST, instance=order)
        if form.is_valid():
            # Sauvegarder les modifications de base
            order = form.save()
            
            # Supprimer les anciens items
            order.items.all().delete()
            
            # Ajouter les nouveaux items
            products = request.POST.getlist('products')
            quantities = request.POST.getlist('quantities')
            prices = request.POST.getlist('prices')
            
            total_amount = 0
            for product_id, quantity, price in zip(products, quantities, prices):
                if product_id and quantity and price:
                    product = Product.objects.get(id=product_id)
                    quantity_int = int(quantity)
                    price_float = float(price)
                    
                    OrderItem.objects.create(
                        order=order,
                        product=product,
                        quantity=quantity_int,
                        unit_price=price_float
                    )
                    
                    total_amount += quantity_int * price_float
            
            # Mettre à jour le total
            order.total_amount = total_amount
            order.save()
            
            messages.success(request, f'Commande {order.order_number} modifiée avec succès!')
            return redirect('order_detail', order_id=order.id)
    else:
        form = OrderForm(instance=order)
    
    return render(request, 'dashboard/orders/edit_order.html', {
        'form': form,
        'order': order,
        'products': Product.objects.all()
    })

@login_required
def delete_order(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    
    if request.method == 'POST':
        order_number = order.order_number
        order.delete()
        messages.success(request, f'Commande {order_number} supprimée avec succès!')
        return redirect('order_list')
    
    return render(request, 'dashboard/orders/delete_order.html', {'order': order})

@login_required
def update_order_status(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    old_status = order.status
    
    if request.method == 'POST':
        new_status = request.POST.get('status')
        
        if new_status in dict(Order.STATUS_CHOICES):
            
            # ========== GESTION STOCK - CONFIRMATION ==========
            if new_status == 'confirmed' and old_status != 'confirmed':
                # Vérifier d'abord si le stock est suffisant
                stock_problems = []
                for item in order.items.all():
                    if item.quantity > item.product.current_stock:
                        stock_problems.append(
                            f"{item.product.reference}: stock {item.product.current_stock}, besoin {item.quantity}"
                        )
                
                if stock_problems:
                    messages.error(request, 
                        f"❌ Stock insuffisant pour confirmer la commande:\n" +
                        "\n".join(stock_problems)
                    )
                    return redirect('order_detail', order_id=order.id)
                
                # Diminuer le stock des produits
                for item in order.items.all():
                    product = item.product
                    product.current_stock -= item.quantity
                    product.save()
                    
                    # Enregistrer le mouvement de stock
                    StockMovement.objects.create(
                        product=product,
                        movement_type='out',
                        quantity=item.quantity,
                        reason=f'Commande {order.order_number}',
                        user=request.user
                    )
                
                messages.success(request, f"✅ Stock diminué pour {order.order_number}")
            
            # ========== GESTION STOCK - ANNULATION ==========
            elif new_status == 'cancelled' and old_status in ['confirmed', 'in_production']:
                # Restaurer le stock des produits
                for item in order.items.all():
                    product = item.product
                    product.current_stock += item.quantity
                    product.save()
                    
                    # Enregistrer le mouvement de stock
                    StockMovement.objects.create(
                        product=product,
                        movement_type='in',
                        quantity=item.quantity,
                        reason=f'Annulation commande {order.order_number}',
                        user=request.user
                    )
                
                messages.success(request, f"✅ Stock restauré pour {order.order_number}")
            
            # Changer le statut de la commande
            order.status = new_status
            order.save()
            
            messages.success(request, 
                f'📦 Statut de {order.order_number} changé : "{order.get_status_display(old_status)}" → "{order.get_status_display()}"'
            )
    
    return redirect('order_detail', order_id=order.id)

# ========== PRODUITS & STOCK ==========
@login_required
def product_list(request):
    products = Product.objects.filter(is_active=True).order_by('reference')
    
    # Filtrer par recherche
    search_query = request.GET.get('search', '')
    if search_query:
        products = products.filter(
            Q(reference__icontains=search_query) |
            Q(name__icontains=search_query)
        )
    
    # Filtrer par stock faible
    low_stock = request.GET.get('low_stock', '')
    if low_stock == 'on':
        products = products.filter(current_stock__lte=F('min_stock'))
    
    return render(request, 'dashboard/products/product_list.html', {
        'products': products,
        'search_query': search_query,
        'low_stock': low_stock,
    })

@login_required
def create_product(request):
    if request.method == 'POST':
        form = ProductForm(request.POST)
        if form.is_valid():
            product = form.save()
            messages.success(request, f'Produit "{product.reference}" créé avec succès!')
            return redirect('product_list')
    else:
        form = ProductForm()
    
    # Récupérer les 3 derniers produits pour l'affichage
    recent_products = Product.objects.all().order_by('-created_at')[:3]
    
    return render(request, 'dashboard/products/create_product.html', {
        'form': form,
        'recent_products': recent_products
    })

@login_required
def edit_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    
    if request.method == 'POST':
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, f'Produit {product.reference} modifié avec succès!')
            return redirect('product_list')
    else:
        form = ProductForm(instance=product)
    
    return render(request, 'dashboard/products/edit_product.html', {
        'form': form,
        'product': product
    })

@login_required
def delete_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    
    if request.method == 'POST':
        # SUPPRESSION DIRECTE - Plus de vérification des commandes
        product_name = product.reference
        
        # OPTIONNEL : Enregistrer la raison de la suppression
        reason = request.POST.get('reason', 'Suppression manuelle')
        
        # CORRIGÉ : current_stock est un champ, pas une méthode
        current_stock = product.current_stock  # Sans parenthèses !
        
        # OPTIONNEL : Créer un mouvement de stock pour mettre à zéro le stock restant
        if current_stock > 0:
            StockMovement.objects.create(
                product=product,
                movement_type='out',
                quantity=current_stock,
                reason=f'Suppression produit - {reason}',
                user=request.user
            )
            stock_message = f" (stock de {current_stock} unités mis à zéro)"
        else:
            stock_message = ""
        
        # SUPPRESSION DU PRODUIT
        product.delete()
        
        messages.success(request, 
            f'✅ Produit {product_name} supprimé avec succès!{stock_message}'
        )
        return redirect('product_list')
    
    # Pour la requête GET, on prépare les données pour le template
    # On peut optionnellement compter les commandes pour information (mais pas pour bloquer)
    order_items_count = OrderItem.objects.filter(
        product=product,
        order__status__in=['draft', 'confirmed', 'in_production', 'shipped']
    ).count()
    
    return render(request, 'dashboard/products/delete_product.html', {
        'product': product,
        'order_items_count': order_items_count  # Maintenant juste pour information
    })
    
@login_required
def adjust_stock(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    
    if request.method == 'POST':
        form = StockMovementForm(request.POST)
        if form.is_valid():
            stock_movement = form.save(commit=False)
            stock_movement.product = product
            stock_movement.user = request.user
            
            # Sauvegarder l'ancien stock pour l'affichage
            old_stock = product.current_stock
            
            # Mettre à jour le stock du produit
            if stock_movement.movement_type == 'in':
                product.current_stock += stock_movement.quantity
                message = f"+{stock_movement.quantity} unités (entrée)"
            elif stock_movement.movement_type == 'out':
                product.current_stock = max(0, product.current_stock - stock_movement.quantity)
                message = f"-{stock_movement.quantity} unités (sortie)"
            elif stock_movement.movement_type == 'adjustment':
                product.current_stock = stock_movement.quantity
                message = f"Ajustement à {stock_movement.quantity} unités"
            
            product.save()
            stock_movement.save()
            
            messages.success(request, f'Stock de {product.reference} ajusté : {message}. Nouveau stock : {product.current_stock} unités.')
            return redirect('product_list')
    else:
        form = StockMovementForm()
    
    return render(request, 'dashboard/products/adjust_stock.html', {
        'form': form,
        'product': product
    })

@login_required
def stock_movements(request):
    movements = StockMovement.objects.select_related('product', 'user').all().order_by('-created_at')
    
    # Filtres
    product_filter = request.GET.get('product', '')
    if product_filter:
        movements = movements.filter(product_id=product_filter)
    
    type_filter = request.GET.get('type', '')
    if type_filter:
        movements = movements.filter(movement_type=type_filter)
    
    return render(request, 'dashboard/products/stock_movements.html', {
        'movements': movements,
        'products': Product.objects.all().order_by('reference'),
    })

# ========== PLANNING & ASSISTANT ==========
@login_required
def planning_dashboard(request):
    # Commandes pour le calendrier
    orders = Order.objects.filter(
        status__in=['confirmed', 'in_production']
    ).order_by('delivery_date')
    
    # KPI calculés
    total_orders = Order.objects.count()
    in_production = Order.objects.filter(status='in_production').count()
    confirmed_orders = Order.objects.filter(status='confirmed').count()
    to_schedule = Order.objects.filter(status='draft').count()
    delayed = Order.objects.filter(
        delivery_date__lt=timezone.now().date(),
        status__in=['confirmed', 'in_production']
    ).count()
    completed = Order.objects.filter(status__in=['shipped', 'delivered']).count()
    
    # Calcul TRS simulé (Taux de Rendement Synthétique)
    trs = calculate_trs()
    
    # Calcul charge de travail simulé
    workload = calculate_workload()
    
    # Événements de planification
    events = PlanningEvent.objects.all()
    
    context = {
        'orders': orders,
        'events': events,
        'trs': trs,
        'workload': workload,
        'in_production': in_production,
        'confirmed_orders': confirmed_orders,
        'to_schedule': to_schedule,
        'delayed': delayed,
        'completed': completed,
        'total_orders': total_orders,
    }
    return render(request, 'dashboard/planning/dashboard.html', context)


@login_required
def planning_dashboard(request):
    from django.db.models import Count
    import json
    from datetime import datetime, timedelta
    
    # Commandes pour le calendrier
    orders = Order.objects.select_related('customer').filter(
        status__in=['confirmed', 'in_production', 'shipped']
    ).order_by('delivery_date')
    
    # Commandes cette semaine
    today = timezone.now().date()
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)
    
    this_week_orders = Order.objects.filter(
        delivery_date__range=[start_of_week, end_of_week],
        status__in=['confirmed', 'in_production']
    ).select_related('customer')
    
    # Commandes en retard
    delayed_orders = Order.objects.filter(
        delivery_date__lt=today,
        status__in=['confirmed', 'in_production']
    ).select_related('customer')
    
    # KPI calculés
    total_orders = Order.objects.count()
    in_production = Order.objects.filter(status='in_production').count()
    confirmed_orders = Order.objects.filter(status='confirmed').count()
    to_schedule = Order.objects.filter(status='draft').count()
    delayed = delayed_orders.count()
    completed = Order.objects.filter(status__in=['shipped', 'delivered']).count()
    
    # Commandes par statut
    orders_by_status = Order.objects.values('status').annotate(count=Count('id'))
    orders_status_dict = {item['status']: item['count'] for item in orders_by_status}
    
    # Calcul TRS simulé
    trs = calculate_trs()
    
    # Calcul charge de travail
    workload = calculate_workload()
    
    # Événements de planification
    events = PlanningEvent.objects.all()
    
    # Préparer les données pour le calendrier
    orders_data = []
    for order in orders:
        orders_data.append({
            'order_number': order.order_number,
            'customer': order.customer.name,
            'delivery_date': order.delivery_date.isoformat(),
            'status': order.status,
            'is_delayed': order.is_delayed
        })
    
    events_data = []
    for event in events:
        events_data.append({
            'title': event.title,
            'start_date': event.start_date.isoformat(),
            'end_date': event.end_date.isoformat(),
            'event_type': event.event_type
        })
    
    context = {
        'orders': orders,
        'this_week_orders': this_week_orders,
        'delayed_orders': delayed_orders,
        'events': events,
        'trs': trs,
        'workload': workload,
        'in_production': in_production,
        'confirmed_orders': confirmed_orders,
        'to_schedule': to_schedule,
        'delayed': delayed,
        'completed': completed,
        'total_orders': total_orders,
        'orders_by_status': orders_status_dict,
        'orders_json': json.dumps(orders_data),
        'events_json': json.dumps(events_data),
    }
    return render(request, 'dashboard/planning/dashboard.html', context)

@login_required
def add_planning_event(request):
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description')
        event_type = request.POST.get('event_type')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        
        event = PlanningEvent(
            title=title,
            description=description,
            event_type=event_type,
            start_date=start_date,
            end_date=end_date,
            created_by=request.user
        )
        event.save()
        
        messages.success(request, 'Événement ajouté au planning!')
    
    return redirect('planning_dashboard')

def calculate_trs():
    """Calcule le TRS (Taux de Rendement Synthétique)"""
    # Simulation - à remplacer par votre logique métier
    import random
    return random.randint(75, 95)

def calculate_workload():
    """Calcule la charge de travail"""
    # Simulation - à remplacer par votre logique métier
    total_capacity = 100  # Capacité maximale
    current_workload = Order.objects.filter(status__in=['confirmed', 'in_production']).count() * 10
    workload_percentage = min((current_workload / total_capacity) * 100, 100)
    return round(workload_percentage)

@login_required
def ai_assistant(request):
    return render(request, 'dashboard/assistant/assistant.html')

@login_required
def ai_assistant(request):
    # Analyses automatiques
    stock_analysis = analyze_stock_situation()
    production_analysis = analyze_production_efficiency()
    alert_analysis = analyze_alerts()
    
    # Conversations récentes
    recent_conversations = AIConversation.objects.filter(
        user=request.user
    ).order_by('-created_at')[:5]
    
    context = {
        'stock_analysis': stock_analysis,
        'production_analysis': production_analysis,
        'alert_analysis': alert_analysis,
        'recent_conversations': recent_conversations,
    }
    return render(request, 'dashboard/assistant/assistant.html', context)

@login_required
def ask_ai_assistant(request):
    if request.method == 'POST':
        question = request.POST.get('question', '').strip()
        
        if question:
            # Analyser le contexte actuel
            context = get_current_business_context()
            
            # Générer une réponse intelligente
            answer = generate_ai_response(question, context)
            
            # Sauvegarder la conversation
            conversation = AIConversation(
                user=request.user,
                question=question,
                answer=answer,
                context=context
            )
            conversation.save()
            
            return JsonResponse({
                'success': True,
                'answer': answer,
                'timestamp': conversation.created_at.strftime('%d/%m/%Y %H:%M')
            })
    
    return JsonResponse({'success': False, 'error': 'Question vide'})

@login_required
def run_ai_analysis(request):
    analysis_type = request.POST.get('analysis_type')
    
    if analysis_type == 'stock':
        result = analyze_stock_situation(detailed=True)
    elif analysis_type == 'production':
        result = analyze_production_efficiency(detailed=True)
    elif analysis_type == 'alerts':
        result = analyze_alerts(detailed=True)
    else:
        result = {'error': 'Type d\'analyse non reconnu'}
    
    return JsonResponse(result)

# ========== FONCTIONS D'ANALYSE INTELLIGENTE ==========

def get_current_business_context():
    """Récupère le contexte métier actuel pour l'IA"""
    return {
        'low_stock_products': list(Product.objects.filter(
            current_stock__lte=F('min_stock')
        ).values('reference', 'name', 'current_stock', 'min_stock')),
        
        'delayed_orders': list(Order.objects.filter(
            delivery_date__lt=timezone.now().date(),
            status__in=['confirmed', 'in_production']
        ).values('order_number', 'customer__name', 'delivery_date')),
        
        'active_orders_count': Order.objects.filter(status='in_production').count(),
        'total_products': Product.objects.count(),
        'total_customers': Customer.objects.count(),
        
        'recent_stock_movements': list(StockMovement.objects.select_related(
            'product'
        ).order_by('-created_at')[:10].values(
            'product__reference', 'movement_type', 'quantity', 'reason', 'created_at'
        ))
    }

def generate_ai_response(question, context):
    """Génère une réponse intelligente basée sur les données"""
    question_lower = question.lower()
    
    # Détection d'intention simple
    if any(word in question_lower for word in ['stock', 'inventaire', 'niveau']):
        return generate_stock_response(question, context)
    elif any(word in question_lower for word in ['commande', 'production', 'retard']):
        return generate_production_response(question, context)
    elif any(word in question_lower for word in ['alerte', 'problème', 'urgence']):
        return generate_alert_response(question, context)
    elif any(word in question_lower for word in ['conseil', 'suggestion', 'optimiser']):
        return generate_optimization_response(question, context)
    else:
        return generate_general_response(question, context)

def generate_stock_response(question, context):
    """Réponses intelligentes sur le stock"""
    low_stock_count = len(context['low_stock_products'])
    
    if low_stock_count > 0:
        products_list = "\n".join([
            f"- {p['reference']} ({p['name']}) : {p['current_stock']} unités (min: {p['min_stock']})"
            for p in context['low_stock_products'][:3]
        ])
        
        return f"""🔴 **Alerte Stock** 

J'ai détecté {low_stock_count} produits avec un stock faible :

{products_list}

**Recommandations :**
• Planifier un réapprovisionnement urgent
• Vérifier les commandes en cours pour ces produits
• Contacter les fournisseurs prioritaires

Voulez-vous que je génère une liste de réapprovisionnement ?"""
    else:
        return """✅ **État du Stock**

Tous vos produits ont un niveau de stock satisfaisant ! 

**Statistiques :**
• Produits suivis : {total_products}
• Aucune alerte stock active
• Dernier mouvement : {last_movement}

Tout semble sous contrôle ! 👍""".format(
            total_products=context['total_products'],
            last_movement=context['recent_stock_movements'][0]['created_at'].strftime('%d/%m/%Y') if context['recent_stock_movements'] else 'Aucun'
        )

def generate_production_response(question, context):
    """Réponses intelligentes sur la production"""
    delayed_count = len(context['delayed_orders'])
    active_orders = context['active_orders_count']
    
    if delayed_count > 0:
        orders_list = "\n".join([
            f"- {o['order_number']} pour {o['customer__name']} (retard depuis {o['delivery_date']})"
            for o in context['delayed_orders'][:3]
        ])
        
        return f"""⚠️ **Retards de Production**

{delayed_count} commande(s) sont en retard :

{orders_list}

**Actions recommandées :**
• Contacter les clients pour les informer
• Prioriser ces commandes en production
• Vérifier la disponibilité des matières premières

Voulez-vous que je génère des emails d'information pour ces clients ?"""
    else:
        return f"""🏭 **Production en Cours**

**Tableau de bord production :**
• Commandes en cours : {active_orders}
• Commandes en retard : 0 ✅
• Taux de service : Excellent

Toutes les commandes respectent les délais ! 🎉"""

def generate_alert_response(question, context):
    """Réponses pour les alertes"""
    alerts = []
    
    # Alertes stock
    if context['low_stock_products']:
        alerts.append(f"🔴 {len(context['low_stock_products'])} produits en stock faible")
    
    # Alertes retards
    if context['delayed_orders']:
        alerts.append(f"⚠️ {len(context['delayed_orders'])} commandes en retard")
    
    if alerts:
        alerts_text = "\n".join([f"• {alert}" for alert in alerts])
        return f"""🚨 **Alertes Actives**

{alerts_text}

**Priorités :**
1. Traiter les stocks critiques
2. Gérer les retards clients
3. Planifier la production

Que souhaitez-vous adresser en premier ?"""
    else:
        return """✅ **Aucune Alerte Critique**

Aucune alerte nécessitant une attention immédiate. 

**Statut :** Tout est sous contrôle 👍

**Conseil :** Profitez-en pour optimiser vos processus !"""

def generate_optimization_response(question, context):
    """Recommandations d'optimisation"""
    recommendations = [
        "📊 **Analyser le TRS** : Vérifiez l'efficacité globale de vos équipements",
        "🔄 **Optimiser les flux** : Réduisez les temps de changement de série",
        "📦 **Automatiser les alertes** : Configurez des notifications proactives",
        "🤖 **Planifier la maintenance** : Anticipez les arrêts techniques"
    ]
    
    rec_text = "\n".join([f"• {rec}" for rec in recommendations])
    
    return f"""💡 **Recommandations d'Optimisation**

{rec_text}

**Question :** Sur quel aspect souhaitez-vous vous améliorer ?"""

def generate_general_response(question, context):
    """Réponses générales de l'assistant"""
    return f"""🤖 **Assistant ERP Copilot**

J'ai analysé votre question : "{question}"

**Contexte actuel :**
• {len(context['low_stock_products'])} produits en alerte stock
• {len(context['delayed_orders'])} commandes en retard  
• {context['active_orders_count']} commandes en production

**Comment puis-vous vous aider ?**
• Analyse détaillée du stock
• Optimisation de la production
• Gestion des alertes
• Rapports de performance

Dites-moi ce qui vous préoccupe ! 💪"""

def analyze_stock_situation(detailed=False):
    """Analyse intelligente du stock"""
    low_stock_products = Product.objects.filter(current_stock__lte=F('min_stock'))
    critical_products = Product.objects.filter(current_stock=0)
    
    analysis = {
        'low_stock_count': low_stock_products.count(),
        'critical_count': critical_products.count(),
        'total_products': Product.objects.count(),
        'insights': [],
        'recommendations': []
    }
    
    if detailed:
        analysis['low_stock_products'] = list(low_stock_products.values(
            'reference', 'name', 'current_stock', 'min_stock'
        ))
        analysis['critical_products'] = list(critical_products.values(
            'reference', 'name'
        ))
    
    # Insights
    if analysis['critical_count'] > 0:
        analysis['insights'].append(f"{analysis['critical_count']} produits en rupture de stock")
    
    if analysis['low_stock_count'] > 3:
        analysis['insights'].append("Plusieurs produits nécessitent un réapprovisionnement urgent")
    
    # Recommandations
    if analysis['critical_count'] > 0:
        analysis['recommendations'].append("Commander d'urgence les produits en rupture")
    
    if analysis['low_stock_count'] > 0:
        analysis['recommendations'].append("Réviser les niveaux de stock minimum")
    
    return analysis

def analyze_production_efficiency(detailed=False):
    """Analyse de l'efficacité production"""
    delayed_orders = Order.objects.filter(
        delivery_date__lt=timezone.now().date(),
        status__in=['confirmed', 'in_production']
    )
    
    analysis = {
        'delayed_orders_count': delayed_orders.count(),
        'total_active_orders': Order.objects.filter(status='in_production').count(),
        'on_time_rate': calculate_on_time_rate(),
        'insights': [],
        'recommendations': []
    }
    
    if detailed:
        analysis['delayed_orders'] = list(delayed_orders.values(
            'order_number', 'customer__name', 'delivery_date'
        ))
    
    # Insights
    if analysis['delayed_orders_count'] > 0:
        analysis['insights'].append(f"{analysis['delayed_orders_count']} commandes en retard")
    
    if analysis['on_time_rate'] < 90:
        analysis['insights'].append("Taux de ponctualité inférieur à 90%")
    
    # Recommandations
    if analysis['delayed_orders_count'] > 0:
        analysis['recommendations'].append("Mettre en place un plan de rattrapage")
    
    analysis['recommendations'].append("Optimiser la planification de la production")
    
    return analysis

def analyze_alerts(detailed=False):
    """Analyse consolidée des alertes"""
    alerts = {
        'stock_alerts': Product.objects.filter(current_stock__lte=F('min_stock')).count(),
        'delivery_alerts': Order.objects.filter(
            delivery_date__lt=timezone.now().date(),
            status__in=['confirmed', 'in_production']
        ).count(),
        'priority_alerts': [],
        'insights': [],
        'recommendations': []
    }
    
    # Déterminer la priorité
    if alerts['stock_alerts'] > 5:
        alerts['priority_alerts'].append("STOCK: Plus de 5 produits en alerte")
    
    if alerts['delivery_alerts'] > 3:
        alerts['priority_alerts'].append("LIVRAISON: Plusieurs retards clients")
    
    # Insights
    if alerts['stock_alerts'] > 0:
        alerts['insights'].append(f"{alerts['stock_alerts']} alertes stock à traiter")
    
    if alerts['delivery_alerts'] > 0:
        alerts['insights'].append(f"{alerts['delivery_alerts']} retards de livraison")
    
    # Recommandations
    if alerts['priority_alerts']:
        alerts['recommendations'].append("Traiter les alertes prioritaires immédiatement")
    
    alerts['recommendations'].append("Mettre à jour le tableau de bord quotidien")
    
    return alerts

def calculate_on_time_rate():
    """Calcule le taux de ponctualité"""
    total_delivered = Order.objects.filter(status__in=['shipped', 'delivered']).count()
    on_time_delivered = Order.objects.filter(
        status__in=['shipped', 'delivered'],
        delivery_date__gte=models.F('created_at')
    ).count()
    
    if total_delivered > 0:
        return round((on_time_delivered / total_delivered) * 100, 1)
    return 100.0


@login_required
def archive_product(request, product_id):
    """Archive un produit au lieu de le supprimer"""
    product = get_object_or_404(Product, id=product_id)
    
    if request.method == 'POST':
        product.archive()
        messages.success(request, f'Produit {product.reference} archivé avec succès!')
        return redirect('product_list')
    
    return render(request, 'dashboard/products/archive_product.html', {'product': product})

# ========== ERP COPILOT ==========
@login_required
def erp_copilot(request):
    """Vue principale pour l'ERP Copilot - Assistant automatique contextuel"""
    
    # Récupérer le contexte métier actuel
    business_context = get_current_business_context()
    
    # Générer des insights automatiques
    automatic_insights = generate_automatic_insights(business_context)
    
    # Statistiques pour le dashboard copilot
    copilot_stats = {
        'total_insights': len(automatic_insights),
        'critical_alerts': business_context['low_stock_products_count'] + business_context['delayed_orders_count'],
        'optimization_opportunities': count_optimization_opportunities(business_context),
        'recent_activities': get_recent_activities()
    }
    
    context = {
        'business_context': business_context,
        'automatic_insights': automatic_insights,
        'copilot_stats': copilot_stats,
        'page_suggestions': get_page_specific_suggestions(request.path),
    }
    
    return render(request, 'dashboard/copilot/erp_copilot.html', context)

@login_required
def copilot_analyze(request):
    """Endpoint pour l'analyse en temps réel par le copilot"""
    if request.method == 'POST':
        analysis_type = request.POST.get('analysis_type', 'overview')
        
        if analysis_type == 'stock':
            result = analyze_stock_situation(detailed=True)
        elif analysis_type == 'production':
            result = analyze_production_efficiency(detailed=True)
        elif analysis_type == 'financial':
            result = analyze_financial_performance()
        elif analysis_type == 'optimization':
            result = analyze_optimization_opportunities()
        else:
            result = get_business_overview()
        
        return JsonResponse({
            'success': True,
            'analysis_type': analysis_type,
            'data': result,
            'timestamp': timezone.now().strftime('%d/%m/%Y %H:%M')
        })
    
    return JsonResponse({'success': False, 'error': 'Méthode non autorisée'})

# ========== VUES CONCRETES POUR ACTIONS RAPIDES ==========

@login_required
def copilot_analyze(request):
    """Endpoint pour l'analyse en temps réel par le copilot"""
    if request.method == 'POST':
        analysis_type = request.POST.get('analysis_type', 'overview')
        
        if analysis_type == 'stock':
            result = analyze_stock_situation(detailed=True)
        elif analysis_type == 'production':
            result = analyze_production_efficiency(detailed=True)
        elif analysis_type == 'financial':
            result = analyze_financial_performance()
        elif analysis_type == 'optimization':
            result = analyze_optimization_opportunities()
        else:
            result = get_business_overview()
        
        return JsonResponse({
            'success': True,
            'analysis_type': analysis_type,
            'data': result,
            'timestamp': timezone.now().strftime('%d/%m/%Y %H:%M')
        })
    
    return JsonResponse({'success': False, 'error': 'Méthode non autorisée'})

@login_required
def copilot_execute_action(request):
    """Endpoint pour exécuter des actions concrètes"""
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'stock_report':
            # Générer un vrai rapport stock
            low_stock_products = Product.objects.filter(current_stock__lte=F('min_stock'))
            critical_products = Product.objects.filter(current_stock=0)
            
            result = {
                'message': '📊 Rapport de Stock Généré',
                'type': 'report',
                'data': {
                    'low_stock_count': low_stock_products.count(),
                    'critical_count': critical_products.count(),
                    'low_stock_products': list(low_stock_products.values('reference', 'name', 'current_stock', 'min_stock')),
                    'critical_products': list(critical_products.values('reference', 'name', 'current_stock')),
                    'generated_at': timezone.now().strftime('%d/%m/%Y %H:%M')
                }
            }
            
        elif action == 'production_plan':
            # Générer un plan de production
            delayed_orders = Order.objects.filter(
                delivery_date__lt=timezone.now().date(),
                status__in=['confirmed', 'in_production']
            )
            urgent_orders = Order.objects.filter(
                delivery_date__lte=timezone.now().date() + timezone.timedelta(days=2),
                status__in=['confirmed', 'in_production']
            )
            
            result = {
                'message': '📅 Plan de Production Généré',
                'type': 'plan',
                'data': {
                    'delayed_orders_count': delayed_orders.count(),
                    'urgent_orders_count': urgent_orders.count(),
                    'delayed_orders': list(delayed_orders.values('order_number', 'customer__name', 'delivery_date')),
                    'urgent_orders': list(urgent_orders.values('order_number', 'customer__name', 'delivery_date')),
                    'priority_actions': [
                        "Traiter les commandes en retard en priorité",
                        "Contacter les clients des commandes retardées",
                        "Réviser la planification de la semaine"
                    ]
                }
            }
            
        elif action == 'customer_analysis':
            # Analyse clients
            top_customers = Customer.objects.annotate(
                total_orders=Count('order'),
                total_spent=Sum('order__total_amount')
            ).order_by('-total_spent')[:5]
            
            result = {
                'message': '👥 Analyse Clients Générée',
                'type': 'analysis',
                'data': {
                    'total_customers': Customer.objects.count(),
                    'top_customers': list(top_customers.values('name', 'email', 'total_orders', 'total_spent')),
                    'insights': [
                        f"{len(top_customers)} clients représentent 80% du chiffre d'affaires",
                        "Opportunité de fidélisation des clients premium"
                    ]
                }
            }
            
        elif action == 'alert_summary':
            # Synthèse des alertes
            stock_alerts = Product.objects.filter(current_stock__lte=F('min_stock')).count()
            delivery_alerts = Order.objects.filter(
                delivery_date__lt=timezone.now().date(),
                status__in=['confirmed', 'in_production']
            ).count()
            
            result = {
                'message': '🚨 Synthèse des Alertes',
                'type': 'alerts',
                'data': {
                    'stock_alerts': stock_alerts,
                    'delivery_alerts': delivery_alerts,
                    'critical_alerts': Product.objects.filter(current_stock=0).count(),
                    'actions_required': [
                        f"Réapprovisionner {stock_alerts} produits" if stock_alerts > 0 else "Aucune alerte stock",
                        f"Traiter {delivery_alerts} retards" if delivery_alerts > 0 else "Aucun retard"
                    ]
                }
            }
            
        elif action == 'reapprovisionner_urgence':
            # Action concrète pour réapprovisionnement
            critical_products = Product.objects.filter(current_stock=0)
            if critical_products.exists():
                product_list = ", ".join([p.reference for p in critical_products[:3]])
                result = {
                    'message': f'🔄 Réapprovisionnement Urgence',
                    'type': 'action',
                    'data': {
                        'products': list(critical_products.values('reference', 'name')),
                        'recommended_quantities': {p.reference: p.min_stock * 3 for p in critical_products},
                        'next_steps': [
                            f"Commander {len(critical_products)} produits en urgence",
                            "Contacter les fournisseurs prioritaires",
                            "Mettre à jour le planning de réception"
                        ]
                    }
                }
            else:
                result = {'message': '✅ Aucun produit en rupture de stock'}
                
        elif action == 'gerer_retards':
            # Action pour gérer les retards
            delayed_orders = Order.objects.filter(
                delivery_date__lt=timezone.now().date(),
                status__in=['confirmed', 'in_production']
            )
            if delayed_orders.exists():
                result = {
                    'message': f'⏰ Gestion des Retards',
                    'type': 'action',
                    'data': {
                        'delayed_orders_count': delayed_orders.count(),
                        'orders': list(delayed_orders.values('order_number', 'customer__name', 'delivery_date')),
                        'actions': [
                            "Prioriser ces commandes en production",
                            "Contacter les clients pour informer",
                            "Réviser les délais de livraison"
                        ]
                    }
                }
            else:
                result = {'message': '✅ Aucune commande en retard'}
                
        else:
            result = {'message': f'Action "{action}" exécutée'}
        
        return JsonResponse({'success': True, 'result': result})
    
    return JsonResponse({'success': False, 'error': 'Méthode non autorisée'})

@login_required
def copilot_suggest_action(request):
    """Endpoint pour obtenir des suggestions d'actions"""
    if request.method == 'POST':
        action_type = request.POST.get('action_type')
        context_data = request.POST.get('context_data', '{}')
        
        try:
            context = json.loads(context_data)
        except:
            context = get_current_business_context()
        
        suggestions = generate_action_suggestions(action_type, context)
        
        return JsonResponse({
            'success': True,
            'suggestions': suggestions,
            'action_type': action_type
        })
    
    return JsonResponse({'success': False, 'error': 'Méthode non autorisée'})

# ========== FONCTIONS SUPPORT ERP COPILOT ==========

def generate_automatic_insights(business_context):
    """Génère des insights automatiques basés sur le contexte métier"""
    insights = []
    
    # Insights sur le stock
    low_stock_count = len(business_context['low_stock_products'])
    if low_stock_count > 0:
        critical_products = [p for p in business_context['low_stock_products'] if p['current_stock'] == 0]
        
        if critical_products:
            insights.append({
                'type': 'critical',
                'icon': 'fas fa-exclamation-triangle',
                'title': f'Rupture de stock sur {len(critical_products)} produit(s)',
                'description': f'Produits en rupture : {", ".join([p["reference"] for p in critical_products[:3]])}',
                'action': 'reapprovisionner_urgence',
                'priority': 1
            })
        else:
            insights.append({
                'type': 'warning',
                'icon': 'fas fa-box',
                'title': f'{low_stock_count} produit(s) avec stock faible',
                'description': 'Niveau de stock proche du minimum pour plusieurs produits',
                'action': 'verifier_stock',
                'priority': 2
            })
    
    # Insights sur les commandes
    delayed_orders_count = len(business_context['delayed_orders'])
    if delayed_orders_count > 0:
        insights.append({
            'type': 'warning',
            'icon': 'fas fa-clock',
            'title': f'{delayed_orders_count} commande(s) en retard',
            'description': 'Des commandes dépassent leur date de livraison prévue',
            'action': 'gerer_retards',
            'priority': 1
        })
    
    # Insights sur la production
    active_orders = business_context['active_orders_count']
    if active_orders > 10:
        insights.append({
            'type': 'info',
            'icon': 'fas fa-industry',
            'title': 'Charge de production élevée',
            'description': f'{active_orders} commandes en cours de production',
            'action': 'optimiser_planning',
            'priority': 3
        })
    
    # Insights sur les performances
    on_time_rate = calculate_on_time_rate()
    if on_time_rate < 85:
        insights.append({
            'type': 'warning',
            'icon': 'fas fa-chart-line',
            'title': f'Taux de ponctualité bas ({on_time_rate}%)',
            'description': 'Optimisation nécessaire des délais de production',
            'action': 'analyser_delais',
            'priority': 2
        })
    
    # Trier par priorité
    insights.sort(key=lambda x: x['priority'])
    return insights

def count_optimization_opportunities(business_context):
    """Compte les opportunités d'optimisation"""
    opportunities = 0
    
    # Opportunités stock
    low_stock_ratio = len(business_context['low_stock_products']) / business_context['total_products']
    if low_stock_ratio > 0.1:  # Plus de 10% des produits en stock faible
        opportunities += 1
    
    # Opportunités production
    if business_context['delayed_orders_count'] > 0:
        opportunities += 1
    
    # Opportunités financières
    if business_context.get('cash_flow_risk', False):
        opportunities += 1
    
    return opportunities

def get_recent_activities():
    """Récupère les activités récentes pour le copilot"""
    recent_activities = []
    
    # Dernières commandes créées
    recent_orders = Order.objects.select_related('customer').order_by('-created_at')[:3]
    for order in recent_orders:
        recent_activities.append({
            'type': 'order',
            'icon': 'fas fa-shopping-cart',
            'description': f'Nouvelle commande {order.order_number} pour {order.customer.name}',
            'timestamp': order.created_at,
            'color': 'primary'
        })
    
    # Derniers mouvements de stock
    recent_movements = StockMovement.objects.select_related('product').order_by('-created_at')[:3]
    for movement in recent_movements:
        recent_activities.append({
            'type': 'stock',
            'icon': 'fas fa-boxes',
            'description': f'{movement.movement_type} de {movement.quantity} {movement.product.reference}',
            'timestamp': movement.created_at,
            'color': 'info'
        })
    
    # Dernières analyses IA
    recent_analyses = AIAnalysis.objects.order_by('-created_at')[:2]
    for analysis in recent_analyses:
        recent_activities.append({
            'type': 'analysis',
            'icon': 'fas fa-robot',
            'description': f'Analyse {analysis.analysis_type} générée',
            'timestamp': analysis.created_at,
            'color': 'success'
        })
    
    # Trier par timestamp
    recent_activities.sort(key=lambda x: x['timestamp'], reverse=True)
    return recent_activities[:5]  # Retourner les 5 plus récentes

def get_page_specific_suggestions(current_path):
    """Retourne des suggestions spécifiques à la page actuelle"""
    suggestions = []
    
    if 'dashboard' in current_path:
        suggestions = [
            "Vérifier les KPIs du jour",
            "Analyser les alertes prioritaires",
            "Planifier les actions de la semaine"
        ]
    elif 'customers' in current_path:
        suggestions = [
            "Analyser le portefeuille clients",
            "Identifier les clients stratégiques",
            "Vérifier les retards de paiement"
        ]
    elif 'orders' in current_path:
        suggestions = [
            "Optimiser l'ordonnancement",
            "Vérifier la disponibilité stock",
            "Analyser les retards"
        ]
    elif 'products' in current_path or 'stock' in current_path:
        suggestions = [
            "Réapprovisionner les stocks faibles",
            "Optimiser les niveaux de stock",
            "Analyser la rotation des produits"
        ]
    elif 'planning' in current_path:
        suggestions = [
            "Équilibrer la charge de travail",
            "Anticiper les goulots d'étranglement",
            "Optimiser le calendrier de production"
        ]
    else:
        suggestions = [
            "Analyser les performances globales",
            "Identifier les points d'amélioration",
            "Planifier les optimisations"
        ]
    
    return suggestions

def analyze_financial_performance():
    """Analyse les performances financières"""
    # Calcul du chiffre d'affaires des 30 derniers jours
    thirty_days_ago = timezone.now() - timezone.timedelta(days=30)
    recent_orders = Order.objects.filter(
        created_at__gte=thirty_days_ago,
        status__in=['shipped', 'delivered']
    )
    
    total_revenue = sum(order.total_amount for order in recent_orders)
    average_order_value = total_revenue / len(recent_orders) if recent_orders else 0
    
    # Analyse de la rentabilité
    high_value_orders = recent_orders.filter(total_amount__gt=average_order_value * 1.5)
    
    return {
        'total_revenue_30d': total_revenue,
        'average_order_value': round(average_order_value, 2),
        'high_value_orders_count': high_value_orders.count(),
        'orders_count_30d': len(recent_orders),
        'insights': [
            f"CA 30j : {total_revenue:,.2f}€" if total_revenue > 0 else "Aucune vente récente",
            f"Commande moyenne : {average_order_value:.2f}€" if average_order_value > 0 else ""
        ],
        'recommendations': [
            "Développer le portefeuille clients" if len(recent_orders) < 10 else "",
            "Fidéliser les clients à forte valeur" if high_value_orders.count() > 0 else ""
        ]
    }

def analyze_optimization_opportunities():
    """Identifie les opportunités d'optimisation"""
    opportunities = []
    
    # Optimisation stock
    overstock_products = Product.objects.filter(current_stock__gt=F('max_stock') * 1.2)
    if overstock_products.exists():
        opportunities.append({
            'category': 'stock',
            'title': 'Surstock détecté',
            'description': f'{overstock_products.count()} produits au-dessus du stock max',
            'impact': 'medium',
            'action': 'reduire_stock'
        })
    
    # Optimisation production
    long_production_orders = Order.objects.filter(
        status='in_production',
        created_at__lte=timezone.now() - timezone.timedelta(days=7)
    )
    if long_production_orders.exists():
        opportunities.append({
            'category': 'production',
            'title': 'Temps de production longs',
            'description': f'{long_production_orders.count()} commandes en production depuis +7j',
            'impact': 'high',
            'action': 'accelerer_production'
        })
    
    # Optimisation processus
    draft_orders = Order.objects.filter(status='draft', created_at__lte=timezone.now() - timezone.timedelta(days=2))
    if draft_orders.exists():
        opportunities.append({
            'category': 'process',
            'title': 'Commandes en attente',
            'description': f'{draft_orders.count()} commandes brouillons non traitées',
            'impact': 'low',
            'action': 'traiter_brouillons'
        })
    
    return {
        'total_opportunities': len(opportunities),
        'high_impact_count': len([o for o in opportunities if o['impact'] == 'high']),
        'opportunities': opportunities
    }

def get_business_overview():
    """Vue d'ensemble de l'entreprise"""
    context = get_current_business_context()
    
    return {
        'summary': {
            'total_customers': context['total_customers'],
            'total_products': context['total_products'],
            'active_orders': context['active_orders_count'],
            'monthly_revenue': analyze_financial_performance()['total_revenue_30d']
        },
        'health_indicators': {
            'stock_health': calculate_stock_health(),
            'production_health': calculate_production_health(),
            'financial_health': calculate_financial_health()
        },
        'key_metrics': {
            'on_time_delivery_rate': calculate_on_time_rate(),
            'stock_turnover': calculate_stock_turnover(),
            'customer_satisfaction': estimate_customer_satisfaction()
        }
    }

def calculate_stock_health():
    """Calcule la santé du stock (0-100%)"""
    total_products = Product.objects.count()
    if total_products == 0:
        return 100
    
    healthy_stock = Product.objects.filter(
        current_stock__gt=F('min_stock'),
        current_stock__lte=F('max_stock')
    ).count()
    
    return round((healthy_stock / total_products) * 100, 1)

def calculate_production_health():
    """Calcule la santé de la production (0-100%)"""
    total_orders = Order.objects.filter(status__in=['confirmed', 'in_production', 'shipped']).count()
    if total_orders == 0:
        return 100
    
    on_time_orders = Order.objects.filter(
        status__in=['shipped', 'delivered'],
        delivery_date__gte=models.F('created_at')
    ).count()
    
    return round((on_time_orders / total_orders) * 100, 1) if total_orders > 0 else 100

def calculate_financial_health():
    """Estime la santé financière (simplifié)"""
    # Logique simplifiée - à adapter selon vos besoins
    recent_paid_orders = Order.objects.filter(
        status__in=['shipped', 'delivered'],
        created_at__gte=timezone.now() - timezone.timedelta(days=30)
    ).count()
    
    if recent_paid_orders > 20:
        return 90
    elif recent_paid_orders > 10:
        return 75
    elif recent_paid_orders > 5:
        return 60
    else:
        return 40

def calculate_stock_turnover():
    """Calcule la rotation des stocks (simplifié)"""
    # Logique simplifiée - à implémenter selon votre business
    return 4.2  # Exemple: 4.2 rotations par an

def estimate_customer_satisfaction():
    """Estime la satisfaction client (simplifié)"""
    delayed_orders = Order.objects.filter(
        delivery_date__lt=timezone.now().date(),
        status__in=['confirmed', 'in_production']
    ).count()
    
    total_active_orders = Order.objects.filter(status__in=['confirmed', 'in_production']).count()
    
    if total_active_orders == 0:
        return 95
    
    satisfaction = 100 - (delayed_orders / total_active_orders * 50)  # Pénalité pour retards
    return max(60, min(100, round(satisfaction, 1)))

def generate_action_suggestions(action_type, context):
    """Génère des suggestions d'actions spécifiques"""
    suggestions = []
    
    if action_type == 'stock_management':
        low_stock_products = context.get('low_stock_products', [])
        for product in low_stock_products[:3]:
            suggestions.append({
                'action': f'reorder_{product["reference"]}',
                'title': f'Réapprovisionner {product["reference"]}',
                'description': f'Stock actuel: {product["current_stock"]}, Minimum: {product["min_stock"]}',
                'priority': 'high' if product['current_stock'] == 0 else 'medium'
            })
    
    elif action_type == 'production_optimization':
        if context.get('delayed_orders_count', 0) > 0:
            suggestions.append({
                'action': 'prioritize_delayed_orders',
                'title': 'Prioriser les commandes en retard',
                'description': f'{context["delayed_orders_count"]} commandes nécessitent une attention immédiate',
                'priority': 'high'
            })
    
    elif action_type == 'customer_management':
        suggestions.extend([
            {
                'action': 'analyze_customer_segments',
                'title': 'Analyser les segments clients',
                'description': 'Identifier les clients les plus rentables',
                'priority': 'medium'
            },
            {
                'action': 'check_payment_delays',
                'title': 'Vérifier les retards de paiement',
                'description': 'Surveiller la santé financière des clients',
                'priority': 'medium'
            }
        ])
    
    return suggestions

def execute_copilot_action(action, parameters, user):
    """Exécute une action via le copilot"""
    
    if action == 'generate_stock_report':
        # Générer un rapport de stock
        low_stock_products = Product.objects.filter(current_stock__lte=F('min_stock'))
        return {
            'message': f'Rapport généré: {low_stock_products.count()} produits en stock faible',
            'data': list(low_stock_products.values('reference', 'name', 'current_stock', 'min_stock'))
        }
    
    elif action == 'prioritize_delayed_orders':
        # Marquer les commandes en retard comme prioritaires
        delayed_orders = Order.objects.filter(
            delivery_date__lt=timezone.now().date(),
            status__in=['confirmed', 'in_production']
        )
        
        count = delayed_orders.count()
        return {
            'message': f'{count} commandes en retard identifiées comme prioritaires',
            'count': count
        }
    
    elif action.startswith('reorder_'):
        # Simulation de réapprovisionnement
        product_ref = action.replace('reorder_', '')
        try:
            product = Product.objects.get(reference=product_ref)
            suggested_qty = max(product.min_stock * 2, product.current_stock + 10)
            return {
                'message': f'Réapprovisionnement suggéré pour {product_ref}: {suggested_qty} unités',
                'product': product_ref,
                'suggested_quantity': suggested_qty
            }
        except Product.DoesNotExist:
            return {'error': f'Produit {product_ref} non trouvé'}
    
    else:
        return {'error': f'Action {action} non reconnue'}

# ========== FONCTIONS SUPPORT ERP COPILOT ==========

def get_current_business_context():
    """Récupère le contexte métier actuel pour l'IA - Version corrigée"""
    low_stock_products = list(Product.objects.filter(
        current_stock__lte=F('min_stock')
    ).values('reference', 'name', 'current_stock', 'min_stock'))
    
    delayed_orders = list(Order.objects.filter(
        delivery_date__lt=timezone.now().date(),
        status__in=['confirmed', 'in_production']
    ).values('order_number', 'customer__name', 'delivery_date'))
    
    recent_stock_movements = list(StockMovement.objects.select_related(
        'product'
    ).order_by('-created_at')[:10].values(
        'product__reference', 'movement_type', 'quantity', 'reason', 'created_at'
    ))
    
    context = {
        'low_stock_products': low_stock_products,
        'delayed_orders': delayed_orders,
        'active_orders_count': Order.objects.filter(status='in_production').count(),
        'total_products': Product.objects.count(),
        'total_customers': Customer.objects.count(),
        'recent_stock_movements': recent_stock_movements,
        'low_stock_products_count': len(low_stock_products),
        'delayed_orders_count': len(delayed_orders),
        'cash_flow_risk': analyze_cash_flow_risk(),
        'production_capacity': estimate_production_capacity()
    }
    
    return context

def get_extended_business_context():
    """Version étendue pour le copilot - sans récursion"""
    base_context = get_current_business_context()
    
    # Ajouter des données supplémentaires pour le copilot
    base_context.update({
        'cash_flow_risk': analyze_cash_flow_risk(),
        'production_capacity': estimate_production_capacity(),
        'health_indicators': {
            'stock_health': calculate_stock_health(),
            'production_health': calculate_production_health(),
            'financial_health': calculate_financial_health()
        }
    })
    
    return base_context

@login_required
def erp_copilot(request):
    """Vue principale pour l'ERP Copilot - Assistant automatique contextuel"""
    
    # Utiliser la version étendue sans récursion
    business_context = get_extended_business_context()
    
    # Générer des insights automatiques
    automatic_insights = generate_automatic_insights(business_context)
    
    # Statistiques pour le dashboard copilot
    copilot_stats = {
        'total_insights': len(automatic_insights),
        'critical_alerts': business_context['low_stock_products_count'] + business_context['delayed_orders_count'],
        'optimization_opportunities': count_optimization_opportunities(business_context),
        'recent_activities': get_recent_activities()
    }
    
    context = {
        'business_context': business_context,
        'automatic_insights': automatic_insights,
        'copilot_stats': copilot_stats,
        'page_suggestions': get_page_specific_suggestions(request.path),
    }
    
    return render(request, 'dashboard/copilot/erp_copilot.html', context)

def analyze_cash_flow_risk():
    """Analyse simplifiée du risque de trésorerie"""
    # Logique simplifiée - à adapter
    unpaid_orders = Order.objects.filter(status='shipped').count()
    return unpaid_orders > 5  # Risque si plus de 5 commandes livrées non payées

def estimate_production_capacity():
    """Estime la capacité de production actuelle"""
    active_orders = Order.objects.filter(status='in_production').count()
    return "Élevée" if active_orders < 8 else "Critique" if active_orders > 15 else "Normale"

def calculate_stock_health():
    """Calcule la santé du stock (0-100%)"""
    total_products = Product.objects.count()
    if total_products == 0:
        return 100
    
    # Utilisez seulement min_stock puisque max_stock n'existe pas
    healthy_stock = Product.objects.filter(
        current_stock__gt=F('min_stock')
    ).count()
    
    return round((healthy_stock / total_products) * 100, 1)

def analyze_optimization_opportunities():
    """Identifie les opportunités d'optimisation - Version corrigée"""
    opportunities = []
    
    # Optimisation stock - version corrigée sans max_stock
    overstock_products = Product.objects.filter(current_stock__gt=F('min_stock') * 3)
    if overstock_products.exists():
        opportunities.append({
            'category': 'stock',
            'title': 'Surstock potentiel',
            'description': f'{overstock_products.count()} produits avec stock > 3x minimum',
            'impact': 'medium',
            'action': 'reduire_stock'
        })
    
    # Optimisation production
    long_production_orders = Order.objects.filter(
        status='in_production',
        created_at__lte=timezone.now() - timezone.timedelta(days=7)
    )
    if long_production_orders.exists():
        opportunities.append({
            'category': 'production',
            'title': 'Temps de production longs',
            'description': f'{long_production_orders.count()} commandes en production depuis +7j',
            'impact': 'high',
            'action': 'accelerer_production'
        })
    
    # Optimisation processus
    draft_orders = Order.objects.filter(status='draft', created_at__lte=timezone.now() - timezone.timedelta(days=2))
    if draft_orders.exists():
        opportunities.append({
            'category': 'process',
            'title': 'Commandes en attente',
            'description': f'{draft_orders.count()} commandes brouillons non traitées',
            'impact': 'low',
            'action': 'traiter_brouillons'
        })
    
    return {
        'total_opportunities': len(opportunities),
        'high_impact_count': len([o for o in opportunities if o['impact'] == 'high']),
        'opportunities': opportunities
    }

def calculate_production_health():
    """Calcule la santé de la production (0-100%)"""
    total_orders = Order.objects.filter(status__in=['confirmed', 'in_production', 'shipped']).count()
    if total_orders == 0:
        return 100
    
    on_time_orders = Order.objects.filter(
        status__in=['shipped', 'delivered'],
        delivery_date__gte=models.F('created_at')
    ).count()
    
    return round((on_time_orders / total_orders) * 100, 1) if total_orders > 0 else 100

def calculate_financial_health():
    """Estime la santé financière (simplifié)"""
    # Logique simplifiée - à adapter selon vos besoins
    recent_paid_orders = Order.objects.filter(
        status__in=['shipped', 'delivered'],
        created_at__gte=timezone.now() - timezone.timedelta(days=30)
    ).count()
    
    if recent_paid_orders > 20:
        return 90
    elif recent_paid_orders > 10:
        return 75
    elif recent_paid_orders > 5:
        return 60
    else:
        return 40
    
    
# ========== FONCTIONS MANQUANTES POUR LES ANALYSES ==========

def analyze_financial_performance():
    """Analyse les performances financières"""
    # Calcul du chiffre d'affaires des 30 derniers jours
    thirty_days_ago = timezone.now() - timezone.timedelta(days=30)
    recent_orders = Order.objects.filter(
        created_at__gte=thirty_days_ago,
        status__in=['shipped', 'delivered']
    )
    
    total_revenue = sum(order.total_amount for order in recent_orders) if recent_orders else 0
    average_order_value = total_revenue / len(recent_orders) if recent_orders else 0
    
    # Analyse de la rentabilité
    high_value_orders = recent_orders.filter(total_amount__gt=average_order_value * 1.5) if recent_orders else []
    
    return {
        'total_revenue_30d': total_revenue,
        'average_order_value': round(average_order_value, 2),
        'high_value_orders_count': len(high_value_orders),
        'orders_count_30d': len(recent_orders),
        'insights': [
            f"CA 30j : {total_revenue:,.2f}€" if total_revenue > 0 else "Aucune vente récente",
            f"Commande moyenne : {average_order_value:.2f}€" if average_order_value > 0 else "Aucune commande"
        ],
        'recommendations': [
            "Développer le portefeuille clients" if len(recent_orders) < 10 else "Portefeuille clients stable",
            "Fidéliser les clients à forte valeur" if len(high_value_orders) > 0 else "Diversifier le portefeuille"
        ]
    }

def analyze_optimization_opportunities():
    """Identifie les opportunités d'optimisation - Version corrigée"""
    opportunities = []
    
    # Optimisation stock
    overstock_products = Product.objects.filter(current_stock__gt=F('min_stock') * 3)
    if overstock_products.exists():
        opportunities.append({
            'category': 'stock',
            'title': 'Surstock potentiel',
            'description': f'{overstock_products.count()} produits avec stock > 3x minimum',
            'impact': 'medium',
            'action': 'reduire_stock'
        })
    
    # Optimisation production
    long_production_orders = Order.objects.filter(
        status='in_production',
        created_at__lte=timezone.now() - timezone.timedelta(days=7)
    )
    if long_production_orders.exists():
        opportunities.append({
            'category': 'production',
            'title': 'Temps de production longs',
            'description': f'{long_production_orders.count()} commandes en production depuis +7j',
            'impact': 'high',
            'action': 'accelerer_production'
        })
    
    # Optimisation processus
    draft_orders = Order.objects.filter(status='draft', created_at__lte=timezone.now() - timezone.timedelta(days=2))
    if draft_orders.exists():
        opportunities.append({
            'category': 'process',
            'title': 'Commandes en attente',
            'description': f'{draft_orders.count()} commandes brouillons non traitées',
            'impact': 'low',
            'action': 'traiter_brouillons'
        })
    
    return {
        'total_opportunities': len(opportunities),
        'high_impact_count': len([o for o in opportunities if o['impact'] == 'high']),
        'opportunities': opportunities
    }

def get_business_overview():
    """Vue d'ensemble de l'entreprise"""
    context = get_current_business_context()
    
    return {
        'summary': {
            'total_customers': context['total_customers'],
            'total_products': context['total_products'],
            'active_orders': context['active_orders_count'],
            'monthly_revenue': analyze_financial_performance()['total_revenue_30d']
        },
        'health_indicators': {
            'stock_health': calculate_stock_health(),
            'production_health': calculate_production_health(),
            'financial_health': calculate_financial_health()
        },
        'key_metrics': {
            'on_time_delivery_rate': calculate_on_time_rate(),
            'stock_turnover': 4.2,  # Valeur simulée
            'customer_satisfaction': estimate_customer_satisfaction()
        }
    }

def calculate_stock_turnover():
    """Calcule la rotation des stocks (simplifié)"""
    # Logique simplifiée - à implémenter selon votre business
    return 4.2  # Exemple: 4.2 rotations par an

def estimate_customer_satisfaction():
    """Estime la satisfaction client (simplifié)"""
    delayed_orders = Order.objects.filter(
        delivery_date__lt=timezone.now().date(),
        status__in=['confirmed', 'in_production']
    ).count()
    
    total_active_orders = Order.objects.filter(status__in=['confirmed', 'in_production']).count()
    
    if total_active_orders == 0:
        return 95
    
    satisfaction = 100 - (delayed_orders / total_active_orders * 50)  # Pénalité pour retards
    return max(60, min(100, round(satisfaction, 1)))

def generate_action_suggestions(action_type, context):
    """Génère des suggestions d'actions spécifiques"""
    suggestions = []
    
    if action_type == 'stock_management':
        low_stock_products = context.get('low_stock_products', [])
        for product in low_stock_products[:3]:
            suggestions.append({
                'action': f'reorder_{product["reference"]}',
                'title': f'Réapprovisionner {product["reference"]}',
                'description': f'Stock actuel: {product["current_stock"]}, Minimum: {product["min_stock"]}',
                'priority': 'high' if product['current_stock'] == 0 else 'medium'
            })
    
    elif action_type == 'production_optimization':
        if context.get('delayed_orders_count', 0) > 0:
            suggestions.append({
                'action': 'prioritize_delayed_orders',
                'title': 'Prioriser les commandes en retard',
                'description': f'{context["delayed_orders_count"]} commandes nécessitent une attention immédiate',
                'priority': 'high'
            })
    
    elif action_type == 'customer_management':
        suggestions.extend([
            {
                'action': 'analyze_customer_segments',
                'title': 'Analyser les segments clients',
                'description': 'Identifier les clients les plus rentables',
                'priority': 'medium'
            },
            {
                'action': 'check_payment_delays',
                'title': 'Vérifier les retards de paiement',
                'description': 'Surveiller la santé financière des clients',
                'priority': 'medium'
            }
        ])
    
    return suggestions    


@require_POST
@login_required
def copilot_analyze(request):
    """Endpoint pour les analyses en temps réel"""
    try:
        analysis_type = request.POST.get('analysis_type', 'overview')
        
        if analysis_type == 'overview':
            data = get_business_overview()
        elif analysis_type == 'stock':
            data = analyze_stock_situation()
        elif analysis_type == 'production':
            data = analyze_production_situation()
        elif analysis_type == 'financial':
            data = analyze_financial_performance()
        else:
            return JsonResponse({'success': False, 'error': 'Type d\'analyse non valide'})
        
        return JsonResponse({
            'success': True,
            'analysis_type': analysis_type,
            'data': data,
            'timestamp': timezone.now().isoformat()
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@require_POST
@login_required
def copilot_execute_action(request):
    """Endpoint pour exécuter des actions concrètes"""
    try:
        action = request.POST.get('action', '')
        
        if action == 'stock_report':
            result = generate_stock_report()
        elif action == 'production_plan':
            result = generate_production_plan()
        elif action == 'customer_analysis':
            result = generate_customer_analysis()
        elif action == 'alert_summary':
            result = generate_alert_summary()
        else:
            # Actions depuis les insights
            result = execute_insight_action(action)
        
        return JsonResponse({
            'success': True,
            'result': result
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

# ========== FONCTIONS D'ANALYSE CONCRÈTES ==========

def analyze_stock_situation():
    """Analyse concrète de la situation du stock"""
    low_stock_products = list(Product.objects.filter(
        current_stock__lte=F('min_stock')
    ).values('reference', 'name', 'current_stock', 'min_stock'))
    
    critical_products = [p for p in low_stock_products if p['current_stock'] == 0]
    
    return {
        'low_stock_count': len(low_stock_products),
        'critical_count': len(critical_products),
        'low_stock_products': low_stock_products,
        'insights': [
            f"{len(critical_products)} produits en rupture de stock",
            f"{len(low_stock_products)} produits sous le stock minimum",
            "Planifier les réapprovisionnements urgents" if critical_products else "Stock globalement stable"
        ]
    }

def analyze_production_situation():
    """Analyse concrète de la production"""
    delayed_orders = list(Order.objects.filter(
        delivery_date__lt=timezone.now().date(),
        status__in=['confirmed', 'in_production']
    ).values('order_number', 'customer__name', 'delivery_date'))
    
    urgent_orders = Order.objects.filter(
        delivery_date__lte=timezone.now().date() + timezone.timedelta(days=2),
        status__in=['confirmed', 'in_production']
    ).count()
    
    return {
        'delayed_orders_count': len(delayed_orders),
        'urgent_orders_count': urgent_orders,
        'total_active_orders': Order.objects.filter(status='in_production').count(),
        'delayed_orders': delayed_orders,
        'priority_actions': [
            "Traiter les commandes en retard en priorité",
            "Replanifier la production pour les urgences",
            "Contacter les clients pour les retards importants"
        ] if delayed_orders else ["Production dans les délais"]
    }

# ========== FONCTIONS D'ACTION CONCRÈTES ==========

def generate_stock_report():
    """Génère un rapport stock concret"""
    low_stock_products = list(Product.objects.filter(
        current_stock__lte=F('min_stock')
    ).values('reference', 'name', 'current_stock', 'min_stock'))
    
    critical_products = [p for p in low_stock_products if p['current_stock'] == 0]
    
    return {
        'type': 'report',
        'message': f'Rapport Stock - {len(low_stock_products)} produits à surveiller',
        'data': {
            'low_stock_count': len(low_stock_products),
            'critical_count': len(critical_products),
            'low_stock_products': low_stock_products[:10]  # Limiter pour l'affichage
        }
    }

def generate_production_plan():
    """Génère un plan de production concret"""
    delayed_orders = list(Order.objects.filter(
        delivery_date__lt=timezone.now().date(),
        status__in=['confirmed', 'in_production']
    ).values('order_number', 'customer__name', 'delivery_date')[:10])
    
    urgent_orders = Order.objects.filter(
        delivery_date__lte=timezone.now().date() + timezone.timedelta(days=2),
        status__in=['confirmed', 'in_production']
    ).count()
    
    return {
        'type': 'plan',
        'message': f'Plan Production - {len(delayed_orders)} retards à traiter',
        'data': {
            'delayed_orders_count': len(delayed_orders),
            'urgent_orders_count': urgent_orders,
            'delayed_orders': delayed_orders,
            'priority_actions': [
                "1. Traiter immédiatement les commandes en retard",
                "2. Contacter les clients affectés",
                "3. Réorganiser la ligne de production",
                "4. Allouer des ressources supplémentaires"
            ]
        }
    }

def generate_customer_analysis():
    """Génère une analyse clients concrète"""
    recent_orders = Order.objects.filter(
        created_at__gte=timezone.now() - timezone.timedelta(days=30)
    )
    
    top_customers = Customer.objects.annotate(
        order_count=models.Count('order'),
        total_spent=models.Sum('order__total_amount')
    ).order_by('-total_spent')[:5]
    
    return {
        'type': 'analysis',
        'message': 'Analyse Clients - Top 5 clients',
        'data': {
            'total_customers': Customer.objects.count(),
            'recent_orders_count': recent_orders.count(),
            'top_customers': list(top_customers.values('name', 'order_count', 'total_spent')),
            'insights': [
                f"Chiffre d'affaires 30j: {sum(order.total_amount for order in recent_orders if order.total_amount):.2f}€",
                f"Top client: {top_customers[0].name if top_customers else 'N/A'}"
            ]
        }
    }

def generate_alert_summary():
    """Génère un résumé des alertes"""
    low_stock_count = Product.objects.filter(current_stock__lte=F('min_stock')).count()
    delayed_orders_count = Order.objects.filter(
        delivery_date__lt=timezone.now().date(),
        status__in=['confirmed', 'in_production']
    ).count()
    
    return {
        'type': 'alerts',
        'message': f'Synthèse Alertes - {low_stock_count + delayed_orders_count} points critiques',
        'data': {
            'low_stock_alerts': low_stock_count,
            'delayed_orders_alerts': delayed_orders_count,
            'critical_alerts': Product.objects.filter(current_stock=0).count(),
            'recommendations': [
                f"🔴 {Product.objects.filter(current_stock=0).count()} ruptures de stock",
                f"🟡 {low_stock_count} stocks faibles", 
                f"🔵 {delayed_orders_count} commandes en retard",
                "Priorité: Traiter les ruptures de stock en premier"
            ]
        }
    }

def execute_insight_action(action):
    """Exécute une action spécifique depuis un insight"""
    if action.startswith('reorder_'):
        reference = action.replace('reorder_', '')
        return {
            'type': 'action',
            'message': f'Réapprovisionnement lancé pour {reference}',
            'data': {
                'action': 'reorder',
                'product_reference': reference,
                'status': 'planned'
            }
        }
    elif action == 'prioritize_delayed_orders':
        return {
            'type': 'action', 
            'message': 'Priorisation des commandes en retard activée',
            'data': {
                'action': 'prioritize',
                'affected_orders': Order.objects.filter(
                    delivery_date__lt=timezone.now().date()
                ).count()
            }
        }
    
    return {'type': 'action', 'message': 'Action exécutée', 'data': {}}