import type { Source } from "@/lib/types";
import styles from "./SourceBadge.module.css";

const LABELS: Record<Source, string> = {
  demo: "デモモード（ローカル近似計算）",
  bigquery: "BigQuery ML",
  snowflake: "Snowflake Cortex / Snowpark ML",
};

/**
 * Makes every page's `source` field visible at a glance, so a demo-mode
 * result (statsmodels/scikit-learn approximation) can never be mistaken for
 * a real trained BigQuery ML or Snowflake Cortex/Snowpark ML model's output.
 */
export function SourceBadge({ source, model }: { source: Source; model: string }) {
  return (
    <span className={`${styles.badge} ${styles[source]}`} title={`model: ${model}`}>
      {LABELS[source]}
    </span>
  );
}
