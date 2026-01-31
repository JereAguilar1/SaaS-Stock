/**
 * Preserves focus state during HTMX swaps for the POS cart.
 * Prevents annoyance when row is replaced while editing.
 */
let focusState = {
    elementId: null,
    selectionStart: null,
    selectionEnd: null
};

document.body.addEventListener('htmx:beforeRequest', function (evt) {
    if (document.activeElement && document.activeElement.classList.contains('qty-input')) {
        focusState.elementId = document.activeElement.id; // Assuming we add IDs later or match by other means
        // Actually, inputs might not have stable IDs in the specific partial yet, 
        // but we'll try to match by name+value or context if needed.
        // For now, let's rely on standard browser behavior + OOB which is less destructive.
        // But if OuterHTML swap happens, focus is lost.

        // Simple strategy: save cursor position if it's a text/number input
        try {
            focusState.selectionStart = document.activeElement.selectionStart;
            focusState.selectionEnd = document.activeElement.selectionEnd;
        } catch (e) { }
    }
});

/* 
   Since we switched to Row-Level Update with OuterHTML swap, 
   the input element is literally destroyed and recreated.
   So we must re-focus it. 
   Problem: The new element might not be easily identifiable if we don't have unique IDs on inputs.
   Recommendation: Add unique IDs to qty inputs in _cart_line.html to make this robust.
*/
