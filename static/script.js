const form = document.getElementById('gastoForm');
const tablaTotales = document.getElementById('tablaTotales');
const ctx = document.getElementById('graficoGastos').getContext('2d');
const totalSpan = document.getElementById('totalGastos');
let grafico;

// === Enviar gasto ===
form.addEventListener('submit', async (e) => {
    e.preventDefault();

    const data = {
        fecha: document.getElementById('fecha').value,
        categoria: document.getElementById('categoria').value,
        descripcion: document.getElementById('descripcion').value,
        monto: parseFloat(document.getElementById('monto').value)
    };

    const res = await fetch('/agregar_gasto', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    });

    const result = await res.json();
    alert(result.mensaje);
    form.reset();
    cargarReporte();
});

// === Cargar reporte ===
async function cargarReporte() {
    const res = await fetch('/reporte_mensual');
    const data = await res.json();

    if (!data.categorias || data.categorias.length === 0) {
        tablaTotales.innerHTML = '<tr><td colspan="2">Sin datos disponibles</td></tr>';
        if (grafico) grafico.destroy();
            totalSpan.textContent = '$0.00';
        return;
    }

    if (grafico) grafico.destroy();

    grafico = new Chart(ctx, {
        type: 'pie',
        data: {
            labels: data.categorias,
            datasets: [{
                data: data.montos,
                backgroundColor: ['#007bff', '#28a745', '#ffc107', '#dc3545', '#6c757d', '#6610f2', '#20c997']
            }]
        },
        options: {
            plugins: {
                legend: { position: 'bottom' },
                title: { display: true, text: 'Gastos por categoría' }
            }
        }
    });

    // Tabla de totales
    tablaTotales.innerHTML = '';
    data.categorias.forEach((cat, i) => {
        tablaTotales.innerHTML += `<tr>
        <td>${cat}</td>
        <td>$${data.montos[i].toFixed(2)}</td>
        </tr>`;
    });

    // Total general
    totalSpan.textContent = `$${data.total.toFixed(2)}`;
}

// Cargar al inicio
window.onload = cargarReporte;
