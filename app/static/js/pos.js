/**
 * POS Logic - Event Delegation for HTMX compatibility
 * Handles payment method changes, change calculation, and idempotency keys.
 */

// VARIABLE GLOBAL: Persistencia del monto recibido
let lastEnteredAmount = null;

document.addEventListener('DOMContentLoaded', function () {
    // Initial check
    initializePOSState();

    // Event Delegation: Watch for changes in payment method select
    document.addEventListener('change', function (e) {
        if (e.target && e.target.id === 'cart_payment_method') {
            handlePaymentMethodChange(e.target);
        }
    });

    // Event Delegation: Watch for input in amount received (real-time change calculation)
    document.addEventListener('input', function (e) {
        if (e.target && e.target.id === 'amount_received') {
            // Calculate change in real-time as user types
            calculateChange();
        }
    });

    // Event Delegation: Format amount_received on blur (when user finishes typing)
    document.addEventListener('blur', function (e) {
        if (e.target && e.target.id === 'amount_received') {
            const input = e.target;
            const rawValue = input.value.trim();

            if (rawValue === '' || rawValue === '0') {
                return; // Don't format empty or zero
            }

            // Parse the value (handles both formats: "1550.05" or "1.550,05")
            const numericValue = parseArToNumber(rawValue);

            if (!isNaN(numericValue) && numericValue > 0) {
                // Round to integer (no decimals for received amount)
                const integerValue = Math.round(numericValue);
                // Format to Argentine style (integer only)
                input.value = formatIntegerAr(integerValue);
                // Trigger change calculation
                calculateChange();
            }
        }
    }, true); // Use capture phase to ensure it runs

    // Event Delegation: Apply button click
    document.addEventListener('click', function (e) {
        if (e.target && (e.target.id === 'apply-amount-btn' || e.target.closest('#apply-amount-btn'))) {
            const input = document.getElementById('amount_received');
            if (input) {
                const rawValue = input.value.trim();

                if (rawValue && rawValue !== '0') {
                    // Parse and format
                    const numericValue = parseArToNumber(rawValue);

                    if (!isNaN(numericValue) && numericValue > 0) {
                        const integerValue = Math.round(numericValue);
                        input.value = formatIntegerAr(integerValue);
                        calculateChange();
                    }
                }
            }
        }
    });

    // HTMX: Focus Preservation Logic
    let lastFocusId = null;
    let lastSelectionStart = null;
    let lastSelectionEnd = null;
    let lastFocusValue = null; // Guardar el valor para amount_received

    document.body.addEventListener('htmx:beforeRequest', function (evt) {
        const activeEl = document.activeElement;

        // PERSISTENCIA: Guardar el monto recibido antes de cualquier actualización
        const amountInput = document.getElementById('amount_received');
        if (amountInput && amountInput.value.trim() !== '') {
            lastEnteredAmount = amountInput.value.trim();
        }

        // Preservar foco de inputs de cantidad
        if (activeEl && activeEl.classList.contains('qty-input')) {
            lastFocusId = activeEl.getAttribute('data-product-id');
            // Fallback if ID is not set
            if (!lastFocusId && activeEl.id) lastFocusId = activeEl.id;

            lastSelectionStart = activeEl.selectionStart;
            lastSelectionEnd = activeEl.selectionEnd;
        }
        // Preservar foco del campo "Monto Recibido"
        else if (activeEl && activeEl.id === 'amount_received') {
            lastFocusId = 'amount_received';
            lastFocusValue = activeEl.value; // Guardar el valor actual
            lastSelectionStart = activeEl.selectionStart;
            lastSelectionEnd = activeEl.selectionEnd;
        }
        else {
            lastFocusId = null;
            lastFocusValue = null;
        }
    });

    document.body.addEventListener('htmx:afterSwap', function (evt) {
        // PERSISTENCIA: Restaurar el monto recibido después de actualización
        if (lastEnteredAmount !== null) {
            const amountInput = document.getElementById('amount_received');
            if (amountInput) {
                amountInput.value = lastEnteredAmount;
                // Disparar cálculo de vuelto
                calculateChange();
            }
        }

        if (lastFocusId) {
            if (lastFocusId === 'amount_received') {
                // Restaurar foco y valor del campo "Monto Recibido"
                const amountInput = document.getElementById('amount_received');
                if (amountInput) {
                    // Restaurar el valor que el usuario estaba escribiendo
                    if (lastFocusValue !== null) {
                        amountInput.value = lastFocusValue;
                    }
                    amountInput.focus();
                    // Restore cursor position
                    try {
                        if (lastSelectionStart !== null && lastSelectionEnd !== null) {
                            amountInput.setSelectionRange(lastSelectionStart, lastSelectionEnd);
                        }
                    } catch (e) {
                        // Ignore if element doesn't support selection
                    }
                    // Recalcular vuelto con el valor restaurado
                    calculateChange();
                }
            } else {
                // Try to find the qty input element again
                // We use data-product-id because it's stable across renders
                const newInput = document.querySelector(`.qty-input[data-product-id="${lastFocusId}"]`);
                if (newInput) {
                    newInput.focus();
                    // Restore cursor position if numbers match
                    try {
                        if (lastSelectionStart !== null && lastSelectionEnd !== null) {
                            newInput.setSelectionRange(lastSelectionStart, lastSelectionEnd);
                        }
                    } catch (e) {
                        // Ignore if element doesn't support selection
                    }
                }
            }
            lastFocusId = null;
            lastFocusValue = null;
        }

        // Re-initialize POS state after HTMX swap (ensures formatting is correct)
        initializePOSState();
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

        // NUEVA LÓGICA: Solo establecer valor si el campo está vacío o es inicialización
        // Esto permite la edición manual sin sobrescribir
        if (amountReceivedInput) {
            const currentValue = amountReceivedInput.value.trim();

            // PERSISTENCIA: Verificar si hay un valor guardado globalmente
            const hasStoredValue = lastEnteredAmount !== null && lastEnteredAmount !== '';

            // Solo auto-completar si:
            // 1. NO hay valor guardado en la variable global
            // 2. Es inicialización (primera carga) O el campo está vacío O el valor es "0"
            if (!hasStoredValue && (isInit || currentValue === '' || currentValue === '0')) {
                const totalInteger = Math.ceil(total);
                amountReceivedInput.value = formatIntegerAr(totalInteger);
            }
            // Si ya tiene un valor o hay uno guardado, NO lo toques - permite edición manual
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
 * Formatea un número entero en estilo argentino (solo miles, sin decimales):
 * - Separador de miles: punto (.)
 * - Sin decimales
 * 
 * Ejemplos: 1000 -> "1.000", 1550 -> "1.550"
 */
function formatIntegerAr(value) {
    if (value === null || value === undefined || isNaN(value)) return '0';

    const num = Math.round(parseFloat(value)); // Ensure integer
    if (num === 0) return '0';

    // Formatear con separador de miles
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, '.');
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
    const changeLabel = document.getElementById('change-label');
    const changeAmountSpan = document.getElementById('change-amount');
    const paymentChangedInput = document.getElementById('payment-change-input');
    const paymentReceivedInput = document.getElementById('payment-received-input');
    const paymentAmountInput = document.getElementById('payment-amount-input');

    if (!amountReceivedInput || !paymentAmountInput) return;

    // Parsear formato argentino si es texto
    const receivedValue = amountReceivedInput.value.trim();

    // Si está vacío, no mostrar vuelto
    if (receivedValue === '' || receivedValue === '0') {
        if (changeDisplay) changeDisplay.style.display = 'none';
        if (paymentChangedInput) paymentChangedInput.value = '0';
        if (paymentReceivedInput) paymentReceivedInput.value = '0';
        return;
    }

    const received = parseArToNumber(receivedValue);
    const total = parseFloat(paymentAmountInput.value) || 0;
    const diferencia = received - total;

    // Update hidden inputs for submission (mantener precisión decimal)
    if (paymentReceivedInput) {
        // Redondear a entero para el backend
        paymentReceivedInput.value = Math.round(received).toString();
    }

    if (diferencia >= 0) {
        // CASO VUELTO: El cliente pagó suficiente o más
        if (changeLabel) changeLabel.textContent = 'Vuelto';
        if (changeAmountSpan) changeAmountSpan.textContent = formatSmartAr(diferencia);

        if (changeDisplay) {
            changeDisplay.style.display = 'block';
            // Aplicar clase de éxito (verde)
            changeDisplay.classList.remove('text-danger');
            changeDisplay.classList.add('text-success');
        }

        if (paymentChangedInput) paymentChangedInput.value = diferencia.toFixed(2);

    } else {
        // CASO FALTA: El cliente no pagó suficiente
        if (changeLabel) changeLabel.textContent = 'Falta';
        if (changeAmountSpan) changeAmountSpan.textContent = formatSmartAr(Math.abs(diferencia));

        if (changeDisplay) {
            changeDisplay.style.display = 'block';
            // Aplicar clase de error (rojo)
            changeDisplay.classList.remove('text-success');
            changeDisplay.classList.add('text-danger');
        }

        if (paymentChangedInput) paymentChangedInput.value = '0'; // No hay vuelto
    }
}
