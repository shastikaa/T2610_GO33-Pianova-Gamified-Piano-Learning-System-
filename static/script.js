const ctx = document.getElementById('chart');

new Chart(ctx, {
    type: 'line',
    data: {
        labels: ['Level 1', 'Level 2', 'Level 3', 'Level 4'],
        datasets: [{
            label: 'Students',
            data: [20, 40, 60, 80],
            borderColor: '#6c3cff',
            tension: 0.4
        }]
    },
    options: {
        plugins: {
            legend: {
                labels: { color: "white" }
            }
        },
        scales: {
            x: { ticks: { color: "white" } },
            y: { ticks: { color: "white" } }
        }
    }
});