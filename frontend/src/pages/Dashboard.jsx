import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, CartesianGrid, Legend } from "recharts";
import client from "../api/client";

const COLORS = ["#185FA5", "#0F6E56", "#854F0B", "#534AB7", "#993C1D", "#1A7F64"];
const CHART_RANGES = ["1D", "1W", "1M", "3M", "YTD", "1Y", "ALL"];
const TICKER_CURRENCY_SUFFIX = {
    ".US": "USD",
    ".DE": "EUR",
    ".UK": "USD",
    ".L": "GBP",
    ".PL": "PLN",
    ".WA": "PLN",
};

function formatDate(dateValue) {
    return dateValue.toISOString().slice(0, 10);
}

function getChartDateFrom(range, history) {
    const today = new Date();
    const start = new Date(today);

    if (range === "ALL") {
        if (history.length === 0) return formatDate(today);
        const oldestTransaction = history.reduce((oldest, tx) => {
            const txDate = new Date(tx.executed_at);
            return txDate < oldest ? txDate : oldest;
        }, new Date(history[0].executed_at));
        return formatDate(oldestTransaction);
    }

    if (range === "YTD") return `${today.getFullYear()}-01-01`;
    if (range === "1D") start.setDate(start.getDate() - 1);
    if (range === "1W") start.setDate(start.getDate() - 7);
    if (range === "1M") start.setMonth(start.getMonth() - 1);
    if (range === "3M") start.setMonth(start.getMonth() - 3);
    if (range === "1Y") start.setFullYear(start.getFullYear() - 1);

    return formatDate(start);
}

function inferDisplayCurrency(ticker, fallbackCurrency) {
    const symbol = String(ticker || "").toUpperCase();
    for (const [suffix, currency] of Object.entries(TICKER_CURRENCY_SUFFIX)) {
        if (symbol.endsWith(suffix)) return currency;
    }
    return fallbackCurrency || "PLN";
}

function Dashboard({ onLogout }) {
    const [portfolios, setPortfolios] = useState([]);
    const [chartData, setChartData] = useState([]);
    const [transactions, setTransactions] = useState([]);
    const [selectedPortfolio, setSelectedPortfolio] = useState(null);
    const [loading, setLoading] = useState(false);
    const [submittingTransaction, setSubmittingTransaction] = useState(false);
    const [historyError, setHistoryError] = useState("");
    const [importingXtb, setImportingXtb] = useState(false);
    const [importFile, setImportFile] = useState(null);
    const [importMessage, setImportMessage] = useState("");
    const [activeTab, setActiveTab] = useState("portfel");
    const [selectedRange, setSelectedRange] = useState("ALL");
    const [newTransaction, setNewTransaction] = useState({
        type: "BUY",
        ticker: "",
        quantity: "",
        price: "",
        commission: "",
        currency: "PLN",
        executed_at: new Date().toISOString().slice(0, 10),
    });
    const navigate = useNavigate();

    const fetchPortfolioData = useCallback(async (portfolioId, range) => {
        setLoading(true);
        setHistoryError("");
        try {
            const txRes = await client.get(`/portfolios/${portfolioId}/history`);
            const dateTo = formatDate(new Date());
            const dateFrom = getChartDateFrom(range, txRes.data);
            const chartRes = await client.get(`/portfolios/${portfolioId}/chart?date_from=${dateFrom}&date_to=${dateTo}`);
            setChartData(chartRes.data);
            setTransactions(txRes.data);
        } catch {
            setHistoryError("Nie udało się pobrać danych portfela.");
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        client.get("/portfolios")
            .then(res => {
                setPortfolios(res.data);
                if (res.data.length > 0) {
                    const initialPortfolioId = String(res.data[0].id);
                    setSelectedPortfolio(initialPortfolioId);
                    fetchPortfolioData(initialPortfolioId, "ALL");
                }
            })
            .catch(() => navigate("/login"));
    }, [navigate, fetchPortfolioData]);

    function handlePortfolioChange(portfolioId) {
        setSelectedPortfolio(portfolioId);
        fetchPortfolioData(portfolioId, selectedRange);
    }

    function handleRangeChange(range) {
        setSelectedRange(range);
        if (!selectedPortfolio) return;
        fetchPortfolioData(selectedPortfolio, range);
    }

    function handleLogout() {
        localStorage.removeItem("token");
        onLogout?.();
        navigate("/login");
    }

    function updateNewTransaction(field, value) {
        setNewTransaction((prev) => ({ ...prev, [field]: value }));
    }

    function parseDecimal(value) {
        return Number(String(value).replace(",", ".").trim());
    }

    async function handleAddTransaction(event) {
        event.preventDefault();
        if (!selectedPortfolio) return;

        setSubmittingTransaction(true);
        setHistoryError("");
        try {
            const quantity = parseDecimal(newTransaction.quantity);
            const price = parseDecimal(newTransaction.price);
            const commissionValue = parseDecimal(newTransaction.commission || 0);

            if (!Number.isFinite(quantity) || quantity <= 0) {
                setHistoryError("Ilość musi być dodatnią liczbą.");
                return;
            }
            if (!Number.isFinite(price) || price <= 0) {
                setHistoryError("Cena musi być dodatnią liczbą.");
                return;
            }
            if (!Number.isFinite(commissionValue) || commissionValue < 0) {
                setHistoryError("Prowizja nie może być ujemna.");
                return;
            }

            await client.post("/transactions", {
                portfolio_id: Number(selectedPortfolio),
                type: newTransaction.type,
                ticker: newTransaction.ticker.trim().toUpperCase(),
                quantity,
                price,
                commission: commissionValue,
                currency: newTransaction.currency.trim().toUpperCase() || "PLN",
                executed_at: `${newTransaction.executed_at}T12:00:00`,
            });
            setNewTransaction((prev) => ({
                ...prev,
                ticker: "",
                quantity: "",
                price: "",
                commission: "",
            }));
            await fetchPortfolioData(selectedPortfolio, selectedRange);
        } catch {
            setHistoryError("Nie udało się dodać transakcji. Sprawdź dane formularza.");
        } finally {
            setSubmittingTransaction(false);
        }
    }

    async function handleDeleteTransaction(transactionId) {
        if (!selectedPortfolio) return;
        setHistoryError("");
        try {
            await client.delete(`/transactions/${transactionId}`);
            await fetchPortfolioData(selectedPortfolio, selectedRange);
        } catch {
            setHistoryError("Nie udało się usunąć transakcji.");
        }
    }

    async function handleImportXtb() {
        if (!selectedPortfolio || !importFile) {
            setImportMessage("Wybierz plik .xlsx do importu.");
            return;
        }

        setImportingXtb(true);
        setImportMessage("");
        setHistoryError("");
        try {
            const formData = new FormData();
            formData.append("file", importFile);
            const res = await client.post(`/transactions/import/xtb?portfolio_id=${selectedPortfolio}`, formData, {
                headers: { "Content-Type": "multipart/form-data" },
            });
            const { imported, skipped, errors } = res.data;
            const errorsInfo = Array.isArray(errors) && errors.length > 0 ? ` Błędy: ${errors.length}.` : "";
            setImportMessage(`Import zakończony. Dodano: ${imported}, pominięto: ${skipped}.${errorsInfo}`);
            setImportFile(null);
            await fetchPortfolioData(selectedPortfolio, selectedRange);
        } catch (error) {
            const detail = error?.response?.data?.detail;
            setImportMessage(typeof detail === "string" ? detail : "Nie udało się zaimportować pliku XTB.");
        } finally {
            setImportingXtb(false);
        }
    }

    const positions = {};
    transactions.forEach(t => {
        if (t.type === "BUY") positions[t.ticker] = (positions[t.ticker] || 0) + t.quantity;
        if (t.type === "SELL") positions[t.ticker] = (positions[t.ticker] || 0) - t.quantity;
    });
    const pieData = Object.entries(positions)
        .filter(([, qty]) => qty > 0)
        .map(([ticker, qty]) => ({ name: ticker, value: qty }));
    const historyRows = [...transactions].sort(
        (a, b) => new Date(b.executed_at) - new Date(a.executed_at)
    );

    const lastValue = chartData.length > 0 ? Number(chartData[chartData.length - 1].value || 0) : 0;
    const lastInvested = chartData.length > 0 ? Number(chartData[chartData.length - 1].invested || 0) : 0;
    const change = lastValue - lastInvested;
    const changePct = lastInvested > 0 ? ((change / lastInvested) * 100).toFixed(2) : 0;

    const tabStyle = (tab) => ({
        display: "flex",
        alignItems: "center",
        gap: 10,
        padding: "11px 16px",
        borderRadius: 12,
        cursor: "pointer",
        fontSize: 14,
        fontWeight: activeTab === tab ? 600 : 400,
        background: activeTab === tab ? "rgba(130, 144, 255, 0.18)" : "transparent",
        color: activeTab === tab ? "#f7f8ff" : "#b8bfd9",
        border: activeTab === tab ? "1px solid rgba(156, 167, 255, 0.35)" : "1px solid transparent",
        boxShadow: activeTab === tab ? "inset 0 0 0 1px rgba(255,255,255,0.04), 0 8px 18px rgba(8,10,28,0.28)" : "none",
        width: "100%",
        textAlign: "left",
        transition: "all 0.2s ease",
    });
    const formControlStyle = {
        padding: "7px 10px",
        borderRadius: 8,
        border: "1px solid #d8dde6",
        height: 36,
        minHeight: 36,
        maxHeight: 36,
        boxSizing: "border-box",
        lineHeight: "20px",
        background: "#fff",
        color: "#25304a",
        fontSize: 13,
        display: "block",
        width: "100%",
    };

    return (
        <div style={{ display: "flex", minHeight: "100vh", fontFamily: "sans-serif", background: "#f3f5f8" }}>

            {/* SIDEBAR */}
            <div style={{ width: 236, background: "linear-gradient(180deg, #171a34 0%, #1d2040 100%)", color: "#fff", padding: "24px 12px", display: "flex", flexDirection: "column", gap: 8, flexShrink: 0, borderRadius: 20, margin: "10px 0 10px 10px", border: "1px solid rgba(120, 133, 204, 0.18)" }}>

                <div style={{ fontSize: 16, fontWeight: 700, color: "#f5f7ff", padding: "0 8px", marginBottom: 24 }}>
                    Portfolio Tracker
                </div>

                <div style={{ fontSize: 11, color: "#7f88ad", textTransform: "uppercase", letterSpacing: "0.08em", padding: "0 8px", marginBottom: 4 }}>Menu</div>

                <button style={tabStyle("portfel")} onClick={() => setActiveTab("portfel")}>
                    Portfel
                </button>

                <button style={tabStyle("zarzadzanie")} onClick={() => setActiveTab("zarzadzanie")}>
                    Zarządzanie
                </button>

            </div>

            {/* RIGHT PANEL */}
            <div style={{ flex: 1, display: "flex", flexDirection: "column" }}>

                {/* TOP BAR */}
                <div style={{ height: 56, background: "#fcfcfd", borderBottom: "1px solid #e8ebf0", display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0 24px", flexShrink: 0 }}>

                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <span style={{ fontSize: 13, color: "#888" }}>Portfel:</span>
                        <select
                            value={selectedPortfolio || ""}
                            onChange={e => handlePortfolioChange(e.target.value)}
                            style={{ padding: "6px 10px", borderRadius: 8, border: "1px solid #d8dde6", fontSize: 13, background: "#fdfdfe", cursor: "pointer" }}
                        >
                            {portfolios.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
                        </select>
                    </div>

                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <button
                            onClick={() => setActiveTab("ustawienia")}
                            style={{ padding: "6px 14px", borderRadius: 8, border: "1px solid #d8dde6", background: "#fdfdfe", cursor: "pointer", fontSize: 13, display: "flex", alignItems: "center", gap: 6 }}
                        >
                            Ustawienia
                        </button>
                        <button
                            onClick={handleLogout}
                            style={{ padding: "6px 14px", borderRadius: 8, border: "none", background: "#a84a2a", color: "#fff", cursor: "pointer", fontSize: 13 }}
                        >
                            Wyloguj
                        </button>
                    </div>

                </div>

                {/* CONTENT */}
                <div style={{ flex: 1, padding: 24, display: "flex", flexDirection: "column", gap: 24, overflowY: "auto" }}>

                    {/* TAB: PORTFEL */}
                    {activeTab === "portfel" && (
                        <>
                            {/* METRYKI */}
                            <div style={{ display: "flex", gap: 16 }}>
                                {[
                                    { label: "Wartość portfela", value: `${lastValue.toLocaleString()} PLN` },
                                        { label: "Wpłacono", value: `${lastInvested.toLocaleString()} PLN` },
                                    { label: "Zmiana", value: `${change >= 0 ? "+" : ""}${change.toFixed(2)} PLN`, color: change >= 0 ? "#4caf50" : "#f44336" },
                                    { label: "Stopa zwrotu", value: `${changePct}%`, color: change >= 0 ? "#4caf50" : "#f44336" },
                                    { label: "Pozycje", value: pieData.length },
                                ].map((m, i) => (
                                    <div key={i} style={{ flex: 1, background: "#fcfcfd", borderRadius: 14, padding: "16px 20px", boxShadow: "0 6px 18px rgba(18, 25, 40, 0.06)" }}>
                                        <div style={{ fontSize: 11, color: "#888", marginBottom: 6 }}>{m.label}</div>
                                        <div style={{ fontSize: 20, fontWeight: 600, color: m.color || "#1a1a2e" }}>{m.value}</div>
                                    </div>
                                ))}
                            </div>

                            {/* WYKRES */}
                            <div style={{ background: "#fcfcfd", borderRadius: 14, padding: 24, boxShadow: "0 6px 18px rgba(18, 25, 40, 0.06)" }}>
                                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, marginBottom: 16 }}>
                                    <h3 style={{ margin: 0, fontSize: 15 }}>Wartość portfela</h3>
                                    <div style={{ display: "flex", gap: 6, flexWrap: "wrap", justifyContent: "flex-end" }}>
                                        {CHART_RANGES.map((range) => (
                                            <button
                                                key={range}
                                                onClick={() => handleRangeChange(range)}
                                                style={{
                                                    border: "none",
                                                    background: "transparent",
                                                    color: selectedRange === range ? "#185FA5" : "#6c748b",
                                                    borderBottom: selectedRange === range ? "2px solid #185FA5" : "2px solid transparent",
                                                    fontSize: 12,
                                                    fontWeight: selectedRange === range ? 700 : 600,
                                                    cursor: "pointer",
                                                    padding: "3px 2px",
                                                    minWidth: 28,
                                                }}
                                            >
                                                {range}
                                            </button>
                                        ))}
                                    </div>
                                </div>
                                {loading && <p style={{ color: "#888" }}>Ładowanie...</p>}
                                {!loading && chartData.length === 0 && <p style={{ color: "#888" }}>Brak danych — dodaj transakcje.</p>}
                                {!loading && chartData.length > 0 && (
                                    <ResponsiveContainer width="100%" height={300}>
                                        <LineChart data={chartData} margin={{ top: 10, right: 20, bottom: 60, left: 20 }}>
                                            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                                            <XAxis dataKey="date" tick={{ fontSize: 10, fill: "#888" }} interval={9} angle={-45} textAnchor="end" height={60} />
                                            <YAxis tickFormatter={v => v.toLocaleString()} tick={{ fontSize: 11, fill: "#888" }} axisLine={false} tickLine={false} width={80} />
                                            <Tooltip formatter={(v, n) => [`${Number(v).toLocaleString()} PLN`, n === "value" ? "Wartość" : "Wpłacono"]} contentStyle={{ borderRadius: 8, border: "none", boxShadow: "0 2px 8px rgba(0,0,0,0.1)" }} />
                                            <Legend />
                                            <Line type="monotone" dataKey="value" stroke="#185FA5" name="Wartość" dot={false} strokeWidth={2} activeDot={{ r: 4 }} />
                                            <Line type="monotone" dataKey="invested" stroke="#7a8197" name="Wpłacono" dot={false} strokeWidth={2} strokeDasharray="5 5" />
                                        </LineChart>
                                    </ResponsiveContainer>
                                )}
                            </div>

                            {/* STRUKTURA */}
                            <div style={{ background: "#fcfcfd", borderRadius: 14, padding: 24, boxShadow: "0 6px 18px rgba(18, 25, 40, 0.06)", display: "flex", gap: 32 }}>
                                <div style={{ flex: 1 }}>
                                    <h3 style={{ margin: "0 0 16px 0", fontSize: 15 }}>Struktura portfela</h3>
                                    {pieData.length === 0 && <p style={{ color: "#888" }}>Brak pozycji.</p>}
                                    {pieData.length > 0 && (
                                        <ResponsiveContainer width="100%" height={200}>
                                            <PieChart>
                                                <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label={({ name }) => name}>
                                                    {pieData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                                                </Pie>
                                                <Tooltip />
                                            </PieChart>
                                        </ResponsiveContainer>
                                    )}
                                </div>
                                <div style={{ flex: 1 }}>
                                    <h3 style={{ margin: "0 0 16px 0", fontSize: 15 }}>Pozycje</h3>
                                    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
                                        <thead>
                                            <tr style={{ borderBottom: "1px solid #eee" }}>
                                                <th style={{ textAlign: "left", padding: "4px 8px", color: "#888", fontWeight: 500 }}>Ticker</th>
                                                <th style={{ textAlign: "right", padding: "4px 8px", color: "#888", fontWeight: 500 }}>Ilość</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {pieData.map((p, i) => (
                                                <tr key={i} style={{ borderBottom: "1px solid #f5f5f5" }}>
                                                    <td style={{ padding: "8px 8px", fontWeight: 500 }}>{p.name}</td>
                                                    <td style={{ padding: "8px 8px", textAlign: "right" }}>{p.value}</td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        </>
                    )}

                    {/* TAB: ZARZĄDZANIE */}
                    {activeTab === "zarzadzanie" && (
                        <div style={{ background: "#fcfcfd", borderRadius: 14, padding: 24, boxShadow: "0 6px 18px rgba(18, 25, 40, 0.06)" }}>
                            <h3 style={{ margin: "0 0 16px 0", fontSize: 15 }}>Historia transakcji</h3>
                            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14, flexWrap: "wrap" }}>
                                <input
                                    type="file"
                                    accept=".xlsx"
                                    onChange={(e) => setImportFile(e.target.files?.[0] || null)}
                                    style={{ fontSize: 13 }}
                                />
                                <button
                                    type="button"
                                    onClick={handleImportXtb}
                                    disabled={importingXtb}
                                    style={{ padding: "7px 12px", borderRadius: 8, border: "1px solid #d8dde6", background: "#fff", color: "#25304a", cursor: "pointer", fontWeight: 600, height: 36 }}
                                >
                                    {importingXtb ? "Importowanie..." : "Importuj XTB (.xlsx)"}
                                </button>
                            </div>
                            {importMessage && <p style={{ color: "#4a556f", marginBottom: 12 }}>{importMessage}</p>}
                            <form onSubmit={handleAddTransaction} style={{ display: "grid", gridTemplateColumns: "96px 120px 120px 120px 120px 94px 130px auto", gap: 8, marginBottom: 16, alignItems: "center", justifyContent: "start" }}>
                                <select
                                    value={newTransaction.type}
                                    onChange={(e) => updateNewTransaction("type", e.target.value)}
                                    style={formControlStyle}
                                >
                                    <option value="BUY">BUY</option>
                                    <option value="SELL">SELL</option>
                                </select>
                                <input
                                    value={newTransaction.ticker}
                                    onChange={(e) => updateNewTransaction("ticker", e.target.value)}
                                    placeholder="Ticker"
                                    required
                                    style={formControlStyle}
                                />
                                <input
                                    type="text"
                                    inputMode="decimal"
                                    value={newTransaction.quantity}
                                    onChange={(e) => updateNewTransaction("quantity", e.target.value)}
                                    placeholder="Ilość"
                                    required
                                    style={formControlStyle}
                                />
                                <input
                                    type="text"
                                    inputMode="decimal"
                                    value={newTransaction.price}
                                    onChange={(e) => updateNewTransaction("price", e.target.value)}
                                    placeholder="Cena"
                                    required
                                    style={formControlStyle}
                                />
                                <input
                                    type="text"
                                    inputMode="decimal"
                                    value={newTransaction.commission}
                                    onChange={(e) => updateNewTransaction("commission", e.target.value)}
                                    placeholder="Prowizja"
                                    style={formControlStyle}
                                />
                                <select
                                    value={newTransaction.currency}
                                    onChange={(e) => updateNewTransaction("currency", e.target.value)}
                                    style={formControlStyle}
                                >
                                    <option value="PLN">PLN</option>
                                    <option value="USD">USD</option>
                                    <option value="EUR">EUR</option>
                                    <option value="GBP">GBP</option>
                                    <option value="CHF">CHF</option>
                                </select>
                                <input
                                    type="date"
                                    value={newTransaction.executed_at}
                                    onChange={(e) => updateNewTransaction("executed_at", e.target.value)}
                                    required
                                    style={{ ...formControlStyle, paddingRight: 8 }}
                                />
                                <div style={{ display: "flex", alignItems: "center" }}>
                                    <button
                                        type="submit"
                                        disabled={submittingTransaction}
                                        style={{ padding: "7px 12px", borderRadius: 8, border: "none", background: "#185FA5", color: "#fff", cursor: "pointer", fontWeight: 600, height: 36, minHeight: 36, maxHeight: 36, boxSizing: "border-box", whiteSpace: "nowrap", fontSize: 13 }}
                                    >
                                        {submittingTransaction ? "Dodawanie..." : "Dodaj transakcję"}
                                    </button>
                                </div>
                            </form>
                            {historyError && <p style={{ color: "#b3261e", marginBottom: 12 }}>{historyError}</p>}
                            {historyRows.length === 0 && (
                                <p style={{ color: "#888" }}>Brak transakcji dla wybranego portfela.</p>
                            )}
                            {historyRows.length > 0 && (
                                <div style={{ overflowX: "auto" }}>
                                    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13, minWidth: 780 }}>
                                        <thead>
                                            <tr style={{ borderBottom: "1px solid #e8ebf0" }}>
                                                <th style={{ textAlign: "left", padding: "8px 10px", color: "#7a8197", fontWeight: 600 }}>Data</th>
                                                <th style={{ textAlign: "left", padding: "8px 10px", color: "#7a8197", fontWeight: 600 }}>Operacja</th>
                                                <th style={{ textAlign: "left", padding: "8px 10px", color: "#7a8197", fontWeight: 600 }}>Ticker</th>
                                                <th style={{ textAlign: "right", padding: "8px 10px", color: "#7a8197", fontWeight: 600 }}>Ilość</th>
                                                <th style={{ textAlign: "right", padding: "8px 10px", color: "#7a8197", fontWeight: 600 }}>Cena</th>
                                                <th style={{ textAlign: "right", padding: "8px 10px", color: "#7a8197", fontWeight: 600 }}>Prowizja</th>
                                                <th style={{ textAlign: "right", padding: "8px 10px", color: "#7a8197", fontWeight: 600 }}>Wartość</th>
                                                <th style={{ textAlign: "right", padding: "8px 10px", color: "#7a8197", fontWeight: 600 }}>Akcje</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {historyRows.map((tx) => {
                                                const displayCurrency = tx.ticker === "CASH"
                                                    ? "PLN"
                                                    : inferDisplayCurrency(tx.ticker, tx.currency);
                                                return (
                                                <tr key={tx.id} style={{ borderBottom: "1px solid #f0f2f6" }}>
                                                    <td style={{ padding: "9px 10px", color: "#25304a" }}>{new Date(tx.executed_at).toLocaleDateString("pl-PL")}</td>
                                                    <td style={{ padding: "9px 10px", fontWeight: 600, color: tx.type === "BUY" ? "#0F6E56" : "#993C1D" }}>{tx.type}</td>
                                                    <td style={{ padding: "9px 10px", color: "#25304a", fontWeight: 500 }}>{tx.ticker}</td>
                                                    <td style={{ padding: "9px 10px", textAlign: "right", color: "#25304a" }}>{Number(tx.quantity).toLocaleString()}</td>
                                                    <td style={{ padding: "9px 10px", textAlign: "right", color: "#25304a" }}>
                                                        {Number(tx.price).toLocaleString()} {displayCurrency}
                                                    </td>
                                                    <td style={{ padding: "9px 10px", textAlign: "right", color: "#25304a" }}>
                                                        {Number(tx.commission).toLocaleString()} {displayCurrency}
                                                    </td>
                                                    <td style={{ padding: "9px 10px", textAlign: "right", color: "#25304a", fontWeight: 600 }}>
                                                        {(Number(tx.price) * Number(tx.quantity) + Number(tx.commission)).toLocaleString()} {displayCurrency}
                                                    </td>
                                                    <td style={{ padding: "9px 10px", textAlign: "right" }}>
                                                        <button
                                                            onClick={() => handleDeleteTransaction(tx.id)}
                                                            style={{ padding: "5px 10px", borderRadius: 8, border: "1px solid #e1c6c1", background: "#fff5f3", color: "#993C1D", cursor: "pointer", fontSize: 12, fontWeight: 600 }}
                                                        >
                                                            Usuń
                                                        </button>
                                                    </td>
                                                </tr>
                                                );
                                            })}
                                        </tbody>
                                    </table>
                                </div>
                            )}
                        </div>
                    )}

                    {/* TAB: USTAWIENIA */}
                    {activeTab === "ustawienia" && (
                        <div style={{ background: "#fcfcfd", borderRadius: 14, padding: 24, boxShadow: "0 6px 18px rgba(18, 25, 40, 0.06)" }}>
                            <h3 style={{ margin: "0 0 16px 0", fontSize: 15 }}>Ustawienia konta</h3>
                            <p style={{ color: "#888" }}>Tu pojawią się ustawienia konta i aplikacji.</p>
                        </div>
                    )}

                </div>
            </div>
        </div>
    );
}

export default Dashboard;