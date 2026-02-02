/**
 * POS Logic - Event Delegation for HTMX compatibility
 * Handles payment method changes, change calculation, and idempotency keys.
 */

document.addEventListener('DOMContentLoaded', function () {
    // Initial check
    initializePOSState();

    // Event Delegation: Watch for changes in payment method select
    document.addEventListener('change', function (e) {
        if (e.target && e.target.id === 'cart_payment_method') {
            handlePaymentMethodChange(e.target);
        }
    });

    // Event Delegation: Watch for input in amount received
    document.addEventListener('input', function (e) {
        if (e.target && e.target.id === 'amount_received') {
            calculateChange();
        }
    });

    // HTMX: Focus Preservation Logic
    let lastFocusId = null;
    let lastSelectionStart = null;
    let lastSelectionEnd = null;

    document.body.addEventListener('htmx:beforeRequest', function (evt) {
        if (document.activeElement && document.activeElement.classList.contains('qty-input')) {
            lastFocusId = document.activeElement.getAttribute('data-product-id');
            // Fallback if ID is not set
            if (!lastFocusId && document.activeElement.id) lastFocusId = document.activeElement.id;

            lastSelectionStart = document.activeElement.selectionStart;
            lastSelectionEnd = document.activeElement.selectionEnd;
        } else {
            lastFocusId = null;
        }
    });

    document.body.addEventListener('htmx:afterSwap', function (evt) {
        if (lastFocusId) {
            // Try to find the element again
            // We use data-product-id because it's stable across renders
            const newInput = document.querySelector(`.qty-input[data-product-id="${lastFocusId}"]`);
            if (newInput) {
                newInput.focus();
                // Restore cursor position if numbers match
                try {
                    newInput.setSelectionRange(lastSelectionStart, lastSelectionEnd);
                } catch (e) { }
            }
        }
    });

    // HTMX: After Swap Hook (Re-hydrate state if needed)
    document.body.addEventListener('htmx:load', function (evt) {
        // Ensure idempotency key exists
        ensureIdempotencyKey();

        // Re-apply visual state based on current select value (if present)
        const paymentSelect = document.getElementById('cart_payment_method');
        if (paymentSelect) {
            handlePaymentMethodChange(paymentSelect, false); // false = don't reset values violently
        }
    });
});

function ensureIdempotencyKey() {
    const idempotencyInput = document.getElementById('idempotency-key');
    if (idempotencyInput && !idempotencyInput.value) {
        idempotencyInput.value = crypto.randomUUID();
    }
}

function initializePOSState() {
    ensureIdempotencyKey();
    const paymentSelect = document.getElementById('cart_payment_method');
    if (paymentSelect) {
        handlePaymentMethodChange(paymentSelect, true);
    }
}

function handlePaymentMethodChange(selectElement, isInit = false) {
    const method = selectElement.value;
    const cashSection = document.getElementById('cash-received-section');
    const changeDisplay = document.getElementById('change-display');
    const paymentMethodInput = document.getElementById('payment-method-input');
    const amountReceivedInput = document.getElementById('amount_received');

    // Sync hidden input
    if (paymentMethodInput) {
        paymentMethodInput.value = method;
    }

    // Get total from hidden input (source of truth)
    const paymentAmountInput = document.getElementById('payment-amount-input');
    let total = 0;
    if (paymentAmountInput) {
        total = parseFloat(paymentAmountInput.value) || 0;
    }

    if (method === 'CASH') {
        if (cashSection) cashSection.style.display = 'block';

        // Set default received amount only if initializing or if value is empty/different context
        if (amountReceivedInput && isInit) {
            amountReceivedInput.value = formatSmartAr(total);
        } else if (amountReceivedInput && amountReceivedInput.value === '') {
            amountReceivedInput.value = formatSmartAr(total);
        }

        calculateChange();
    } else {
        if (cashSection) cashSection.style.display = 'none';
        if (changeDisplay) changeDisplay.style.display = 'none';
    }
}

/**
 * Formatea un número en estilo argentino "Smart":
 * - Separador de miles: punto (.)
 * - Separador decimal: coma (,)
 * - Elimina ceros decimales innecesarios
 * 
 * Ejemplos: 1000 -> "1.000", 1250.5 -> "1.250,5", 1250.05 -> "1.250,05"
 */
function formatSmartAr(value) {
    if (value === null || value === undefined || isNaN(value)) return '0';

    const num = parseFloat(value);
    if (num === 0) return '0';

    // Separar parte entera y decimal
    let [integerPart, decimalPart] = num.toFixed(2).split('.');

    // Eliminar ceros finales en decimales
    decimalPart = decimalPart.replace(/0+$/, '');

    // Formatear parte entera con separador de miles
    integerPart = integerPart.replace(/\B(?=(\d{3})+(?!\d))/g, '.');

    // Construir resultado
    return decimalPart ? `${integerPart},${decimalPart}` : integerPart;
}

/**
 * Convierte formato argentino a número
 * Ejemplo: "1.250,50" -> 1250.50
 */
function parseArToNumber(value) {
    if (!value || value === '') return 0;
    // Eliminar puntos (separador de miles) y reemplazar coma por punto
    const cleaned = value.toString().replace(/\./g, '').replace(',', '.');
    return parseFloat(cleaned) || 0;
}

function calculateChange() {
    const amountReceivedInput = document.getElementById('amount_received');
    const changeDisplay = document.getElementById('change-display');
    const changeAmountSpan = document.getElementById('change-amount');
    const paymentChangedInput = document.getElementById('payment-change-input');
    const paymentReceivedInput = document.getElementById('payment-received-input');
    const paymentAmountInput = document.getElementById('payment-amount-input');

    if (!amountReceivedInput || !paymentAmountInput) return;

    // Parsear formato argentino si es texto
    const received = parseArToNumber(amountReceivedInput.value);
    const total = parseFloat(paymentAmountInput.value) || 0;
    const change = received - total;

    // Update hidden inputs for submission (mantener precisión decimal)
    if (paymentReceivedInput) {
        paymentReceivedInput.value = received.toFixed(2);
    }

    if (change > 0) {
        // Usar formato Smart para visualización
        if (changeAmountSpan) changeAmountSpan.textContent = formatSmartAr(change);
        if (changeDisplay) changeDisplay.style.display = 'block';
        // Mantener precisión decimal para envío al backend
        if (paymentChangedInput) paymentChangedInput.value = change.toFixed(2);
    } else {
        if (changeDisplay) changeDisplay.style.display = 'none';
        if (paymentChangedInput) paymentChangedInput.value = '0';
    }
}
