// Click a <th> of any table.sortable to sort by that column. Numeric-aware.
document.querySelectorAll("table.sortable th").forEach((th, i) => {
  th.addEventListener("click", () => {
    const tbody = th.closest("table").querySelector("tbody");
    const dir = th.dataset.dir === "asc" ? -1 : 1;
    th.closest("tr").querySelectorAll("th").forEach(h => delete h.dataset.dir);
    th.dataset.dir = dir === 1 ? "asc" : "desc";
    const val = tr => tr.children[i].dataset.sort ?? tr.children[i].textContent.trim();
    const num = s => s !== "" && !isNaN(s.replace(/,/g, ""));
    [...tbody.rows]
      .sort((a, b) => {
        const [x, y] = [val(a), val(b)];
        return (num(x) && num(y)
          ? parseFloat(x.replace(/,/g, "")) - parseFloat(y.replace(/,/g, ""))
          : x.localeCompare(y)) * dir;
      })
      .forEach(tr => tbody.appendChild(tr));
  });
});
