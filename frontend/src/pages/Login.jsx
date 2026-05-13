import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import client from "../api/client";

function Login({ onLogin }) {
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [error, setError] = useState("");
    const navigate = useNavigate();

    async function handleLogin() {
        try {
            const params = new URLSearchParams();
            params.append("username", email);
            params.append("password", password);

            const res = await client.post("/login", params);
            localStorage.setItem("token", res.data.access_token);
            onLogin?.(res.data.access_token);
            navigate("/dashboard");
        } catch {
            setError("Nieprawidłowy email lub hasło");
        }
    }

    return (
        <div style={{ maxWidth: 400, margin: "100px auto", padding: 24 }}>
            <h2>Logowanie</h2>
            <input placeholder="Email" value={email} onChange={e => setEmail(e.target.value)} style={{ display: "block", width: "100%", marginBottom: 12, padding: 8 }} />
            <input placeholder="Hasło" type="password" value={password} onChange={e => setPassword(e.target.value)} style={{ display: "block", width: "100%", marginBottom: 12, padding: 8 }} />
            {error && <p style={{ color: "red" }}>{error}</p>}
            <button onClick={handleLogin} style={{ width: "100%", padding: 10 }}>Zaloguj</button>
            <p>Nie masz konta? <Link to="/register">Zarejestruj się</Link></p>
        </div>
    );
}

export default Login;