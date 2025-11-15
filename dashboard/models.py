from django.db import models
from django.db.models import Sum
from django.contrib.auth.models import AbstractUser
from django.utils import timezone

class CustomUser(AbstractUser):
    ROLE_CHOICES = [
        ('admin', 'Administrateur'),
        ('manager', 'Manager'),
        ('operator', 'Opérateur'),
    ]
    
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='operator')
    phone = models.CharField(max_length=20, blank=True)
    
    def __str__(self):
        return f"{self.username} - {self.get_role_display()}"

class Customer(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    address = models.TextField()
    
    def __str__(self):
        return self.name

class Product(models.Model):
    reference = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    min_stock = models.IntegerField(default=5)
    current_stock = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.reference} - {self.name}"
    
    @property
    def is_low_stock(self):
        return self.current_stock <= self.min_stock
    
    @property
    def reserved_quantity(self):
        """Quantité réservée dans les commandes actives"""
        return OrderItem.objects.filter(
            product=self,
            order__status__in=['confirmed', 'in_production']
        ).aggregate(total=Sum('quantity'))['total'] or 0
    
    @property
    def available_stock(self):
        """Stock disponible (stock actuel - réservé)"""
        return self.current_stock - self.reserved_quantity
    
    def can_fulfill_order(self, quantity):
        """Vérifie si le stock peut satisfaire une commande"""
        return self.available_stock >= quantity
    
    is_active = models.BooleanField(default=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    
    def archive(self):
        """Archive le produit au lieu de le supprimer"""
        self.is_active = False
        self.archived_at = timezone.now()
        self.save()
    
    def restore(self):
        """Restaure un produit archivé"""
        self.is_active = True
        self.archived_at = None
        self.save()

class Order(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Brouillon'),
        ('confirmed', 'Confirmée'),
        ('in_production', 'En production'),
        ('shipped', 'Expédiée'),
        ('delivered', 'Livrée'),
        ('cancelled', 'Annulée'),
    ]
    
    order_number = models.CharField(max_length=20, unique=True)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    created_at = models.DateTimeField(auto_now_add=True)
    delivery_date = models.DateField()
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    def __str__(self):
        return self.order_number
    
    @property
    def is_delayed(self):
        return self.delivery_date < timezone.now().date() and self.status not in ['shipped', 'delivered', 'cancelled']
    
    def update_stock_on_confirm(self):
        """Diminue le stock quand une commande est confirmée"""
        for item in self.items.all():
                if item.product.current_stock >= item.quantity:
                    item.product.current_stock -= item.quantity
                    item.product.save()
                    
                    # Enregistrer le mouvement de stock
                    StockMovement.objects.create(
                        product=item.product,
                        movement_type='out',
                        quantity=item.quantity,
                        reason=f'Commande {self.order_number}',
                        user=self.customer  # ou l'utilisateur connecté
                    )
                else:
                    raise ValueError(f"Stock insuffisant pour {item.product.reference}")
    
    def restore_stock_on_cancel(self):
        """Restaure le stock quand une commande est annulée"""
        if self.status == 'cancelled':
            for item in self.items.all():
                item.product.current_stock += item.quantity
                item.product.save()
                
                # Enregistrer le mouvement de stock
                StockMovement.objects.create(
                    product=item.product,
                    movement_type='in',
                    quantity=item.quantity,
                    reason=f'Annulation commande {self.order_number}',
                    user=self.customer
                )
    
    def save(self, *args, **kwargs):
        """Override save pour gérer automatiquement les stocks"""
        old_status = None
        if self.pk:
            old_status = Order.objects.get(pk=self.pk).status
        
        super().save(*args, **kwargs)
        
        # Gestion automatique des stocks
        try:
            if old_status != self.status:
                if self.status == 'confirmed' and old_status != 'confirmed':
                    self.update_stock_on_confirm()
                elif self.status == 'cancelled' and old_status in ['confirmed', 'in_production']:
                    self.restore_stock_on_cancel()
        except Exception as e:
            # En cas d'erreur, on revert le statut
            self.status = old_status
            self.save()
            raise e
        
    @property
    def tva_amount(self):
        """Calcule la TVA simplement"""
        try:
            return float(self.total_amount) * 0.20
        except (TypeError, ValueError):
            return 0.0
    
    @property
    def total_ttc(self):
        """Calcule le total TTC simplement"""
        try:
            return float(self.total_amount) * 1.20
        except (TypeError, ValueError):
            return 0.0    

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.IntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    
    def __str__(self):
        return f"{self.order.order_number} - {self.product.name}"
    
    @property
    def tva_amount(self):
        """Calcule le montant de la TVA (20%)"""
        return round(float(self.total_amount) * 0.20, 2)
    
    @property
    def total_ttc(self):
        """Calcule le total TTC"""
        return round(float(self.total_amount) * 1.20, 2)

class StockMovement(models.Model):
    MOVEMENT_TYPES = [
        ('in', 'Entrée'),
        ('out', 'Sortie'),
        ('adjustment', 'Ajustement'),
    ]
    
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    movement_type = models.CharField(max_length=20, choices=MOVEMENT_TYPES)
    quantity = models.IntegerField()
    reason = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='dashboard_stock_movements')    
    
    def __str__(self):
        return f"{self.product.reference} - {self.movement_type} - {self.quantity}"
    
class PlanningEvent(models.Model):
    EVENT_TYPES = [
        ('maintenance', 'Maintenance'),
        ('production', 'Production'),
        ('meeting', 'Réunion'),
        ('breakdown', 'Panne'),
        ('holiday', 'Congé'),
    ]
    
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES)
    start_date = models.DateField()
    end_date = models.DateField()
    created_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.title} ({self.start_date} - {self.end_date})"
    
    @property
    def duration(self):
        return (self.end_date - self.start_date).days + 1    
    
class AIAnalysis(models.Model):
    ANALYSIS_TYPES = [
        ('stock', 'Analyse Stock'),
        ('production', 'Analyse Production'),
        ('sales', 'Analyse Ventes'),
        ('efficiency', 'Analyse Efficacité'),
    ]
    
    analysis_type = models.CharField(max_length=20, choices=ANALYSIS_TYPES)
    title = models.CharField(max_length=200)
    insights = models.JSONField()  # Stocke les insights sous forme JSON
    recommendations = models.JSONField()  # Recommandations sous forme JSON
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.get_analysis_type_display()} - {self.created_at.date()}"

class AIConversation(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    question = models.TextField()
    answer = models.TextField()
    context = models.JSONField(default=dict)  # Contexte des données au moment de la question
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.created_at.date()}"    