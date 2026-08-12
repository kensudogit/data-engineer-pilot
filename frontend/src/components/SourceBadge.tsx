import type { Source } from "@/lib/types";
import styles from "./SourceBadge.module.css";

/**
 * Makes every page's `source` field visible at a glance, so a demo-mode
 * result (statsmodels/scikit-learn approximation) can never be mistaken for
 * a real trained BigQuery ML model's output.
 */
export function SourceBadge({ source, model }: { source: Source; model: string }) {
  const isDemo = source === "demo";
  return (
    <span
      className={`${styles.badge} ${isDemo ? styles.demo : styles.bigquery}`}
      title={`model: ${model}`}
    >
      {isDemo ? "デモモード（ローカル近似計算）" : "BigQuery ML"}
    </span>
  );
}
