"use strict";

(() => {
    const config = JSON.parse(document.getElementById("dashboard-config").textContent);
    const numberFormat = new Intl.NumberFormat("es-CO");
    const moneyFormat = new Intl.NumberFormat("es-CO", {
        style: "currency", currency: "COP", currencyDisplay: "code",
        minimumFractionDigits: 0, maximumFractionDigits: 2,
    });
    const percentFormat = new Intl.NumberFormat("es-CO", {
        style: "percent", maximumFractionDigits: 1,
    });
    const dateFormat = new Intl.DateTimeFormat("es-CO", {
        dateStyle: "medium", timeStyle: "medium",
    });
    const monthFormat = new Intl.DateTimeFormat("es-CO", {
        month: "short", year: "numeric", timeZone: "UTC",
    });
    const stateLabels = {
        PENDIENTE: "Pendiente", CONFIRMADA: "Confirmada", CANCELADA: "Cancelada",
    };
    const stateColors = {
        PENDIENTE: "#d99d43", CONFIRMADA: "#087c86", CANCELADA: "#a1adba",
    };
    const charts = new Map();
    const button = document.getElementById("actualizar");
    const report = document.getElementById("reporte");
    const status = document.getElementById("estado");
    const timestamp = document.getElementById("actualizado");
    const kpiIds = {
        destinos_registrados: "destinos", paquetes_activos: "paquetes",
        reservas_vigentes: "reservas", personas_reservadas: "personas",
        valor_confirmado: "valor",
    };
    const seriesIds = {
        reservas_por_mes: "meses", paquetes_mas_reservados: "paquetes",
        reservas_por_estado: "estados", valor_por_paquete: "valor",
        viajeros_por_destino: "destinos",
    };

    function monthLabel(value) {
        if (!/^\d{4}-(0[1-9]|1[0-2])$/.test(value)) return value;
        return monthFormat.format(new Date(`${value}-01T00:00:00Z`));
    }

    function validNumber(value, integer = false) {
        return typeof value === "number" && Number.isFinite(value)
            && value >= 0 && (!integer || Number.isSafeInteger(value));
    }

    function validatePayload(payload) {
        if (!payload || typeof payload !== "object" || !payload.kpis || !payload.series) {
            throw new Error("La API no devolvió un reporte con la estructura esperada.");
        }
        for (const key of Object.keys(kpiIds)) {
            if (!validNumber(payload.kpis[key], key !== "valor_confirmado")) {
                throw new Error("La API devolvió un indicador no válido.");
            }
        }
        for (const key of Object.keys(seriesIds)) {
            const rows = payload.series[key];
            if (!Array.isArray(rows) || rows.some((row) => !row
                || typeof row.label !== "string"
                || !validNumber(row.value, key !== "valor_por_paquete"))) {
                throw new Error("La API devolvió una serie de datos no válida.");
            }
        }
        const generatedAt = new Date(payload.meta?.generado_en);
        if (!payload.meta || payload.meta.moneda !== "COP"
            || typeof payload.meta.generado_en !== "string"
            || Number.isNaN(generatedAt.getTime())) {
            throw new Error("El reporte no incluye una fecha o moneda válida.");
        }
        return payload;
    }

    function setStatus(message, state) {
        status.textContent = message;
        status.className = `status status-${state}`;
    }

    function tableMessage(id, message) {
        const body = document.getElementById(`tabla-${id}`);
        const row = document.createElement("tr");
        const cell = document.createElement("td");
        cell.colSpan = id === "estados" ? 3 : 2;
        cell.textContent = message;
        row.append(cell);
        body.replaceChildren(row);
    }

    function clearReport(message) {
        for (const chart of charts.values()) chart.destroy();
        charts.clear();
        for (const id of Object.values(kpiIds)) {
            document.getElementById(`kpi-${id}`).textContent = "-";
        }
        for (const id of Object.values(seriesIds)) {
            document.getElementById(`grafica-${id}`).hidden = true;
            const empty = document.getElementById(`vacio-${id}`);
            empty.textContent = message;
            empty.hidden = false;
            document.getElementById(`historia-${id}`).textContent = message;
            tableMessage(id, message);
        }
        timestamp.textContent = "sin datos actualizados";
        timestamp.removeAttribute("datetime");
    }

    function tableRows(id, rows) {
        if (!rows.length) {
            tableMessage(id, "No hay registros para esta consulta.");
            return;
        }
        const fragment = document.createDocumentFragment();
        const total = rows.reduce((sum, row) => sum + row.value, 0);
        for (const item of rows) {
            const row = document.createElement("tr");
            let label = item.label;
            if (id === "meses") label = monthLabel(label);
            if (id === "estados") label = stateLabels[label] || label;
            const values = [label, id === "valor"
                ? moneyFormat.format(item.value) : numberFormat.format(item.value)];
            if (id === "estados") values.push(percentFormat.format(total ? item.value / total : 0));
            for (const value of values) {
                const cell = document.createElement("td");
                cell.textContent = value;
                row.append(cell);
            }
            fragment.append(row);
        }
        document.getElementById(`tabla-${id}`).replaceChildren(fragment);
    }

    function chartOptions({ horizontal = false, money = false, doughnut = false } = {}) {
        const options = {
            responsive: true,
            maintainAspectRatio: false,
            animation: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? false : { duration: 350 },
            color: "#536c7a",
            font: { family: '"Segoe UI", Arial, sans-serif' },
            plugins: {
                legend: { display: doughnut, position: "bottom", labels: { padding: 18, usePointStyle: true } },
                tooltip: {
                    backgroundColor: "#082f49", padding: 12,
                    callbacks: {
                        label(context) {
                            const amount = typeof context.raw === "number" ? context.raw : 0;
                            if (money) return moneyFormat.format(amount);
                            if (doughnut) {
                                const total = context.dataset.data.reduce((sum, value) => sum + value, 0);
                                return `${numberFormat.format(amount)} reservas (${percentFormat.format(total ? amount / total : 0)})`;
                            }
                            return `${context.dataset.label}: ${numberFormat.format(amount)}`;
                        },
                    },
                },
            },
        };
        if (doughnut) {
            options.cutout = "66%";
            return options;
        }
        options.indexAxis = horizontal ? "y" : "x";
        const valueAxis = horizontal ? "x" : "y";
        const labelAxis = horizontal ? "y" : "x";
        options.scales = {
            [valueAxis]: {
                beginAtZero: true,
                border: { display: false },
                grid: { color: "#eaf0f3" },
                ticks: money ? {
                    callback(value) {
                        return new Intl.NumberFormat("es-CO", { notation: "compact", maximumFractionDigits: 1 }).format(value);
                    },
                } : { precision: 0 },
                title: { display: true, text: money ? "Valor en COP" : "" },
            },
            [labelAxis]: {
                border: { display: false },
                grid: { display: false },
                ticks: { autoSkip: !horizontal, maxRotation: horizontal ? 0 : 25 },
            },
        };
        return options;
    }

    function drawChart(id, rows, configuration) {
        const canvas = document.getElementById(`grafica-${id}`);
        const empty = document.getElementById(`vacio-${id}`);
        tableRows(id, rows);
        if (!rows.length || rows.every((row) => row.value === 0)) {
            canvas.hidden = true;
            empty.hidden = false;
            empty.textContent = id === "valor"
                ? "No hay valor confirmado para comparar."
                : "No hay registros con valores mayores que cero en esta consulta.";
            return;
        }
        canvas.hidden = false;
        empty.hidden = true;
        charts.set(id, new Chart(canvas, configuration));
    }

    function leaderStory(rows, description, valueFormatter = numberFormat.format) {
        if (!rows.length || rows.every((row) => row.value === 0)) return "No hay valores mayores que cero para realizar esta comparación.";
        const highest = Math.max(...rows.map((row) => row.value));
        const leaders = rows.filter((row) => row.value === highest);
        const label = leaders[0].label;
        if (leaders.length > 1) {
            return `${label} y ${numberFormat.format(leaders.length - 1)} más comparten el mayor valor entre los resultados mostrados: ${valueFormatter(highest)} ${description}.`;
        }
        return `${label} presenta el mayor valor entre los resultados mostrados: ${valueFormatter(highest)} ${description}.`;
    }

    function writeStories(series) {
        const months = series.reservas_por_mes;
        let monthStory = "No hay reservas vigentes para construir la evolución mensual.";
        if (months.length) {
            const last = months[months.length - 1];
            monthStory = `${monthLabel(last.label)} es el último mes con datos de esta serie: ${numberFormat.format(last.value)} reservas vigentes.`;
            if (months.length > 1) {
                const previous = months[months.length - 2];
                const difference = last.value - previous.value;
                monthStory += difference === 0
                    ? " La cantidad es igual a la del mes anterior de la serie."
                    : ` Son ${numberFormat.format(Math.abs(difference))} ${difference > 0 ? "más" : "menos"} que en ${monthLabel(previous.label)}.`;
            }
        }
        document.getElementById("historia-meses").textContent = monthStory;
        document.getElementById("historia-paquetes").textContent = leaderStory(series.paquetes_mas_reservados, "reservas vigentes");
        const states = series.reservas_por_estado;
        const total = states.reduce((sum, row) => sum + row.value, 0);
        const confirmed = states.filter((row) => row.label === "CONFIRMADA").reduce((sum, row) => sum + row.value, 0);
        document.getElementById("historia-estados").textContent = total
            ? `De ${numberFormat.format(total)} reservas registradas, ${numberFormat.format(confirmed)} están confirmadas (${percentFormat.format(confirmed / total)} del total).`
            : "Aún no hay reservas registradas para calcular la distribución por estado.";
        document.getElementById("historia-valor").textContent = leaderStory(series.valor_por_paquete, "en reservas confirmadas", moneyFormat.format);
        document.getElementById("historia-destinos").textContent = leaderStory(series.viajeros_por_destino, "personas de reservas vigentes");
    }

    function renderReport(payload) {
        for (const [key, id] of Object.entries(kpiIds)) {
            document.getElementById(`kpi-${id}`).textContent = key === "valor_confirmado"
                ? moneyFormat.format(payload.kpis[key]) : numberFormat.format(payload.kpis[key]);
        }
        const series = payload.series;
        writeStories(series);
        const definitions = [
            ["meses", series.reservas_por_mes, "line", "Reservas", { tension: .2, fill: true, borderColor: "#087c86", backgroundColor: "#087c8618", pointBackgroundColor: "#087c86", pointRadius: 4, borderWidth: 2 }, {}],
            ["paquetes", series.paquetes_mas_reservados, "bar", "Reservas", { backgroundColor: "#087c86", borderRadius: 4, maxBarThickness: 34 }, { horizontal: true }],
            ["estados", series.reservas_por_estado, "doughnut", "Reservas", { backgroundColor: series.reservas_por_estado.map((row) => stateColors[row.label] || "#536c7a"), borderWidth: 3, borderColor: "white" }, { doughnut: true }],
            ["valor", series.valor_por_paquete, "bar", "Valor en COP", { backgroundColor: "#082f49", borderRadius: 4, maxBarThickness: 48 }, { money: true }],
            ["destinos", series.viajeros_por_destino, "bar", "Personas reservadas", { backgroundColor: "#4c9299", borderRadius: 4, maxBarThickness: 30 }, { horizontal: true }],
        ];
        for (const [id, rows, type, label, style, settings] of definitions) {
            drawChart(id, rows, {
                type,
                data: {
                    labels: rows.map((row) => id === "meses" ? monthLabel(row.label)
                        : id === "estados" ? (stateLabels[row.label] || row.label) : row.label),
                    datasets: [{ label, data: rows.map((row) => row.value), ...style }],
                },
                options: chartOptions(settings),
            });
        }
        timestamp.dateTime = payload.meta.generado_en;
        timestamp.textContent = dateFormat.format(new Date(payload.meta.generado_en));
    }

    async function loadReport() {
        if (button.disabled) return;
        button.disabled = true;
        button.textContent = "Actualizando...";
        report.setAttribute("aria-busy", "true");
        clearReport("Consultando la información...");
        setStatus("Consultando la información de la API...", "loading");
        const controller = new AbortController();
        const timeout = window.setTimeout(() => controller.abort(), 12000);
        try {
            if (typeof Chart === "undefined") {
                throw new Error("No se pudo cargar la biblioteca local de gráficas. Revisa el archivo chart.umd.min.js.");
            }
            const response = await fetch(config.reportUrl, {
                signal: controller.signal, cache: "no-store", headers: { Accept: "application/json" },
            });
            let payload;
            try {
                payload = await response.json();
            } catch (error) {
                if (error.name === "AbortError") throw error;
                throw new Error(`La API no respondió con JSON válido (HTTP ${response.status}).`);
            }
            if (!response.ok) {
                throw new Error(typeof payload.error === "string" ? payload.error : `La API respondió con HTTP ${response.status}.`);
            }
            renderReport(validatePayload(payload));
            const hasReservations = payload.series.reservas_por_estado.some((row) => row.value > 0);
            setStatus(hasReservations
                ? "Información actualizada. Los indicadores corresponden a los registros disponibles en la API."
                : "Información actualizada. Aún no hay reservas registradas; los indicadores y las tablas muestran el estado actual.", "success");
        } catch (error) {
            clearReport("No hay información actualizada disponible.");
            let message = error.message;
            if (error.name === "AbortError") message = "La API tardó más de 12 segundos en responder.";
            if (error instanceof TypeError) message = "No fue posible conectar con la API. Comprueba que el servidor del puerto 5000 esté funcionando.";
            setStatus(`No fue posible actualizar el tablero. ${message} Puedes volver a intentarlo con el botón Actualizar información.`, "error");
        } finally {
            window.clearTimeout(timeout);
            button.disabled = false;
            button.textContent = "Actualizar información";
            report.setAttribute("aria-busy", "false");
        }
    }

    button.addEventListener("click", loadReport);
    loadReport();
})();
