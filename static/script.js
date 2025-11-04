const form = document.getElementById('gastoForm');
const tablaTotales = document.getElementById('tablaTotales');
const ctx = document.getElementById('graficoGastos').getContext('2d');
let grafico;

document.getElementById('btnFiltrar').addEventListener('click', () => {
  cargarReporte(); // Usa la función que ya tienes
});

// Enviar gasto
form.addEventListener('submit', async (e) => {
    e.preventDefault();

    const data = {
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

// Cargar reporte (con filtro de mes)
async function cargarReporte() {
    const mesSeleccionado = document.getElementById('mes')?.value;
    let url = '/reporte_mensual';
    if (mesSeleccionado) url += `?mes=${mesSeleccionado}`;

    const res = await fetch(url);
    const data = await res.json();

    if (!data.reporte || data.reporte.length === 0) {
        tablaTotales.innerHTML = "<tr><td colspan='2'>No hay datos para este mes</td></tr>";
        if (grafico) grafico.destroy();
        return;
    }

    const categorias = data.reporte.map(r => r.Categoría);
    const montos = data.reporte.map(r => r.Monto);

    if (grafico) grafico.destroy();

    grafico = new Chart(ctx, {
        type: 'pie',
        data: {
            labels: categorias,
            datasets: [{
                data: montos,
                backgroundColor: ['#007bff','#28a745','#ffc107','#dc3545','#6c757d']
            }]
        }
    });

    tablaTotales.innerHTML = '';
    categorias.forEach((cat, i) => {
        tablaTotales.innerHTML += `<tr><td>${cat}</td><td>$${montos[i].toFixed(2)}</td></tr>`;
    });
}

window.onload = cargarReporte;
