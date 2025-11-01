from django import forms
from .models import Product, Order, Customer, StockMovement

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['reference', 'name', 'description', 'price', 'min_stock', 'current_stock']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'Description du produit...'}),
            'reference': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: P-HYDR-001'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom complet du produit'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'min_stock': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'value': '5'}),
            'current_stock': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'value': '0'}),
        }
        labels = {
            'reference': 'Référence du produit',
            'name': 'Nom du produit', 
            'description': 'Description',
            'price': 'Prix unitaire (€)',
            'min_stock': 'Stock minimum d\'alerte',
            'current_stock': 'Quantité en stock',
        }
    
    def clean_reference(self):
        reference = self.cleaned_data['reference'].strip().upper()
        if self.instance.pk is None:  # Nouveau produit
            if Product.objects.filter(reference=reference).exists():
                raise forms.ValidationError("Cette référence existe déjà. Veuillez en choisir une autre.")
        return reference
    
    def clean_price(self):
        price = self.cleaned_data['price']
        if price <= 0:
            raise forms.ValidationError("Le prix doit être supérieur à 0.")
        return price
    
    def clean_current_stock(self):
        current_stock = self.cleaned_data['current_stock']
        if current_stock < 0:
            raise forms.ValidationError("Le stock ne peut pas être négatif.")
        return current_stock
    
    def clean_min_stock(self):
        min_stock = self.cleaned_data['min_stock']
        if min_stock < 0:
            raise forms.ValidationError("Le stock minimum ne peut pas être négatif.")
        return min_stock

class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ['name', 'email', 'phone', 'address']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }

class OrderForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ['customer', 'delivery_date', 'status']
        widgets = {
            'customer': forms.Select(attrs={'class': 'form-control'}),
            'delivery_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }

class StockMovementForm(forms.ModelForm):
    class Meta:
        model = StockMovement
        fields = ['movement_type', 'quantity', 'reason']
        widgets = {
            'movement_type': forms.Select(attrs={'class': 'form-control'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control'}),
            'reason': forms.TextInput(attrs={'class': 'form-control'}),
        }
    
    def clean_quantity(self):
        quantity = self.cleaned_data['quantity']
        if quantity <= 0:
            raise forms.ValidationError("La quantité doit être positive.")
        return quantity