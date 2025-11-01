from django.utils import timezone
from datetime import timedelta
from .models import Order, PlanningEvent

def calculate_detailed_trs():
    """Calcule le TRS détaillé"""
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)
    
    # Données simulées pour la démonstration
    return {
        'availability': 92.5,  # Taux de disponibilité
        'performance': 88.2,   # Taux de performance
        'quality': 96.8,       # Taux de qualité
        'trs': 78.4,           # TRS global
    }

def get_production_trends():
    """Retourne les tendances de production"""
    trends = []
    for i in range(7):
        date = timezone.now().date() - timedelta(days=6-i)
        trends.append({
            'date': date,
            'orders': Order.objects.filter(created_at__date=date).count(),
            'completed': Order.objects.filter(
                status__in=['shipped', 'delivered'],
                created_at__date=date
            ).count()
        })
    return trends