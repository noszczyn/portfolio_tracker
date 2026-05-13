import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, CartesianGrid } from "recharts";
import client from "../api/client";

const COLORS = ["#185FA5", "#0F6E56", "#854F0B", "#534AB7", "#993C1D", "#1A7F64"];

function Dashboard({ onLogout }) {
    const [portfolios, setPortfolios] = useState([]);
    const [chartData, setChartData] = useState([]);
    const [transactions, setTransactions] = useState([]);
    const [selectedPortfolio, setSelectedPortfolio] = useState(null);
    const [loading, setLoading] = useState(false);
    const [activeTab, setActiveTab] = useState("portfel");
    const navigate = useNavigate();

    useEffect(() => {
        client.get("/portfolios")
            .then(res => {
                setPortfolios(res.data);
                if (res.data.length > 0) setSelectedPortfolio(res.data[0].id);
            })
            .catch(() => navigate("/login"));
    }, [navigate]);

    useEffect(() => {
        if (!selectedPortfolio) return;
        const fetchData = async () => {
            setLoading(true);
            try {
                const [chartRes, txRes] = await Promise.all([
                    client.get(`/portfolios/${selectedPortfolio}/chart?date_from=2024-01-01&date_to=2025-01-01`),
                    client.get(`/transactions?portfolio_id=${selectedPortfolio}`)
                ]);
                setChartData(chartRes.data);
                setTransactions(txRes.data);
            } finally {
                setLoading(false);
            }
        };
        fetchData();
    }, [selectedPortfolio]);

    function handleLogout() {
        localStorage.removeItem("token");
        onLogout?.();
        navigate("/login");
    }

    const positions = {};
    transactions.forEach(t => {
        if (t.type === "BUY") positions[t.ticker] = (positions[t.ticker] || 0) + t.quantity;
        if (t.type === "SELL") positions[t.ticker] = (positions[t.ticker] || 0) - t.quantity;
    });
    const pieData = Object.entries(positions)
        .filter(([, qty]) => qty > 0)
        .map(([ticker, qty]) => ({ name: ticker, value: qty }));

    const lastValue = chartData.length > 0 ? chartData[chartData.length - 1].value : 0;
    const firstValue = chartData.length > 0 ? chartData[0].value : 0;
    const change = lastValue - firstValue;
    const changePct = firstValue > 0 ? ((change / firstValue) * 100).toFixed(2) : 0;

    const tabStyle = (tab) => ({
        display: "flex",
        alignItems: "center",
        gap: 10,
        padding: "10px 16px",
        borderRadius: 8,
        cursor: "pointer",
        fontSize: 14,
        fontWeight: activeTab === tab ? 600 : 400,
        background: activeTab === tab ? "#2a2a4a" : "transparent",
        color: activeTab === tab ? "#fff" : "#aaa",
        border: "none",
        width: "100%",
        textAlign: "left",
    });

    return (
        <div style={{ display: "flex", minHeight: "100vh", fontFamily: "sans-serif", background: "#f5f5f5" }}>

            {/* SIDEBAR */}
            <div style={{ width: 220, background: "#1a1a2e", color: "#fff", padding: "24px 12px", display: "flex", flexDirection: "column", gap: 8, flexShrink: 0 }}>

                <div style={{ fontSize: 16, fontWeight: 700, color: "#fff", padding: "0 8px", marginBottom: 24 }}>
                    Portfolio Tracker
                </div>

                <div style={{ fontSize: 11, color: "#555", textTransform: "uppercase", padding: "0 8px", marginBottom: 4 }}>Menu</div>

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
                <div style={{ height: 56, background: "#fff", borderBottom: "1px solid #eee", display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0 24px", flexShrink: 0 }}>

                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <span style={{ fontSize: 13, color: "#888" }}>Portfel:</span>
                        <select
                            value={selectedPortfolio || ""}
                            onChange={e => setSelectedPortfolio(e.target.value)}
                            style={{ padding: "5px 10px", borderRadius: 6, border: "1px solid #ddd", fontSize: 13, background: "#fff", cursor: "pointer" }}
                        >
                            {portfolios.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
                        </select>
                    </div>

                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <button
                            onClick={() => setActiveTab("ustawienia")}
                            style={{ padding: "6px 14px", borderRadius: 6, border: "1px solid #ddd", background: "#fff", cursor: "pointer", fontSize: 13, display: "flex", alignItems: "center", gap: 6 }}
                        >
                            Ustawienia
                        </button>
                        <button
                            onClick={handleLogout}
                            style={{ padding: "6px 14px", borderRadius: 6, border: "none", background: "#993C1D", color: "#fff", cursor: "pointer", fontSize: 13 }}
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
                                    { label: "Zmiana", value: `${change >= 0 ? "+" : ""}${change.toFixed(2)} PLN`, color: change >= 0 ? "#4caf50" : "#f44336" },
                                    { label: "Stopa zwrotu", value: `${changePct}%`, color: change >= 0 ? "#4caf50" : "#f44336" },
                                    { label: "Pozycji", value: pieData.length },
                                ].map((m, i) => (
                                    <div key={i} style={{ flex: 1, background: "#fff", borderRadius: 10, padding: "16px 20px", boxShadow: "0 1px 4px rgba(0,0,0,0.06)" }}>
                                        <div style={{ fontSize: 11, color: "#888", marginBottom: 6 }}>{m.label}</div>
                                        <div style={{ fontSize: 20, fontWeight: 600, color: m.color || "#1a1a2e" }}>{m.value}</div>
                                    </div>
                                ))}
                            </div>

                            {/* WYKRES */}
                            <div style={{ background: "#fff", borderRadius: 12, padding: 24, boxShadow: "0 1px 4px rgba(0,0,0,0.06)" }}>
                                <h3 style={{ margin: "0 0 16px 0", fontSize: 15 }}>Wartość portfela</h3>
                                {loading && <p style={{ color: "#888" }}>Ładowanie...</p>}
                                {!loading && chartData.length === 0 && <p style={{ color: "#888" }}>Brak danych — dodaj transakcje.</p>}
                                {!loading && chartData.length > 0 && (
                                    <ResponsiveContainer width="100%" height={300}>
                                        <LineChart data={chartData} margin={{ top: 10, right: 20, bottom: 60, left: 20 }}>
                                            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                                            <XAxis dataKey="date" tick={{ fontSize: 10, fill: "#888" }} interval={9} angle={-45} textAnchor="end" height={60} />
                                            <YAxis tickFormatter={v => v.toLocaleString()} tick={{ fontSize: 11, fill: "#888" }} axisLine={false} tickLine={false} width={80} />
                                            <Tooltip formatter={v => [`${v.toLocaleString()} PLN`, "Wartość"]} contentStyle={{ borderRadius: 8, border: "none", boxShadow: "0 2px 8px rgba(0,0,0,0.1)" }} />
                                            <Line type="monotone" dataKey="value" stroke="#185FA5" dot={false} strokeWidth={2} activeDot={{ r: 4 }} />
                                        </LineChart>
                                    </ResponsiveContainer>
                                )}
                            </div>

                            {/* STRUKTURA */}
                            <div style={{ background: "#fff", borderRadius: 12, padding: 24, boxShadow: "0 1px 4px rgba(0,0,0,0.06)", display: "flex", gap: 32 }}>
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
                        <div style={{ background: "#fff", borderRadius: 12, padding: 24, boxShadow: "0 1px 4px rgba(0,0,0,0.06)" }}>
                            <h3 style={{ margin: "0 0 16px 0", fontSize: 15 }}>Zarządzanie</h3>
                            <p style={{ color: "#888" }}>Tu pojawi się import CSV, lista transakcji i zarządzanie portfelami.</p>
                        </div>
                    )}

                    {/* TAB: USTAWIENIA */}
                    {activeTab === "ustawienia" && (
                        <div style={{ background: "#fff", borderRadius: 12, padding: 24, boxShadow: "0 1px 4px rgba(0,0,0,0.06)" }}>
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