import styles from "./AiInsightCard.module.css";

/**
 * Renders a use case's `ai_insight` narrative summary alongside a tag
 * disclosing how it was produced. `ai_insight_generated_by === "cortex"`
 * means a real SNOWFLAKE.CORTEX.COMPLETE call generated the text (only
 * possible when source === "snowflake"); "template" means it's an
 * f-string built from already-computed metrics — never phrased as if an
 * AI wrote it, and always tagged as such here, mirroring the same
 * "never let a demo result look like the real thing" principle SourceBadge
 * already applies to numbers.
 */
export function AiInsightCard({
  insight,
  generatedBy,
}: {
  insight: string | null | undefined;
  generatedBy: "template" | "cortex" | null | undefined;
}) {
  if (!insight) return null;
  const isCortex = generatedBy === "cortex";

  return (
    <div className={`card ${styles.card}`}>
      <div className={styles.head}>
        <span className={`${styles.tag} ${isCortex ? styles.cortex : styles.template}`}>
          {isCortex ? "AIインサイト（Cortex生成）" : "サマリー（テンプレート生成・AI不使用）"}
        </span>
      </div>
      <p className={styles.text}>{insight}</p>
    </div>
  );
}
