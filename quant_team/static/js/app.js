/* Quant Team Dashboard — shared utilities */

// Format helpers available globally
window.QT = {
    formatCurrency(n) {
        return '$' + (n || 0).toLocaleString(undefined, {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        });
    },
    formatPct(n) {
        return (n >= 0 ? '+' : '') + (n || 0).toFixed(2) + '%';
    },
};
