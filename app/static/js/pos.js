/**
 * POS Logic - Event Delegation for HTMX compatibility
 * Handles form submission, hidden input syncing, change calculation, and idempotency keys.
 * 
 * NOTE: Payment logic (enableSplitPayment, disableSplitPayment, enforcePaymentLogic)
 * is defined in new.html's inline script block.
 */

// VARIABLE GLOBAL: Estado de pago dividido y persistencia
let isSplitPayment = false;

document.addEventListener('DOMContentLoaded', function () {
    // Initial check
    initializePOSState();

    // Event Delegation: Intercept confirm-form submission
    document.addEventListener('submit', function (e) {
        if (e.target && e.target.id === 'confirm-form') {
            e.preventDefault();

            // Sync visible inputs to hidden form fields
            syncPaymentHiddenInputs();

            const form = e.target;

            // Validation: Cuenta Corriente requires a customer
            const pm1 = document.getElementById('payment_method_1');
            const pm2 = document.getElementById('payment_method_2');
            const hasCC = (pm1 && pm1.value === 'CUENTA_CORRIENTE') ||
                (isSplitPayment && pm2 && pm2.value === 'CUENTA_CORRIENTE');

            if (hasCC) {
                const customerIdInput = document.getElementById('customer_id');
                const customerId = customerIdInput ? customerIdInput.value.trim() : '';

                if (!customerId) {
                    alert('Error: Para usar Cuenta Corriente debe seleccionar un Cliente registrado.');
                    return false;
                }
            }

            // Validation: Split payment requires method 2 selected
            if (isSplitPayment) {
                if (!pm2 || !pm2.value) {
                    alert('Error: Debe seleccionar el segundo medio de pago.');
                    return false;
                }
                const amt2 = document.getElementById('amount_received_2');
                if (!amt2 || !amt2.value.trim() || parseArToNumber(amt2.value) <= 0) {
                    alert('Error: Debe ingresar el monto del segundo pago.');
                    return false;
                }
            }

            // Fetch request
            const csrfTokenMeta = document.querySelector('meta[name="csrf-token"]');
            const csrfToken = csrfTokenMeta ? csrfTokenMeta.getAttribute('content') : '';
            const formData = new FormData(form);

            fetch(form.action, {
                method: 'POST',
                headers: { 'X-CSRFToken': csrfToken },
                body: formData
            })
                .then(response => {
                    if (response.redirected) {
                        window.location.href = response.url;
                    } else if (response.ok) {
                        window.location.reload();
                    } else {
                        response.text().then(text => {
                            console.error('Submission error:', text);
                            alert('Error al confirmar venta. Por favor revise los datos.');
                        });
                    }
                })
                .catch(error => {
                    console.error('Network error:', error);
                    alert('Error de conexión al confirmar venta.');
                });
        }
    });

    // Event Delegation: Strip non-numeric characters (no letters allowed)
    document.addEventListener('input', function (e) {
        if (e.target && (e.target.id === 'amount_received_1' || e.target.id === 'amount_received_2')) {
            const cursorPos = e.target.selectionStart;
            const before = e.target.value;
            const cleaned = before.replace(/[^\d.,]/g, '');
            if (before !== cleaned) {
                e.target.value = cleaned;
                const diff = before.length - cleaned.length;
                e.target.setSelectionRange(cursorPos - diff, cursorPos - diff);
            }
        }
    }, true);

    // Event Delegation: Format amounts on blur
    document.addEventListener('blur', function (e) {
        if (e.target && (e.target.id === 'amount_received_1' || e.target.id === 'amount_received_2')) {
            const input = e.target;
            const rawValue = input.value.trim();

            if (rawValue === '' || rawValue === '0') return;

            const numericValue = parseArToNumber(rawValue);
            if (!isNaN(numericValue) && numericValue > 0) {
                input.value = formatSmartAr(numericValue);
            }
        }
    }, true);

    // HTMX: Focus Preservation Logic
    let lastFocusId = null;
    let lastSelectionStart = null;
    let lastSelectionEnd = null;
    let lastFocusValue = null;

    document.body.addEventListener('htmx:beforeRequest', function (evt) {
        const activeEl = document.activeElement;

        if (activeEl && activeEl.classList.contains('qty-input')) {
            lastFocusId = activeEl.getAttribute('data-product-id');
            if (!lastFocusId && activeEl.id) lastFocusId = activeEl.id;
            lastSelectionStart = activeEl.selectionStart;
            lastSelectionEnd = activeEl.selectionEnd;
        }
        else if (activeEl && (activeEl.id === 'amount_received_1' || activeEl.id === 'amount_received_2')) {
            lastFocusId = activeEl.id;
            lastFocusValue = activeEl.value;
            lastSelectionStart = activeEl.selectionStart;
            lastSelectionEnd = activeEl.selectionEnd;
        }
        else {
            lastFocusId = null;
            lastFocusValue = null;
        }
    });

    document.body.addEventListener('htmx:afterSwap', function (evt) {
        // Restaurar estado de split payment
        if (isSplitPayment) {
            const row2 = document.getElementById('payment-row-2');
            const btn = document.getElementById('split-payment-btn-container');
            if (row2) row2.classList.remove('d-none');
            if (btn) btn.classList.add('d-none');
        }

        if (lastFocusId) {
            if (lastFocusId === 'amount_received_1' || lastFocusId === 'amount_received_2') {
                const amountInput = document.getElementById(lastFocusId);
                if (amountInput) {
                    if (lastFocusValue !== null) amountInput.value = lastFocusValue;
                    amountInput.focus();
                    try {
                        if (lastSelectionStart !== null && lastSelectionEnd !== null) {
                            amountInput.setSelectionRange(lastSelectionStart, lastSelectionEnd);
                        }
                    } catch (e) { }
                }
            } else {
                const newInput = document.querySelector(`.qty-input[data-product-id="${lastFocusId}"]`);
                if (newInput) {
                    newInput.focus();
                    try {
                        if (lastSelectionStart !== null && lastSelectionEnd !== null) {
                            newInput.setSelectionRange(lastSelectionStart, lastSelectionEnd);
                        }
                    } catch (e) { }
                }
            }
            lastFocusId = null;
            lastFocusValue = null;
        }

        initializePOSState();
    });

    // HTMX: After Load Hook
    document.body.addEventListener('htmx:load', function (evt) {
        ensureIdempotencyKey();
    });
});

// =====================================================
// CORE FUNCTIONS
// =====================================================

function ensureIdempotencyKey() {
    const idempotencyInput = document.getElementById('idempotency-key');
    if (idempotencyInput && !idempotencyInput.value) {
        idempotencyInput.value = crypto.randomUUID();
    }
}

function initializePOSState() {
    ensureIdempotencyKey();
}

/**
 * Sync visible payment inputs to hidden form fields before submission.
 */
function syncPaymentHiddenInputs() {
    const pm1Select = document.getElementById('payment_method_1');
    const amt1Input = document.getElementById('amount_received_1');

    const hiddenMethod0 = document.getElementById('payment-method-input-0');
    const hiddenAmount0 = document.getElementById('payment-amount-input-0');
    const hiddenReceived0 = document.getElementById('payment-received-input-0');

    if (pm1Select && hiddenMethod0) {
        hiddenMethod0.value = pm1Select.value;
    }

    if (amt1Input && hiddenAmount0) {
        const numericAmt1 = parseArToNumber(amt1Input.value);
        hiddenAmount0.value = numericAmt1.toString();
        if (hiddenReceived0) {
            hiddenReceived0.value = numericAmt1.toString();
        }
    }

    const hiddenMethod1 = document.getElementById('payment-method-input-1');
    const hiddenAmount1 = document.getElementById('payment-amount-input-1');

    if (isSplitPayment) {
        const pm2Select = document.getElementById('payment_method_2');
        const amt2Input = document.getElementById('amount_received_2');

        if (hiddenMethod1) {
            hiddenMethod1.disabled = false;
            hiddenMethod1.value = pm2Select ? pm2Select.value : '';
        }
        if (hiddenAmount1) {
            hiddenAmount1.disabled = false;
            hiddenAmount1.value = amt2Input ? parseArToNumber(amt2Input.value).toString() : '0';
        }
    } else {
        if (hiddenMethod1) { hiddenMethod1.disabled = true; hiddenMethod1.value = ''; }
        if (hiddenAmount1) { hiddenAmount1.disabled = true; hiddenAmount1.value = ''; }
    }
}

// =====================================================
// FORMATTING UTILITIES
// =====================================================

/**
 * Formatea un número en estilo argentino con decimales:
 * 1000 -> "1.000,00", 1250.5 -> "1.250,50"
 */
function formatSmartAr(value) {
    if (value === null || value === undefined || isNaN(value)) return '0,00';
    const num = parseFloat(value);
    let [integerPart, decimalPart] = num.toFixed(2).split('.');
    integerPart = integerPart.replace(/\B(?=(\d{3})+(?!\d))/g, '.');
    return `${integerPart},${decimalPart}`;
}

/**
 * Formatea un número entero en estilo argentino (solo miles):
 * 1000 -> "1.000", 1550 -> "1.550"
 */
function formatIntegerAr(value) {
    if (value === null || value === undefined || isNaN(value)) return '0';
    const num = Math.round(parseFloat(value));
    if (num === 0) return '0';
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, '.');
}

/**
 * Convierte formato argentino a número:
 * "1.250,50" -> 1250.50
 */
function parseArToNumber(value) {
    if (!value || value === '') return 0;
    const cleaned = value.toString().replace(/\./g, '').replace(',', '.');
    return parseFloat(cleaned) || 0;
}
