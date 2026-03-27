import React, { useEffect, useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Menu, X, Search, Link2, ThumbsUp, ThumbsDown, CircleHelp, LogIn, MessageSquare, Send, Info, Copy, Check } from "lucide-react";

// Global style reset — hapus margin/padding default browser
if (typeof document !== "undefined") {
  const style = document.createElement("style");
  style.textContent = "html, body, #root { margin: 0; padding: 0; width: 100%; min-height: 100vh; }";
  document.head.appendChild(style);
}

const COLORS = {
  bg: "#efebe7",
  panel: "#f7f3ef",
  panelSoft: "#fbf8f5",
  primary: "#ef5b9c",
  primaryDark: "#db4e8c",
  text: "#111111",
  border: "#1d1d1d",
  muted: "#6f6a67",
};

const demoQuestions = [
  "Berapa persentase penduduk miskin Indonesia pada Maret 2025?",
  "Berapa persentase penduduk miskin Indonesia pada September 2025?",
  "Berapa jumlah penduduk miskin Indonesia pada September 2025?",
  "Berapa jumlah penduduk miskin Indonesia pada September 2024?",
  "Berapa garis kemiskinan Indonesia pada Maret 2025?",
  "Berapa garis kemiskinan Indonesia di perkotaan pada Maret 2025?",
  "Berapa garis kemiskinan Indonesia di perdesaan pada Maret 2025?",
  "Berapa persentase penduduk miskin Aceh pada Maret 2025?",
  "Berapa persentase penduduk miskin Aceh pada September 2025?",
  "Berapa persentase penduduk miskin Sumatera Barat di perdesaan pada Maret 2024?",

  "Bandingkan persentase penduduk miskin Indonesia pada Maret 2024 dan Maret 2025.",
  "Bandingkan persentase penduduk miskin Indonesia pada September 2024 dan September 2025.",
  "Bandingkan jumlah penduduk miskin Indonesia pada September 2024 dan September 2025.",
  "Bandingkan garis kemiskinan Indonesia pada Maret 2024 dan Maret 2025.",
  "Bandingkan persentase penduduk miskin Aceh pada Maret 2024 dan Maret 2025.",
  "Bandingkan persentase penduduk miskin Aceh pada September 2024 dan September 2025.",
  "Bandingkan jumlah penduduk miskin Indonesia di perdesaan pada September 2024 dan September 2025.",
  "Bandingkan garis kemiskinan Indonesia di perkotaan pada Maret 2024 dan Maret 2025.",

  "Bagaimana tren kemiskinan Indonesia dalam lima tahun terakhir?",
  "Bagaimana tren jumlah penduduk miskin Indonesia dalam lima tahun terakhir?",
  "Bagaimana tren jumlah penduduk miskin Indonesia di perdesaan dalam lima tahun terakhir?",
  "Bagaimana tren persentase penduduk miskin Indonesia dalam beberapa tahun terakhir?",
  "Bagaimana tren kemiskinan Aceh dalam beberapa tahun terakhir?",
  "Bagaimana tren garis kemiskinan Indonesia dalam lima tahun terakhir?",
  "Benarkah lima tahun terakhir kemiskinan Indonesia menurun?",
  "Benarkah dalam beberapa tahun terakhir angka kemiskinan nasional cenderung membaik?",
  "Benarkah tren kemiskinan Indonesia dalam lima tahun terakhir tidak selalu lurus turun?",
  "Benarkah dalam lima tahun terakhir jumlah penduduk miskin Indonesia cenderung menurun?",

  "Benarkah tahun ini kemiskinan Indonesia turun?",
  "Benarkah tahun ini jumlah penduduk miskin Indonesia menurun?",
  "Benarkah tahun ini angka kemiskinan nasional membaik?",
  "Benarkah tahun ini persentase penduduk miskin Indonesia lebih rendah dibanding tahun lalu?",
  "Benarkah kondisi kemiskinan Indonesia tahun ini lebih baik dibanding tahun sebelumnya?",
  "Benarkah tahun ini kemiskinan Aceh turun?",
  "Benarkah tahun ini angka kemiskinan Aceh masih di atas rata rata nasional?",
  "Benarkah tahun ini penduduk miskin di Indonesia lebih banyak berada di perdesaan daripada di perkotaan?",

  "Pemerintah menyebut tahun ini kemiskinan turun karena programnya berhasil. Apakah klaim ini benar?",
  "Pemerintah menyebut penurunan kemiskinan tahun ini membuktikan kebijakan mereka berhasil. Apakah klaim ini benar?",
  "Pejabat mengatakan angka kemiskinan yang turun tahun ini adalah bukti program pemerintah efektif. Apakah klaim ini benar?",
  "Benarkah penurunan angka kemiskinan saja belum cukup untuk membuktikan satu program pemerintah berhasil?",

  "Berapa persentase penduduk miskin Indonesia pada September 2025?",
  "Berapa jumlah penduduk miskin Indonesia pada September 2025?",
  "Berapa garis kemiskinan Indonesia di perdesaan pada Maret 2025?",
  "Bandingkan persentase penduduk miskin Aceh pada Maret 2024 dan Maret 2025.",
  "Bandingkan jumlah penduduk miskin Indonesia di perdesaan pada September 2024 dan September 2025.",
  "Bandingkan garis kemiskinan Indonesia pada Maret 2024 dan Maret 2025.",
  "Bagaimana tren persentase penduduk miskin Indonesia dalam beberapa tahun terakhir?",
  "Bagaimana tren jumlah penduduk miskin Indonesia di perdesaan dalam lima tahun terakhir?",
  "Bagaimana tren kemiskinan Aceh dalam beberapa tahun terakhir?",
  "Benarkah tahun ini angka kemiskinan Aceh masih di atas rata rata nasional?",
  "Benarkah tahun ini penduduk miskin di Indonesia lebih banyak berada di perdesaan daripada di perkotaan?",
  "Benarkah kondisi kemiskinan Indonesia tahun ini lebih baik dibanding tahun sebelumnya?",
  "Benarkah tahun ini jumlah penduduk miskin Indonesia menurun?",
  "Pemerintah menyebut penurunan kemiskinan tahun ini membuktikan kebijakan mereka berhasil. Apakah klaim ini benar?",
  "Prabowo mengklaim program MBG berhasil menambah 1 juta pekerja di Indonesia pada 2025. Apakah klaim ini benar?"
];


function Button({ children, onClick, variant = "solid", style = {}, disabled = false }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        border: variant === "outline" ? "1px solid rgba(17,17,17,0.12)" : "none",
        background: disabled ? "#d7d2ce" : variant === "outline" ? "white" : COLORS.primary,
        color: variant === "outline" ? COLORS.text : "white",
        borderRadius: 16,
        padding: "12px 18px",
        fontSize: 15,
        fontWeight: 700,
        cursor: disabled ? "not-allowed" : "pointer",
        ...style,
      }}
    >
      {children}
    </button>
  );
}

function Card({ children, style = {} }) {
  return (
    <div
      style={{
        background: COLORS.panel,
        borderRadius: 28,
        boxShadow: "0 1px 3px rgba(0,0,0,0.05)",
        ...style,
      }}
    >
      {children}
    </div>
  );
}

function Pill({ children, style = {} }) {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        borderRadius: 9999,
        padding: "6px 12px",
        fontSize: 13,
        fontWeight: 700,
        ...style,
      }}
    >
      {children}
    </span>
  );
}

function renderReadableText(text) {
  const raw = String(text || "").trim();
  if (!raw) return null;

  const yearMatches = [
    ...raw.matchAll(/((?:19|20)\d{2}):\s*([^]+?)(?=(?:\s*-\s*(?:19|20)\d{2}:)|$)/g),
  ];

  if (yearMatches.length >= 2) {
    const beforeFirst = raw.slice(0, yearMatches[0].index).trim();

    const cleanedMatches = yearMatches.map((m, idx) => {
      let valueText = m[2].trim();
      let trailing = "";

      if (idx === yearMatches.length - 1) {
        const splitMatch = valueText.match(/^(.*?)(\s+(Perubahan total.*|Pola:.*))$/i);
        if (splitMatch) {
          valueText = splitMatch[1].trim();
          trailing = splitMatch[2].trim();
        }
      }

      return {
        year: m[1],
        valueText,
        trailing,
      };
    });

    const trailingText = cleanedMatches
      .map((x) => x.trailing)
      .filter(Boolean)
      .join(" ")
      .trim();

    return (
      <div style={{ lineHeight: 1.8 }}>
        {beforeFirst ? <p style={{ marginTop: 0, marginBottom: 12 }}>{beforeFirst}</p> : null}

        <div style={{ display: "grid", gap: 8 }}>
          {cleanedMatches.map((m, idx) => (
            <div
              key={idx}
              style={{
                display: "grid",
                gridTemplateColumns: "64px 1fr",
                gap: 8,
                alignItems: "start",
              }}
            >
              <div style={{ fontWeight: 700 }}>{m.year}</div>
              <div>{m.valueText}</div>
            </div>
          ))}
        </div>

        {trailingText ? (
          <p style={{ marginTop: 12, marginBottom: 0 }}>{trailingText}</p>
        ) : null}
      </div>
    );
  }

  const bulletParts = raw
    .split(/\s+-\s+/)
    .map((x) => x.trim())
    .filter(Boolean);

  if (bulletParts.length >= 3) {
    return (
      <div style={{ display: "grid", gap: 8 }}>
        {bulletParts.map((item, idx) => (
          <div key={idx} style={{ lineHeight: 1.8 }}>
            • {item}
          </div>
        ))}
      </div>
    );
  }

  return <p style={{ margin: 0, textAlign: "left", lineHeight: 1.8 }}>{raw}</p>;
}

function DownloadLinks({ value }) {
  if (!value) return null;

  const links = Array.isArray(value) ? value.filter(Boolean) : [value].filter(Boolean);
  if (!links.length) return null;

  const backendBase =
    (typeof window !== "undefined" && window.location.hostname)
      ? `${window.location.protocol}//${window.location.hostname}:8000`
      : "http://127.0.0.1:8001";

  function toAbsoluteUrl(link) {
    if (!link) return "#";
    if (/^https?:\/\//i.test(link)) return link;
    if (link.startsWith("/")) return backendBase + link;
    return backendBase + "/" + link;
  }

  function labelFromLink(link) {
    try {
      // Google Drive URL: ambil nama file dari parameter &filename=
      if (link.includes("drive.google.com") && link.includes("filename=")) {
        const match = link.match(/filename=([^&]+)/);
        if (match) return decodeURIComponent(match[1]);
      }
      const raw = link.split("/").pop() || link;
      const decoded = decodeURIComponent(raw);
      return decoded.replace(/\.csv$/i, ".csv");
    } catch (e) {
      return link;
    }
  }

  return (
    <div style={{ marginTop: 12 }}>
      <div
        style={{
          marginBottom: 8,
          fontSize: 15,
          fontWeight: 700,
          color: COLORS.primaryDark,
        }}
      >
        Unduh data
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {links.map((link, idx) => (
          <a
            key={idx}
            href={toAbsoluteUrl(link)}
            target="_blank"
            rel="noreferrer"
            style={{
              color: COLORS.primaryDark,
              fontWeight: 700,
              textDecoration: "none",
              wordBreak: "break-word",
              lineHeight: 1.5,
            }}
          >
            {labelFromLink(link)}
          </a>
        ))}
      </div>
    </div>
  );
}

function Section({ title, children }) {
  return (
    <div style={{ marginTop: 16, textAlign: "left" }}>
      <div
        style={{
          marginBottom: 6,
          fontSize: 13,
          fontWeight: 700,
          textTransform: "uppercase",
          letterSpacing: 0.6,
          color: COLORS.muted,
        }}
      >
        {title}
      </div>
      {renderReadableText(children)}
    </div>
  );
}

function verdictTone(verdict) {
  const v = (verdict || "").toLowerCase();
  if (v === "benar") return { bg: "#dcfce7", color: "#166534" };
  if (v.includes("sebagian")) return { bg: "#fef3c7", color: "#92400e" };
  if (v.includes("menyesatkan")) return { bg: "#ffe4e6", color: "#be123c" };
  return { bg: "#e2e8f0", color: "#475569" };
}

function feedbackChipStyle(active) {
  return {
    display: "inline-flex",
    alignItems: "center",
    gap: 8,
    borderRadius: 9999,
    border: active ? `1px solid ${COLORS.primary}` : "1px solid rgba(17,17,17,0.12)",
    background: active ? "#fff1f7" : "white",
    color: active ? COLORS.primaryDark : COLORS.text,
    padding: "10px 14px",
    fontSize: 14,
    fontWeight: 600,
    cursor: "pointer",
  };
}

const pStyle = {
  marginTop: 0,
  marginBottom: 16,
  color: COLORS.text,
  lineHeight: 1.8,
};

const inputStyle = {
  width: "100%",
  border: "none",
  borderRadius: 16,
  background: "white",
  padding: "14px 16px",
  fontSize: 15,
  boxSizing: "border-box",
  color: COLORS.text,
};

function Header({ page, setPage, isLoggedIn, handleSignOut }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const isMobile = typeof window !== "undefined" ? window.innerWidth <= 640 : false;

  return (
    <div style={{ borderBottom: `1px solid ${COLORS.border}`, position: "relative" }}>
      <div
        style={{
          width: "100%",
          padding: "12px 28px",
          display: "grid",
          gridTemplateColumns: "1fr auto 1fr",
          alignItems: "center",
          gap: 16,
          boxSizing: "border-box",
        }}
      >
        <div style={{ justifySelf: "start" }}>
          {!isMobile && isLoggedIn ? (
            <Button variant="outline" onClick={() => setPage("chat")}>Open Chat</Button>
          ) : null}
        </div>

        <button
          onClick={() => {
            setPage("home");
            setMenuOpen(false);
          }}
          style={{
            background: "transparent",
            border: "none",
            cursor: "pointer",
            fontSize: isMobile ? 24 : 32,
            fontWeight: 900,
            justifySelf: "center",
          }}
        >
          <span style={{ color: COLORS.primary }}>cekdata</span>
          <span style={{ color: "#111111" }}>.ai</span>
        </button>

        {isMobile ? (
          <div style={{ justifySelf: "end", position: "relative" }}>
            <button
              onClick={() => setMenuOpen((v) => !v)}
              style={{
                border: "none",
                background: "transparent",
                width: 32,
                height: 32,
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                cursor: "pointer",
                padding: 0,
                color: COLORS.text,
              }}
            >
              <Menu size={22} />
            </button>

            {menuOpen ? (
              <div
                style={{
                  position: "absolute",
                  top: 44,
                  right: 0,
                  width: 220,
                  background: "white",
                  border: "1px solid rgba(17,17,17,0.08)",
                  borderRadius: 18,
                  boxShadow: "0 8px 24px rgba(0,0,0,0.08)",
                  padding: 10,
                  zIndex: 50,
                }}
              >
                <button
                  onClick={() => {
                    setPage("about");
                    setMenuOpen(false);
                  }}
                  style={mobileMenuButtonStyle}
                >
                  About Cek Data AI
                </button>

                {!isLoggedIn ? (
                  <button
                    onClick={() => {
                      setPage("signin");
                      setMenuOpen(false);
                    }}
                    style={mobileMenuButtonStyle}
                  >
                    Sign In
                  </button>
                ) : (
                  <>
                    <button
                      onClick={() => {
                        setPage("chat");
                        setMenuOpen(false);
                      }}
                      style={mobileMenuButtonStyle}
                    >
                      Open Chat
                    </button>
                    <button
                      onClick={() => {
                        handleSignOut();
                        setMenuOpen(false);
                      }}
                      style={mobileMenuButtonStyle}
                    >
                      Sign Out
                    </button>
                  </>
                )}
              </div>
            ) : null}
          </div>
        ) : (
          <div style={{ display: "flex", alignItems: "center", gap: 8, justifySelf: "end" }}>
            {page !== "about" ? (
              <Button variant="outline" onClick={() => setPage("about")}>
                About Cek Data AI
              </Button>
            ) : null}

            {!isLoggedIn && page !== "signin" ? (
              <Button variant="outline" onClick={() => setPage("signin")}>
                Sign In
              </Button>
            ) : null}

            {isLoggedIn ? (
              <Button variant="outline" onClick={handleSignOut}>
                Sign Out
              </Button>
            ) : null}
          </div>
        )}
      </div>
    </div>
  );
}

const mobileMenuButtonStyle = {
  width: "100%",
  textAlign: "left",
  border: "none",
  background: "transparent",
  padding: "12px 12px",
  borderRadius: 12,
  cursor: "pointer",
  fontSize: 15,
  fontWeight: 600,
  color: COLORS.text,
};

function HomePage({ setPage }) {
  const [demoQuestion, setDemoQuestion] = useState(demoQuestions[0]);
  const [showDemoAnswer, setShowDemoAnswer] = useState(false);
  const [demoResult, setDemoResult] = useState(null);
  const [demoLoading, setDemoLoading] = useState(false);
  const [demoError, setDemoError] = useState("");

  useEffect(() => {
    const pick = demoQuestions[Math.floor(Math.random() * demoQuestions.length)];
    setDemoQuestion(pick);
  }, []);

  function refreshDemoQuestion() {
    let next = demoQuestion;
    while (demoQuestions.length > 1 && next === demoQuestion) {
      next = demoQuestions[Math.floor(Math.random() * demoQuestions.length)];
    }
    setDemoQuestion(next);
    setShowDemoAnswer(false);
    setDemoResult(null);
    setDemoError("");
  }

  async function handleDemoAsk() {
    try {
      setDemoLoading(true);
      setDemoError("");
      setShowDemoAnswer(false);
      setDemoResult(null);

      const res = await fetch("http://127.0.0.1:8001/ask", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ question: demoQuestion }),
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data?.error || "Gagal memanggil backend");
      }

      setDemoResult(data);
      setShowDemoAnswer(true);
    } catch (err) {
      setDemoError(err.message || "Terjadi kesalahan");
    } finally {
      setDemoLoading(false);
    }
  }

  const verdict = verdictTone(demoResult?.parsed?.penilaian || "");

  return (
    <div style={{ maxWidth: 1280, margin: "0 auto", padding: "40px 24px 56px" }}>
      <div
        style={{
          maxWidth: 920,
          margin: "0 auto",
          textAlign: "center",
          padding: "0 12px",
          boxSizing: "border-box",
        }}
      >
        <p
          style={{
            maxWidth: 760,
            margin: "0 auto",
            fontSize: 20,
            lineHeight: 1.8,
            color: COLORS.muted,
          }}
        >
          Cek Data AI adalah alat bantu bagi jurnalis untuk memverifikasi klaim data dan mengujinya dengan sumber resmi serta terpercaya.
        </p>
      </div>

      <div
        style={{
          maxWidth: 980,
          margin: "56px auto 0",
          padding: "0 12px",
          boxSizing: "border-box",
        }}
      >
        <Card>
          <div style={{ padding: 24 }}>
            <div
              style={{
                marginBottom: 18,
                fontSize: 14,
                fontWeight: 700,
                color: COLORS.muted,
                textTransform: "uppercase",
                letterSpacing: 0.6,
                textAlign: "center",
              }}
            >
              Coba versi demo
            </div>

            <div style={{ display: "grid", gap: 16 }}>
              <div style={{ display: "flex", justifyContent: "center" }}>
                <div
                  style={{
                    width: "100%",
                    maxWidth: "100%",
                    borderRadius: 28,
                    padding: "18px 20px",
                    background: COLORS.primary,
                    color: "white",
                    textAlign: "left",
                    fontSize: 16,
                    lineHeight: 1.7,
                  }}
                >
                  {demoQuestion}
                </div>
              </div>

              <div style={{ display: "flex", justifyContent: "center", gap: 12, flexWrap: "wrap" }}>
                <Button onClick={handleDemoAsk} disabled={demoLoading}>
                  {demoLoading ? "Memverifikasi..." : "Verifikasi"}
                </Button>
                <Button variant="outline" onClick={refreshDemoQuestion} disabled={demoLoading}>
                  Refresh
                </Button>
              </div>

              {demoError ? (
                <div style={{ display: "flex", justifyContent: "center" }}>
                  <div
                    style={{
                      width: "100%",
                      maxWidth: 760,
                      borderRadius: 20,
                      padding: 16,
                      background: "#fff1f1",
                      color: "#9f1d1d",
                      textAlign: "left",
                    }}
                  >
                    {demoError}
                  </div>
                </div>
              ) : null}

              {showDemoAnswer && demoResult?.parsed ? (
                <div style={{ display: "flex", justifyContent: "flex-start" }}>
                  <div
                    style={{
                      maxWidth: "100%",
                      borderRadius: 28,
                      padding: 20,
                      background: "white",
                      boxShadow: "0 1px 3px rgba(0,0,0,0.05)",
                      textAlign: "left",
                    }}
                  >
                    <div style={{ marginBottom: 12, display: "flex", flexWrap: "wrap", gap: 10 }}>
                      <Pill style={{ background: COLORS.primary, color: "white" }}>Demo jawaban</Pill>
                      {demoResult.parsed.penilaian ? (
                        <Pill style={{ background: verdict.bg, color: verdict.color }}>
                          {demoResult.parsed.penilaian}
                        </Pill>
                      ) : null}
                    </div>

                    {!demoResult.parsed.temuan_data &&
                    !demoResult.parsed.konteks_penting &&
                    !demoResult.parsed.penilaian &&
                    !demoResult.parsed.alasan &&
                    !demoResult.parsed.peringatan_editorial &&
                    !demoResult.parsed.sumber &&
                    demoResult.answer ? (
                      <p
                        style={{
                          margin: 0,
                          lineHeight: 1.8,
                          color: COLORS.text,
                          whiteSpace: "pre-wrap",
                        }}
                      >
                        {demoResult.answer}
                      </p>
                    ) : null}

                    {demoResult.parsed.temuan_data ? (
                      <Section title="Temuan data">{demoResult.parsed.temuan_data}</Section>
                    ) : null}
                    {demoResult.parsed.konteks_penting ? (
                      <Section title="Konteks penting">{demoResult.parsed.konteks_penting}</Section>
                    ) : null}
                    {demoResult.parsed.penilaian ? (
                      <Section title="Penilaian">{demoResult.parsed.penilaian}</Section>
                    ) : null}
                    {demoResult.parsed.alasan ? (
                      <Section title="Alasan">{demoResult.parsed.alasan}</Section>
                    ) : null}

                    {demoResult.parsed.peringatan_editorial ? (
                      <div
                        style={{
                          marginTop: 16,
                          borderRadius: 20,
                          padding: 16,
                          background: "#fff7fb",
                          border: "1px solid rgba(239,91,156,0.25)",
                        }}
                      >
                        <div
                          style={{
                            marginBottom: 8,
                            fontSize: 13,
                            fontWeight: 700,
                            color: COLORS.primaryDark,
                            textTransform: "uppercase",
                          }}
                        >
                          Peringatan editorial
                        </div>
                        <p style={{ margin: 0, lineHeight: 1.7 }}>
                          {demoResult.parsed.peringatan_editorial}
                        </p>
                      </div>
                    ) : null}

                    {demoResult.parsed.followup_prompt ? (
                      <div
                        style={{
                          marginTop: 16,
                          borderRadius: 20,
                          padding: 16,
                          background: "#f0f4ff",
                          border: "1px solid rgba(41,128,185,0.25)",
                        }}
                      >
                        <div
                          style={{
                            marginBottom: 8,
                            fontSize: 13,
                            fontWeight: 700,
                            color: "#2980b9",
                            textTransform: "uppercase",
                          }}
                        >
                          Bantu kami membantu kamu
                        </div>
                        <p style={{ margin: 0, lineHeight: 1.7 }}>
                          {demoResult.parsed.followup_prompt}
                        </p>
                      </div>
                    ) : null}

                    {demoResult.parsed.sumber ? (
                      <Section title="Sumber">{demoResult.parsed.sumber}</Section>
                    ) : null}

                    {demoResult.parsed.unduh_data ? (
                      <DownloadLinks value={demoResult.parsed.unduh_data} />
                    ) : null}
                  </div>
                </div>
              ) : null}
            </div>
          </div>
        </Card>

        <div
          style={{
            marginTop: 18,
            textAlign: "center",
            color: COLORS.muted,
            lineHeight: 1.7,
            fontSize: 14,
            maxWidth: 760,
            marginLeft: "auto",
            marginRight: "auto",
            padding: "0 12px",
            boxSizing: "border-box",
          }}
        >
          Akses penuh ke fitur chat saat ini hanya tersedia bagi pengguna uji coba yang telah memperoleh akun dari admin. Untuk mencoba versi penuh, silakan hubungi admin.
        </div>
      </div>
    </div>
  );
}

function AboutPage() {
  return (
    <div style={{ maxWidth: 980, margin: "0 auto", padding: "40px 24px 56px" }}>
      <Card>
        <div style={{ padding: 32, textAlign: "left" }}>
          <div
            style={{
              marginBottom: 10,
              fontSize: 14,
              fontWeight: 700,
              color: COLORS.muted,
              textTransform: "uppercase",
              letterSpacing: 0.6,
            }}
          >
            About Cek Data AI
          </div>

          <p style={pStyle}>
            Cek Data AI adalah prototipe yang membantu jurnalis memeriksa klaim menggunakan data resmi. Sistem ini dirancang untuk mendukung proses verifikasi awal agar klaim publik, terutama yang berkaitan dengan angka dan statistik, tidak langsung diterima begitu saja tanpa pemeriksaan data.
          </p>

          <p style={pStyle}>
            Cek Data AI dikembangkan oleh tim{" "}
            <a
              href="https://idjnetwork.org"
              target="_blank"
              rel="noreferrer"
              style={{ color: COLORS.primaryDark, fontWeight: 700, textDecoration: "none" }}
            >
              Indonesia Data Journalism Network (IDJN)
            </a>{" "}
            sebagai bagian dari upaya memperkuat praktik jurnalisme berbasis data dan verifikasi berbasis bukti di Indonesia.
          </p>

          <div
            style={{
              marginTop: 28,
              marginBottom: 14,
              fontSize: 14,
              fontWeight: 700,
              color: COLORS.muted,
              textTransform: "uppercase",
              letterSpacing: 0.6,
            }}
          >
            Methodology
          </div>

          <p style={pStyle}>
            Cek Data AI membantu jurnalis memeriksa klaim menggunakan data resmi. Sistem ini bekerja dengan mencari data yang paling relevan dari basis pengetahuan yang sudah disiapkan, lalu menggunakan AI untuk membantu menyusun jawaban.
          </p>

          <p style={pStyle}>
            Pada tahap ini, basis pengetahuan Cek Data AI memuat sekitar 10.000 tabel data resmi dari BPS. Sebelum digunakan, data tersebut terlebih dahulu dibersihkan dan disusun ulang agar lebih rapi, lebih konsisten, dan lebih mudah dicari oleh sistem.
          </p>

          <p style={pStyle}>
            Saat pengguna mengajukan pertanyaan, sistem mencoba mengenali topik, wilayah, dan periode waktu yang dimaksud, lalu mencari data yang paling sesuai. Jawaban kemudian disusun berdasarkan data yang ditemukan. Jika data yang relevan belum tersedia, sistem seharusnya menyatakan keterbatasan itu secara terbuka.
          </p>

          <p style={{ ...pStyle, marginBottom: 0 }}>
            Sebagai prototipe, Cek Data AI masih dalam tahap pengujian terbatas. Cakupan data dan kualitas sistem akan terus diperbaiki seiring proses uji coba. Untuk saat ini, akses penuh ke fitur chat hanya tersedia bagi pengguna yang telah memperoleh akun uji coba dari admin.
          </p>

          <div
            style={{
              marginTop: 28,
              marginBottom: 14,
              fontSize: 14,
              fontWeight: 700,
              color: COLORS.muted,
              textTransform: "uppercase",
              letterSpacing: 0.6,
            }}
          >
            Editorial Review
          </div>

          <p style={pStyle}>
            Cek Data AI tidak hanya mencocokkan klaim dengan angka, tetapi juga membantu membaca apakah data yang ditemukan benar benar cukup untuk mendukung sebuah klaim. Karena itu, hasil verifikasi tidak berhenti pada temuan data, tetapi juga dilengkapi dengan penilaian dan catatan editorial.
          </p>

          <p style={pStyle}>
            <strong>Benar</strong> digunakan ketika klaim didukung oleh data yang relevan, sebanding, dan cukup jelas.
          </p>

          <p style={pStyle}>
            <strong>Salah</strong> digunakan ketika data yang tersedia secara langsung bertentangan dengan klaim yang diajukan.
          </p>

          <p style={pStyle}>
            <strong>Sebagian benar</strong> digunakan ketika klaim memakai sebagian data yang benar, tetapi kesimpulan yang ditarik berlebihan, tidak utuh, atau melompat lebih jauh daripada yang bisa dibuktikan data.
          </p>

          <p style={pStyle}>
            <strong>Tidak dapat diverifikasi</strong> digunakan ketika data yang tersedia belum cukup untuk mendukung penilaian tegas, misalnya karena pembanding tidak lengkap, periode tidak setara, indikator yang dipakai tidak tepat, atau data yang tersedia belum cukup untuk membuktikan klaim.
          </p>

          <p style={pStyle}>
            <strong>Peringatan editorial</strong> ditampilkan ketika data yang ditemukan perlu dibaca dengan kehati-hatian tambahan. Fitur ini penting terutama untuk klaim sebab-akibat, klaim keberhasilan program, atau klaim yang melompat dari perubahan angka ke kesimpulan politik atau kebijakan. Dalam situasi seperti ini, Cek Data AI membantu menunjukkan batas pembacaan data dan memunculkan pertanyaan kritis yang bisa dipakai untuk tindak lanjut jurnalistik.
          </p>

          <p style={{ ...pStyle, marginBottom: 0 }}>
            Secara sederhana, data yang ditemukan belum tentu otomatis membuktikan sebuah klaim. Di situlah penilaian dan editorial review membantu pengguna membedakan antara angka, konteks, dan kesimpulan.
          </p>
        </div>
      </Card>
    </div>
  );
}

function SignInPage({ setPage, setIsLoggedIn }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleLogin() {
    if (!email.trim() || !password.trim()) {
      setError("Masukkan email dan password.");
      return;
    }
    try {
      setLoading(true);
      setError("");
      const res = await fetch("http://127.0.0.1:8001/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim(), password }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data?.detail || "Email atau password salah.");
        return;
      }
      try { localStorage.setItem("cekdata_auth_token", data.token || ""); } catch {}
      setIsLoggedIn(true);
      localStorage.setItem("cekdata_logged_in", "true");
      setPage("chat");
    } catch (e) {
      setError("Gagal menghubungi server. Pastikan backend berjalan.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div
      style={{
        maxWidth: 1280,
        margin: "0 auto",
        padding: "40px 24px",
        minHeight: "calc(100vh - 120px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        style={{ width: "100%", maxWidth: 460 }}
      >
        <Card>
          <div style={{ padding: 32, textAlign: "left" }}>
            <div style={{ textAlign: "center", marginBottom: 24 }}>
              <div style={{ marginTop: 8, fontSize: 28, fontWeight: 700 }}>Sign In</div>
              <p style={{ marginTop: 8, color: COLORS.muted, lineHeight: 1.7 }}>
                Akses saat ini dibatasi untuk pengguna uji coba yang telah memperoleh akun dari admin.
              </p>
            </div>

            <div style={{ display: "grid", gap: 14 }}>
              <input
                placeholder="Email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                style={inputStyle}
              />
              <input
                type="password"
                placeholder="Password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                style={inputStyle}
              />
              <Button onClick={handleLogin} style={{ width: "100%" }}>
                Masuk
              </Button>
            </div>

            {error ? (
              <p
                style={{
                  marginTop: 14,
                  marginBottom: 0,
                  color: "#b42318",
                  lineHeight: 1.6,
                  textAlign: "center",
                  fontSize: 14,
                }}
              >
                {error}
              </p>
            ) : null}

            <p
              style={{
                marginTop: 16,
                marginBottom: 0,
                color: COLORS.muted,
                lineHeight: 1.7,
                textAlign: "center",
              }}
            >
              Butuh akses uji coba? Hubungi admin.
            </p>
          </div>
        </Card>
      </motion.div>
    </div>
  );
}

function ChatPage() {
  const [conversations, setConversations] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [mobileHistoryOpen, setMobileHistoryOpen] = useState(false);
  const [historyReady, setHistoryReady] = useState(false);
  const [copiedId, setCopiedId] = useState(null);

  useEffect(() => {
    try {
      const saved = localStorage.getItem("cekdata_chat_history");
      const savedSelectedId = localStorage.getItem("cekdata_chat_selected_id");

      if (saved) {
        const parsed = JSON.parse(saved);

        if (Array.isArray(parsed)) {
          const trimmed = parsed.slice(-5);
          setConversations(trimmed);

          if (savedSelectedId && trimmed.some((item) => item.id === savedSelectedId)) {
            setSelectedId(savedSelectedId);
          } else if (trimmed.length > 0) {
            setSelectedId(trimmed[trimmed.length - 1].id);
          } else {
            setSelectedId(null);
          }
        } else {
          setConversations([]);
          setSelectedId(null);
        }
      } else {
        setConversations([]);
        setSelectedId(null);
      }
    } catch (e) {
      console.error("Gagal membaca histori chat", e);
      setConversations([]);
      setSelectedId(null);
    } finally {
      setHistoryReady(true);
    }
  }, []);

  useEffect(() => {
    if (!historyReady) return;

    try {
      const trimmed = conversations.slice(-5);
      localStorage.setItem("cekdata_chat_history", JSON.stringify(trimmed));

      if (selectedId && trimmed.some((item) => item.id === selectedId)) {
        localStorage.setItem("cekdata_chat_selected_id", selectedId);
      } else if (trimmed.length > 0) {
        localStorage.setItem("cekdata_chat_selected_id", trimmed[trimmed.length - 1].id);
      } else {
        localStorage.removeItem("cekdata_chat_selected_id");
      }
    } catch (e) {
      console.error("Gagal menyimpan histori chat", e);
    }
  }, [conversations, selectedId, historyReady]);

  const isMobile = typeof window !== "undefined" ? window.innerWidth <= 768 : false;
  const selectedConversation = conversations.find((item) => item.id === selectedId) || null;

  function buildCopyText(result) {
    if (!result) return "";

    if (result.answer) return result.answer;
    if (result.parsed?.raw_answer) return result.parsed.raw_answer;

    const sections = [];
    if (result.parsed?.temuan_data) sections.push("Temuan data\n" + result.parsed.temuan_data);
    if (result.parsed?.konteks_penting) sections.push("Konteks penting\n" + result.parsed.konteks_penting);
    if (result.parsed?.penilaian) sections.push("Penilaian\n" + result.parsed.penilaian);
    if (result.parsed?.alasan) sections.push("Alasan\n" + result.parsed.alasan);
    if (result.parsed?.peringatan_editorial) sections.push("Peringatan editorial\n" + result.parsed.peringatan_editorial);
    if (result.parsed?.followup_prompt) sections.push(result.parsed.followup_prompt);
    if (result.parsed?.sumber) sections.push("Sumber\n" + result.parsed.sumber);

    const unduh = result.parsed?.unduh_data;
    if (unduh) {
      if (Array.isArray(unduh)) {
        sections.push("Unduh data\n" + unduh.join("\n"));
      } else {
        sections.push("Unduh data\n" + unduh);
      }
    }

    return sections.join("\n\n").trim();
  }

  async function handleCopyAnswer(conversation) {
    try {
      const text = buildCopyText(conversation?.result);
      if (!text) return;
      await navigator.clipboard.writeText(text);
      setCopiedId(conversation.id);
      window.setTimeout(() => {
        setCopiedId((prev) => (prev === conversation.id ? null : prev));
      }, 1500);
    } catch (err) {
      console.error("Gagal menyalin jawaban", err);
    }
  }

  const historyItems = conversations.slice(-5).reverse();

  async function handleAsk() {
    const question = draft.trim();
    if (!question || loading) return;

    try {
      setLoading(true);
      setError("");

      const res = await fetch("http://127.0.0.1:8001/ask", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ question }),
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data?.error || "Gagal memanggil backend");
      }

      const newItem = {
        id: String(Date.now()),
        question,
        result: data,
        feedback: null,
      };

      setConversations((prev) => [...prev, newItem].slice(-5));
      setSelectedId(newItem.id);
      setDraft("");
      setMobileHistoryOpen(false);
    } catch (err) {
      setError(err.message || "Terjadi kesalahan");
    } finally {
      setLoading(false);
    }
  }

  function handleNewChat() {
    setSelectedId(null);
    setDraft("");
    setError("");
    setMobileHistoryOpen(false);
  }

  function setFeedback(id, value) {
    setConversations((prev) =>
      prev.map((item) => (item.id === id ? { ...item, feedback: value } : item))
    );
  }

  function HistoryList() {
    return (
      <>
        <Button onClick={handleNewChat} style={{ width: "100%", marginBottom: 16 }}>
          <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
            <MessageSquare size={16} />
            New chat
          </span>
        </Button>

        <div style={{ display: "grid", gap: 8 }}>
          {historyItems.length === 0 ? (
            <div
              style={{
                color: COLORS.muted,
                fontSize: 14,
                lineHeight: 1.7,
                padding: "8px 4px",
              }}
            >
              Belum ada riwayat obrolan.
            </div>
          ) : (
            historyItems.map((item) => {
              const active = item.id === selectedId;
              return (
                <button
                  key={item.id}
                  onClick={() => {
                    setSelectedId(item.id);
                    setMobileHistoryOpen(false);
                  }}
                  style={{
                    width: "100%",
                    textAlign: "left",
                    border: active ? `1px solid ${COLORS.primary}` : "1px solid transparent",
                    background: active ? "#fff1f7" : "transparent",
                    borderRadius: 14,
                    padding: 12,
                    cursor: "pointer",
                  }}
                >
                  <div
                    style={{
                      fontSize: 14,
                      fontWeight: 700,
                      color: COLORS.text,
                      lineHeight: 1.5,
                      marginBottom: 4,
                    }}
                  >
                    {item.question.length > 72 ? item.question.slice(0, 72) + "..." : item.question}
                  </div>
                </button>
              );
            })
          )}
        </div>
      </>
    );
  }

  return (
    <div style={{ minHeight: "calc(100vh - 57px)", position: "relative" }}>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: isMobile ? "1fr" : "280px minmax(0,1fr)",
          minHeight: "calc(100vh - 57px)",
        }}
      >
        {!isMobile ? (
          <aside
            style={{
              background: COLORS.panel,
              borderRight: "1px solid rgba(17,17,17,0.08)",
              padding: 16,
            }}
          >
            <HistoryList />
          </aside>
        ) : null}

        <main style={{ minWidth: 0, display: "flex", flexDirection: "column" }}>
          <div
            style={{
              borderBottom: "1px solid rgba(17,17,17,0.08)",
              padding: "14px 18px",
              display: "flex",
              alignItems: "center",
              gap: 12,
              fontSize: 14,
              fontWeight: 700,
            }}
          >
            {isMobile ? (
              <button
                onClick={() => setMobileHistoryOpen(true)}
                style={{
                  border: "none",
                  background: "transparent",
                  width: 32,
                  height: 32,
                  display: "inline-flex",
                  alignItems: "center",
                  justifyContent: "center",
                  cursor: "pointer",
                  padding: 0,
                  color: COLORS.text,
                  flexShrink: 0,
                }}
              >
                <Menu size={22} />
              </button>
            ) : null}
            <span>Cek Data AI Chat</span>
          </div>

          <div style={{ flex: 1, padding: isMobile ? 16 : 24 }}>
            <div style={{ maxWidth: 860, margin: "0 auto", display: "grid", gap: 18 }}>
              {selectedConversation ? (
                <>
                                    <div style={{ display: "flex", justifyContent: "flex-end" }}>
                    <div
                      style={{
                        maxWidth: "100%",
                        width: "fit-content",
                        background: COLORS.primary,
                        color: "white",
                        borderRadius: 24,
                        padding: "16px 18px",
                        lineHeight: 1.7,
                        textAlign: "left",
                      }}
                    >
                      {selectedConversation.question}
                    </div>
                  </div>

                  <div style={{ display: "flex", justifyContent: "flex-start" }}>
                    <div
                      style={{
                        maxWidth: "100%",
                        background: "white",
                        borderRadius: 24,
                        padding: 20,
                        boxShadow: "0 1px 3px rgba(0,0,0,0.05)",
                        textAlign: "left",
                        position: "relative",
                      }}
                    >
                      <button
                        onClick={() => handleCopyAnswer(selectedConversation)}
                        title="Copy jawaban"
                        style={{
                          position: "absolute",
                          top: 14,
                          right: 14,
                          display: "inline-flex",
                          alignItems: "center",
                          gap: 6,
                          border: "1px solid rgba(17,17,17,0.08)",
                          background: "#fff",
                          borderRadius: 999,
                          padding: "6px 10px",
                          cursor: "pointer",
                          color: COLORS.muted,
                          fontSize: 12,
                          fontWeight: 600,
                        }}
                      >
                        {copiedId === selectedConversation?.id ? <Check size={14} /> : <Copy size={14} />}
                        {copiedId === selectedConversation?.id ? "Copied" : "Copy"}
                      </button>
                      {selectedConversation.result?.parsed?.penilaian ? (
                        <div style={{ marginBottom: 12, display: "flex", flexWrap: "wrap", gap: 10 }}>
                          <Pill
                            style={{
                              background: verdictTone(selectedConversation.result.parsed.penilaian || "").bg,
                              color: verdictTone(selectedConversation.result.parsed.penilaian || "").color,
                            }}
                          >
                            {selectedConversation.result.parsed.penilaian}
                          </Pill>
                        </div>
                      ) : null}
                      {selectedConversation.result?.parsed?.temuan_data ? (
                        <Section title="Temuan data">{selectedConversation.result.parsed.temuan_data}</Section>
                      ) : null}

                      {!selectedConversation.result?.parsed?.temuan_data &&
                      !selectedConversation.result?.parsed?.konteks_penting &&
                      !selectedConversation.result?.parsed?.penilaian &&
                      !selectedConversation.result?.parsed?.alasan &&
                      !selectedConversation.result?.parsed?.peringatan_editorial &&
                      !selectedConversation.result?.parsed?.sumber &&
                      selectedConversation.result?.answer ? (
                        <p
                          style={{
                            margin: 0,
                            lineHeight: 1.8,
                            color: COLORS.text,
                            whiteSpace: "pre-wrap",
                          }}
                        >
                          {selectedConversation.result.answer}
                        </p>
                      ) : null}

                      {selectedConversation.result?.parsed?.konteks_penting ? (
                        <Section title="Konteks penting">
                          {selectedConversation.result.parsed.konteks_penting}
                        </Section>
                      ) : null}

                      {selectedConversation.result?.parsed?.penilaian ? (
                        <Section title="Penilaian">{selectedConversation.result.parsed.penilaian}</Section>
                      ) : null}

                      {selectedConversation.result?.parsed?.alasan ? (
                        <Section title="Alasan">{selectedConversation.result.parsed.alasan}</Section>
                      ) : null}

                      {selectedConversation.result?.parsed?.peringatan_editorial ? (
                        <div
                          style={{
                            marginTop: 16,
                            borderRadius: 18,
                            padding: 16,
                            background: "#fff7fb",
                            border: "1px solid rgba(239,91,156,0.25)",
                          }}
                        >
                          <div
                            style={{
                              marginBottom: 8,
                              fontSize: 13,
                              fontWeight: 700,
                              color: COLORS.primaryDark,
                              textTransform: "uppercase",
                            }}
                          >
                            Peringatan editorial
                          </div>
                          <p style={{ margin: 0, lineHeight: 1.7 }}>
                            {selectedConversation.result.parsed.peringatan_editorial}
                          </p>
                        </div>
                      ) : null}

                      {selectedConversation.result?.parsed?.followup_prompt ? (
                        <div
                          style={{
                            marginTop: 16,
                            borderRadius: 20,
                            padding: 16,
                            background: "#f0f4ff",
                            border: "1px solid rgba(41,128,185,0.25)",
                          }}
                        >
                          <div
                            style={{
                              marginBottom: 8,
                              fontSize: 13,
                              fontWeight: 700,
                              color: "#2980b9",
                              textTransform: "uppercase",
                            }}
                          >
                            Bantu kami membantu kamu
                          </div>
                          <p style={{ margin: 0, lineHeight: 1.7 }}>
                            {selectedConversation.result.parsed.followup_prompt}
                          </p>
                        </div>
                      ) : null}

                      {selectedConversation.result?.parsed?.sumber ? (
                        <Section title="Sumber">{selectedConversation.result.parsed.sumber}</Section>
                      ) : null}

                      {selectedConversation.result?.parsed?.unduh_data ? (
                        <DownloadLinks value={selectedConversation.result.parsed.unduh_data} />
                      ) : null}

                      <div
                        style={{
                          marginTop: 18,
                          paddingTop: 16,
                          borderTop: "1px solid rgba(17,17,17,0.08)",
                        }}
                      >
                        <div
                          style={{
                            marginBottom: 10,
                            fontSize: 13,
                            fontWeight: 700,
                            color: COLORS.muted,
                            textTransform: "uppercase",
                            letterSpacing: 0.6,
                          }}
                        >
                          Feedback
                        </div>
                        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                          <button
                            onClick={() => setFeedback(selectedConversation.id, "membantu")}
                            style={feedbackChipStyle(selectedConversation.feedback === "membantu")}
                          >
                            <ThumbsUp size={16} />
                            Membantu
                          </button>
                          <button
                            onClick={() => setFeedback(selectedConversation.id, "kurang tepat")}
                            style={feedbackChipStyle(selectedConversation.feedback === "kurang tepat")}
                          >
                            <CircleHelp size={16} />
                            Kurang tepat
                          </button>
                          <button
                            onClick={() => setFeedback(selectedConversation.id, "salah")}
                            style={feedbackChipStyle(selectedConversation.feedback === "salah")}
                          >
                            <ThumbsDown size={16} />
                            Salah
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                </>
              ) : (
                <div
                  style={{
                    color: COLORS.muted,
                    textAlign: "center",
                    lineHeight: 1.8,
                    padding: "48px 16px",
                  }}
                >
                  Mulai percakapan baru untuk memeriksa klaim.
                </div>
              )}

              {error ? (
                <div
                  style={{
                    background: "#fff1f1",
                    color: "#9f1d1d",
                    borderRadius: 16,
                    padding: 14,
                    textAlign: "left",
                  }}
                >
                  {error}
                </div>
              ) : null}
            </div>
          </div>

          <div
            style={{
              borderTop: "1px solid rgba(17,17,17,0.08)",
              paddingTop: isMobile ? 16 : 24,
              paddingBottom: isMobile ? 18 : 26,
              paddingLeft: isMobile ? 12 : 16,
              paddingRight: isMobile ? 12 : 16,
              background: COLORS.bg,
            }}
          >
            <div
              style={{
                maxWidth: 860,
                margin: "0 auto",
              }}
            >
              <div
                style={{
                  display: "flex",
                  gap: 12,
                  alignItems: "flex-end",
                }}
              >
                <textarea
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      handleAsk();
                    }
                  }}
                  placeholder="Tulis pertanyaan atau klaim yang ingin diperiksa..."
                  style={{
                    flex: 1,
                    minHeight: 56,
                    maxHeight: 180,
                    borderRadius: 18,
                    border: "1px solid rgba(17,17,17,0.08)",
                    background: "white",
                    padding: 14,
                    fontSize: 16,
                    lineHeight: 1.6,
                    resize: "vertical",
                    boxSizing: "border-box",
                    color: COLORS.text,
                    boxShadow: "0 8px 24px rgba(17,17,17,0.06)",
                  }}
                />
                <Button onClick={handleAsk} disabled={loading} style={{ height: 56 }}>
                  <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
                    <Send size={16} />
                    {loading ? "Memeriksa..." : "Kirim"}
                  </span>
                </Button>
              </div>

              <p
                style={{
                  marginTop: 10,
                  marginBottom: 0,
                  textAlign: "center",
                  fontSize: 12,
                  lineHeight: 1.5,
                  color: COLORS.muted,
                }}
              >
                Cek Data AI masih prototipe untuk uji coba. Cek ulang untuk informasi penting.
              </p>
            </div>
          </div>
        </main>
      </div>

      {isMobile && mobileHistoryOpen ? (
        <>
          <div
            onClick={() => setMobileHistoryOpen(false)}
            style={{
              position: "fixed",
              inset: 0,
              background: "rgba(0,0,0,0.25)",
              zIndex: 40,
            }}
          />
          <div
            style={{
              position: "fixed",
              top: 0,
              left: 0,
              bottom: 0,
              width: "80%",
              maxWidth: 320,
              background: COLORS.panel,
              borderRight: "1px solid rgba(17,17,17,0.08)",
              padding: 16,
              zIndex: 50,
              overflowY: "auto",
            }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: 12,
              }}
            >
              <div style={{ fontSize: 16, fontWeight: 700 }}>Riwayat</div>
              <button
                onClick={() => setMobileHistoryOpen(false)}
                style={{
                  border: "none",
                  background: "transparent",
                  width: 32,
                  height: 32,
                  display: "inline-flex",
                  alignItems: "center",
                  justifyContent: "center",
                  cursor: "pointer",
                  padding: 0,
                  color: COLORS.text,
                }}
              >
                <X size={20} />
              </button>
            </div>
            <HistoryList />
          </div>
        </>
      ) : null}
    </div>
  );
}

export default function App() {
  const [isLoggedIn, setIsLoggedIn] = useState(() => {
    try {
      return localStorage.getItem("cekdata_logged_in") === "true";
    } catch (e) {
      console.error("Gagal membaca status login", e);
      return false;
    }
  });

  const [page, setPage] = useState(() => {
    try {
      const savedLogin = localStorage.getItem("cekdata_logged_in") === "true";
      const savedPage = localStorage.getItem("cekdata_page");

      if (savedLogin) {
        if (savedPage && ["home", "about", "signin", "chat"].includes(savedPage)) {
          return savedPage;
        }
        return "chat";
      }

      if (savedPage && ["home", "about", "signin"].includes(savedPage)) {
        return savedPage;
      }

      return "home";
    } catch (e) {
      console.error("Gagal membaca status halaman", e);
      return "home";
    }
  });

  useEffect(() => {
    try {
      if (page === "chat" && !isLoggedIn) {
        localStorage.setItem("cekdata_page", "signin");
      } else {
        localStorage.setItem("cekdata_page", page);
      }
    } catch (e) {
      console.error("Gagal menyimpan status halaman", e);
    }
  }, [page, isLoggedIn]);

  useEffect(() => {
    try {
      localStorage.setItem("cekdata_logged_in", isLoggedIn ? "true" : "false");
    } catch (e) {
      console.error("Gagal menyimpan status login", e);
    }
  }, [isLoggedIn]);

  function handleSignOut() {
    setIsLoggedIn(false);
    localStorage.removeItem("cekdata_logged_in");
    localStorage.setItem("cekdata_page", "home");
    setPage("home");
  }

  return (
    <div
      style={{
        minHeight: "100vh",
        background: COLORS.bg,
        color: COLORS.text,
        fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
        display: "flex",
        flexDirection: "column",
      }}
    >
      <Header page={page} setPage={setPage} isLoggedIn={isLoggedIn} handleSignOut={handleSignOut} />

      <div style={{ flex: 1 }}>
        {page === "home" ? <HomePage setPage={setPage} /> : null}
        {page === "about" ? <AboutPage /> : null}
        {page === "signin" ? <SignInPage setPage={setPage} setIsLoggedIn={setIsLoggedIn} /> : null}
        {page === "chat" ? (
          isLoggedIn ? (
            <ChatPage />
          ) : (
            <SignInPage setPage={setPage} setIsLoggedIn={setIsLoggedIn} />
          )
        ) : null}
      </div>

      {page !== "chat" ? (
        <footer style={{ background: COLORS.primary }}>
          <div
            style={{
              maxWidth: 1280,
              margin: "0 auto",
              padding: "16px 24px",
              display: "flex",
              justifyContent: "center",
              gap: 12,
              flexWrap: "wrap",
              color: "white",
              fontSize: 14,
              textAlign: "center",
              width: "100%",
              boxSizing: "border-box",
            }}
          >
            <span>Developed by IDJN</span>
            <span>|</span>
            <span>Prototype for limited testing</span>
          </div>
        </footer>
      ) : null}
    </div>
  );
}
