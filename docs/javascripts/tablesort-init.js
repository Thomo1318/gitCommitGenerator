document$.subscribe(function() {
  if (typeof Tablesort === "function") {
    var tables = document.querySelectorAll("article table:not([class])")
    tables.forEach(function(table) {
      new Tablesort(table)
    })
  } else {
    console.warn("Tablesort is not loaded. Skipping table sort initialization.")
  }
})
