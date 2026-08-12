import type { ChurnCustomer } from "@/lib/types";

const TIER_BADGE: Record<string, string> = { high: "badgeRed", medium: "badgeYellow", low: "badgeGray" };
const TIER_LABEL: Record<string, string> = { high: "高", medium: "中", low: "低" };

export function ChurnRiskTable({ customers }: { customers: ChurnCustomer[] }) {
  return (
    <table>
      <thead>
        <tr>
          <th>顧客ID</th>
          <th>解約確率</th>
          <th>リスク</th>
          <th>プラン</th>
          <th>地域</th>
          <th>在籍日数</th>
        </tr>
      </thead>
      <tbody>
        {customers.map((c) => (
          <tr key={c.customer_id}>
            <td>{c.customer_id}</td>
            <td>{(c.churn_probability * 100).toFixed(1)}%</td>
            <td>
              <span className={`badge ${TIER_BADGE[c.risk_tier]}`}>{TIER_LABEL[c.risk_tier]}</span>
            </td>
            <td>{c.plan_type}</td>
            <td>{c.region}</td>
            <td>{c.tenure_days}日</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
