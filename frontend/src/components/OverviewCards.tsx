import Link from "next/link";
import type { UseCaseSummary } from "@/lib/types";
import styles from "./OverviewCards.module.css";

const HREF: Record<string, string> = {
  "sales-forecast": "/sales-forecast",
  churn: "/churn",
  segmentation: "/segmentation",
  anomaly: "/anomaly",
  "demand-forecast": "/demand-forecast",
};

export function OverviewCards({ summaries }: { summaries: UseCaseSummary[] }) {
  return (
    <div className={styles.grid}>
      {summaries.map((s) => (
        <Link key={s.key} href={HREF[s.key] ?? "/"} className={`card ${styles.card}`}>
          <div className={styles.label}>{s.label}</div>
          <div className={styles.headline}>{s.headline}</div>
          <div className={styles.detail}>{s.detail}</div>
        </Link>
      ))}
    </div>
  );
}
