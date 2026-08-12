import Link from "next/link";
import styles from "./Nav.module.css";

const LINKS = [
  { href: "/", label: "概要" },
  { href: "/sales-forecast", label: "売上予測" },
  { href: "/churn", label: "解約予測" },
  { href: "/segmentation", label: "顧客分類" },
  { href: "/anomaly", label: "異常検知" },
  { href: "/demand-forecast", label: "需要予測" },
  { href: "/ask", label: "AIに質問する" },
];

export default function Nav() {
  return (
    <header className={styles.header}>
      <div className={styles.inner}>
        <Link href="/" className={styles.brand}>
          Data Engineer Pilot
          <span className={styles.brandSub}>BigQuery ML 想定 5機能パイロット</span>
        </Link>
        <nav className={styles.nav}>
          {LINKS.map((link) => (
            <Link key={link.href} href={link.href} className={styles.navLink}>
              {link.label}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  );
}
