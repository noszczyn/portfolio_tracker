import { useState } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Dashboard from "./pages/Dashboard";

function App() {
    const [token, setToken] = useState(() => localStorage.getItem("token"));

    return (
        <BrowserRouter>
            <Routes>
                <Route path="/login" element={<Login onLogin={setToken} />} />
                <Route path="/register" element={<Register />} />
                <Route
                    path="/dashboard"
                    element={token ? <Dashboard onLogout={() => setToken(null)} /> : <Navigate to="/login" />}
                />
                <Route path="*" element={<Navigate to="/dashboard" />} />
            </Routes>
        </BrowserRouter>
    );
}

export default App;