import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import client from "../api/client";

function Register() {
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [error, setError] = useState("");
    const navigate = useNavigate();

    async function handleRegister() {
        try {
            await client.post("/register", { email, password });
            navigate("/login");
        } catch {
            setError("Rejestracja nie powiodła się");
        }
    }

    return (
        <div style={{ maxWidth: 400, margin: "100px auto", padding: 24 }}>
            <h2>Rejestracja</h2>
            <input placeholder="Email" value={email} onChange={e => setEmail(e.target.value)} style={{ display: "block", width: "100%", marginBottom: 12, padding: 8 }} />
            <input placeholder="Hasło" type="password" value={password} onChange={e => setPassword(e.target.value)} style={{ display: "block", width: "100%", marginBottom: 12, padding: 8 }} />
            {error && <p style={{ color: "red" }}>{error}</p>}
            <button onClick={handleRegister} style={{ width: "100%", padding: 10 }}>Zarejestruj</button>
            <p>Masz już konto? <Link to="/login">Zaloguj się</Link></p>
        </div>
    );
}

export default Register;