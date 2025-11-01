from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, F, Sum
from django.utils import timezone
from django.db import models
from .models import Order, Product, Customer, StockMovement, OrderItem, PlanningEvent, AIConversation, AIAnalysis
from .forms import ProductForm, OrderForm, StockMovementForm, CustomerForm
from django.http import JsonResponse 

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
        form = OrderForm()
    
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
    
    if request.method == 'POST':
        new_status = request.POST.get('status')
        if new_status in dict(Order.STATUS_CHOICES):
            old_status = order.get_status_display()
            order.status = new_status
            order.save()
            messages.success(request, f'Statut de la commande {order.order_number} changé de "{old_status}" à "{order.get_status_display()}"')
    
    return redirect('order_detail', order_id=order.id)

# ========== PRODUITS & STOCK ==========
@login_required
def product_list(request):
    products = Product.objects.all().order_by('reference')
    
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
    
    # Compter les commandes utilisant ce produit
    order_items_count = OrderItem.objects.filter(product=product).count()
    
    if request.method == 'POST':
        # Vérifier si le produit est utilisé dans des commandes
        if order_items_count > 0:
            messages.error(request, f'Impossible de supprimer {product.reference} car il est utilisé dans {order_items_count} commande(s).')
        else:
            product_name = product.reference
            product.delete()
            messages.success(request, f'Produit {product_name} supprimé avec succès!')
        return redirect('product_list')
    
    return render(request, 'dashboard/products/delete_product.html', {
        'product': product,
        'order_items_count': order_items_count
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