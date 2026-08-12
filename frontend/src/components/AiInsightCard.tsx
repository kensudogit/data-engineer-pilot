import styles from "./AiInsightCard.module.css";

type GeneratedBy = "template" | "cortex" | "openai";

const LABELS: Record<GeneratedBy, string> = {
  cortex: "AIインサイト（Cortex生成）",
  openai: "AIインサイト（OpenAI生成）",
  template: "サマリー（テンプレート生成・AI不使用）",
};

const TAG_CLASS: Record<GeneratedBy, keyof typeof styles> = {
  cortex: "cortex",
  openai: "openai",
  template: "template",
};

/**
 * Renders a use case's `ai_insight` narrative summary alongside a tag
 * disclosing how it was produced. "cortex" means a real
 * SNOWFLAKE.CORTEX.COMPLETE call generated it (source === "snowflake");
 * "openai" means a real OpenAI chat completion generated it (an optional
 * enhancement to the demo path when OPENAI_API_KEY is set — source stays
 * "demo" either way, since OpenAI never changes which ML backend computed
 * the numbers, only how the narrative text was produced); "template" means
 * it's an f-string built from already-computed metrics — never phrased as
 * if an AI wrote it, and always tagged as such here, mirroring the same
 * "never let a demo result look like the real thing" principle SourceBadge
 * already applies to numbers.
 */
export function AiInsightCard({
  insight,
  generatedBy,
}: {
  insight: string | null | undefined;
  generatedBy: GeneratedBy | null | undefined;
}) {
  if (!insight) return null;
  const key: GeneratedBy = generatedBy ?? "template";

  return (
    <div className={`card ${styles.card}`}>
      <div className={styles.head}>
        <span className={`${styles.tag} ${styles[TAG_CLASS[key]]}`}>{LABELS[key]}</span>
      </div>
      <p className={styles.text}>{insight}</p>
    </div>
  );
}
