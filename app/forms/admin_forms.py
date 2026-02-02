"""
Admin forms for payment and subscription management.
"""
from flask_wtf import FlaskForm
from wtforms import DecimalField, DateField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, NumberRange, Length, Optional
from datetime import date


class TenantPaymentForm(FlaskForm):
    """Form for registering manual tenant payments."""
    
    amount = DecimalField(
        'Monto',
        validators=[
            DataRequired(message='El monto es requerido'),
            NumberRange(min=0.01, message='El monto debe ser mayor a 0')
        ],
        places=2,
        render_kw={'placeholder': '0.00', 'step': '0.01', 'min': '0.01'}
    )
    
    payment_date = DateField(
        'Fecha de Pago',
        validators=[DataRequired(message='La fecha es requerida')],
        default=date.today,
        format='%Y-%m-%d'
    )
    
    payment_method = SelectField(
        'Método de Pago',
        choices=[
            ('transfer', 'Transferencia Bancaria'),
            ('cash', 'Efectivo'),
            ('stripe_manual', 'Stripe (Manual)'),
            ('other', 'Otro')
        ],
        validators=[DataRequired(message='El método de pago es requerido')],
        default='transfer'
    )
    
    reference = StringField(
        'Referencia/Comprobante',
        validators=[Optional(), Length(max=255)],
        render_kw={'placeholder': 'Ej: Nro de transferencia, recibo, etc.'}
    )
    
    notes = TextAreaField(
        'Notas',
        validators=[Optional()],
        render_kw={'rows': 3, 'placeholder': 'Notas adicionales (opcional)'}
    )
