"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import type { CortexAgentResult, CortexAnalystResult } from "@/lib/types";

type Mode = "analyst" | "agent";

const MODE_LABEL: Record<Mode, string> = {
  analyst: "Cortex Analyst（MARTへの自然言語SQL質問）",
  agent: "Cortex Agent（Cortex Search文書 + Cortex Analyst横断）",
};

const PLACEHOLDER: Record<Mode, string> = {
  analyst: "例: 直近30日のチャネル別売上を教えて",
  agent: "例: 解約リスクの高い顧客への対応方法を教えて",
};

export default function AskPage() {
  const [mode, setMode] = useState<Mode>("analyst");
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<CortexAnalystResult | CortexAgentResult | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!question.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = mode === "analyst" ? await api.askCortexAnalyst(question) : await api.askCortexAgent(question);
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "質問の送信に失敗しました");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <h1 className="pageTitle">AIに質問する</h1>
      <p className="pageSubtitle">
        Snowflake MARTデータ（Cortex Analyst）と、PDF/FAQ/運用マニュアル文書（Cortex
        Search経由でCortex Agentが参照）に対して自然言語で質問できます。この機能にはデモ経路がなく、
        Snowflake接続時のみ動作します。
      </p>

      <div className="card" style={{ marginBottom: 20 }}>
        <div style={{ display: "flex", gap: 10, marginBottom: 16 }}>
          {(["analyst", "agent"] as Mode[]).map((m) => (
            <button
              key={m}
              type="button"
              className={`btn btnOutline btnSmall ${m === mode ? "active" : ""}`}
              onClick={() => {
                setMode(m);
                setResult(null);
                setError(null);
              }}
            >
              {MODE_LABEL[m]}
            </button>
          ))}
        </div>

        <form onSubmit={handleSubmit} className="formGroup">
          <label htmlFor="question">質問</label>
          <textarea
            id="question"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder={PLACEHOLDER[mode]}
            rows={3}
            style={{
              padding: "8px 10px",
              border: "1px solid var(--color-border)",
              borderRadius: 6,
              fontSize: 14,
              fontFamily: "inherit",
              resize: "vertical",
            }}
          />
          <div>
            <button type="submit" className="btn btnPrimary" disabled={loading || !question.trim()}>
              {loading ? "問い合わせ中..." : "質問する"}
            </button>
          </div>
        </form>
      </div>

      {error && <p className="errorText">{error}</p>}

      {result && !result.available && (
        <div className="card" style={{ marginBottom: 20 }}>
          <span className="badge badgeYellow" style={{ marginBottom: 10, display: "inline-block" }}>
            Snowflake接続時のみ利用可能
          </span>
          <p className="mutedText">{result.message}</p>
          <p className="mutedText">現在の実行モード: {result.execution_mode}</p>
        </div>
      )}

      {result && result.available && (
        <div className="card">
          <span className="badge badgeBlue" style={{ marginBottom: 12, display: "inline-block" }}>
            Snowflake Cortex
          </span>
          <p style={{ whiteSpace: "pre-wrap" }}>{result.answer}</p>

          {"generated_sql" in result && result.generated_sql && (
            <>
              <div className="sectionTitle" style={{ marginTop: 16 }}>
                生成されたSQL
              </div>
              <pre
                style={{
                  background: "var(--color-bg)",
                  border: "1px solid var(--color-border)",
                  borderRadius: 6,
                  padding: 12,
                  fontSize: 13,
                  overflowX: "auto",
                }}
              >
                {result.generated_sql}
              </pre>
            </>
          )}

          {"citations" in result && result.citations.length > 0 && (
            <>
              <div className="sectionTitle" style={{ marginTop: 16 }}>
                参照文書
              </div>
              <pre
                style={{
                  background: "var(--color-bg)",
                  border: "1px solid var(--color-border)",
                  borderRadius: 6,
                  padding: 12,
                  fontSize: 13,
                  overflowX: "auto",
                }}
              >
                {JSON.stringify(result.citations, null, 2)}
              </pre>
            </>
          )}
        </div>
      )}
    </div>
  );
}
