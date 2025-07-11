// Function to render a pie chart using Chart.js
function renderExpenseChart(labels, data) {
  const ctx = document.getElementById('expenseChart').getContext('2d');

  new Chart(ctx, {
    type: 'pie',
    data: {
      labels: labels,
      datasets: [{
        label: 'Expenses by Category',
        data: data,
        backgroundColor: [
          '#007bff', '#28a745', '#ffc107', '#dc3545',
          '#6f42c1', '#17a2b8', '#fd7e14', '#20c997'
        ],
        borderWidth: 1
      }]
    },
    options: {
      responsive: true,
      plugins: {
        legend: {
          position: 'bottom'
        },
        title: {
          display: true,
          text: 'Expenses by Category'
        }
      }
    }
  });
}
