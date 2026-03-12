function updateSummary() {
    fetch(`/private/api/booking/price/`)
        .then(r => r.json())
        .then(data => {
            document.getElementById("sum_services").innerText = "$" + data.services_total;
            document.getElementById("sum_addons").innerText = "$" + data.addons_total;
            document.getElementById("sum_total").innerText = "$" + data.final;
        })
        .catch(err => console.error("Error updating summary:", err));
}
