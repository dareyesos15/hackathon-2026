/** Marcador de incidente en la interfaz: el mismo disco y pictograma que se ve en el mapa. */
import { CATEGORY_ICON } from "@/lib/iconos";
import { CATEGORY_LABEL, TRIAGE_COLOR, type Category, type TriageLevel } from "@/lib/labels";

interface Props {
  category: Category;
  triage?: TriageLevel;
  size?: number;
  className?: string;
}

export function IconoCategoria({ category, triage, size = 28, className = "" }: Props) {
  const fill = triage ? TRIAGE_COLOR[triage] : "transparent";
  const stroke = !triage ? "currentColor" : triage === "medio" ? "#231a1c" : "#ffffff";
  return (
    <svg
      role="img"
      aria-label={CATEGORY_LABEL[category]}
      viewBox="-4 -4 32 32"
      width={size}
      height={size}
      className={`shrink-0 ${className}`}
    >
      {triage && <circle cx="12" cy="12" r="15" fill={fill} />}
      <path
        d={CATEGORY_ICON[category]}
        fill="none"
        stroke={stroke}
        strokeWidth={2.3}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
