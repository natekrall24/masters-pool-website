const SALARY_CAP = 50000;
const MAX_PICKS = 6;

const slots = Array.from({ length: MAX_PICKS }, (_, i) => document.getElementById(`slot-${i}`));
const totalSalaryEl = document.getElementById("total-salary");
const remainingSalaryEl = document.getElementById("remaining-salary");
const submitBtn = document.getElementById("submit-btn");
const submitHint = document.getElementById("submit-hint");
const nameInput = document.getElementById("name");
const emailInput = document.getElementById("email");
const venmoCheckbox = document.getElementById("venmo-checkbox");
const searchInput = document.getElementById("player-search");

function getChecked() {
    return Array.from(document.querySelectorAll(".player-checkbox:checked"));
}

function formatSalary(n) {
    return "$" + n.toLocaleString();
}

function updateSummary() {
    const checked = getChecked();
    const totalSalary = checked.reduce((sum, cb) => sum + parseInt(cb.closest("tr").dataset.salary), 0);
    const remaining = SALARY_CAP - totalSalary;
    const count = checked.length;

    // Update salary displays
    totalSalaryEl.textContent = formatSalary(totalSalary);
    remainingSalaryEl.textContent = formatSalary(remaining);
    remainingSalaryEl.style.color = remaining < 0 ? "#c0392b" : "";
    totalSalaryEl.style.color = totalSalary > SALARY_CAP ? "#c0392b" : "";

    // Update roster slots
    slots.forEach((slot, i) => {
        const cb = checked[i];
        if (cb) {
            const name = cb.closest("tr").dataset.name;
            const salary = parseInt(cb.closest("tr").dataset.salary);
            slot.textContent = `${name} — ${formatSalary(salary)}`;
            slot.classList.remove("empty");
        } else {
            slot.textContent = "— Empty —";
            slot.classList.add("empty");
        }
    });

    // Lock/unlock checkboxes
    document.querySelectorAll(".player-checkbox").forEach(cb => {
        const row = cb.closest("tr");
        const salary = parseInt(row.dataset.salary);

        if (!cb.checked) {
            const wouldExceedCap = (totalSalary + salary) > SALARY_CAP;
            const atMaxPicks = count >= MAX_PICKS;
            cb.disabled = atMaxPicks || wouldExceedCap;
            row.classList.toggle("disabled", cb.disabled);
        } else {
            cb.disabled = false;
            row.classList.remove("disabled");
        }
    });

    updateHandleBar(count, totalSalary);
    updateSubmitButton(count, totalSalary);
}

function updateSubmitButton(count, totalSalary) {
    const name = nameInput.value.trim();
    const email = emailInput.value.trim();
    const venmo = venmoCheckbox.checked;

    const reasons = [];
    if (count !== MAX_PICKS) reasons.push(`Select ${MAX_PICKS - count} more player${MAX_PICKS - count !== 1 ? "s" : ""}`);
    if (totalSalary > SALARY_CAP) reasons.push("Over salary cap");
    if (!name) reasons.push("Enter your name");
    if (!email) reasons.push("Enter your email");
    if (!venmo) reasons.push("Confirm Venmo payment");

    const ready = reasons.length === 0;
    submitBtn.disabled = !ready;
    submitHint.textContent = ready ? "" : reasons.join(" · ");
}

// Player checkbox interactions
document.querySelectorAll(".player-checkbox").forEach(cb => {
    cb.addEventListener("change", updateSummary);
});

// Form field interactions
[nameInput, emailInput].forEach(el => {
    el.addEventListener("input", () => updateSubmitButton(getChecked().length,
        getChecked().reduce((sum, cb) => sum + parseInt(cb.closest("tr").dataset.salary), 0)));
});
venmoCheckbox.addEventListener("change", () => updateSubmitButton(getChecked().length,
    getChecked().reduce((sum, cb) => sum + parseInt(cb.closest("tr").dataset.salary), 0)));

// Search/filter
searchInput.addEventListener("input", () => {
    const query = searchInput.value.toLowerCase();
    document.querySelectorAll(".player-row").forEach(row => {
        const name = row.dataset.name.toLowerCase();
        row.style.display = name.includes(query) ? "" : "none";
    });
});

// Mobile drawer
const teamSummary = document.getElementById("team-summary");
const drawerHandle = document.getElementById("drawer-handle");
const handleCount = document.getElementById("handle-count");
const handleBudget = document.getElementById("handle-budget");

drawerHandle.addEventListener("click", () => {
    teamSummary.classList.toggle("expanded");
});

function updateHandleBar(count, totalSalary) {
    if (!handleCount) return;
    const remaining = SALARY_CAP - totalSalary;
    handleCount.textContent = `${count}/6`;
    handleBudget.textContent = `${formatSalary(remaining)} left`;
    handleBudget.style.color = remaining < 0 ? "#c0392b" : "";

    // Auto-expand when 6 players are selected
    if (count === MAX_PICKS && !teamSummary.classList.contains("expanded")) {
        teamSummary.classList.add("expanded");
    }
}

// Initialize on page load (handles pre-filled state if form errored)
updateSummary();
