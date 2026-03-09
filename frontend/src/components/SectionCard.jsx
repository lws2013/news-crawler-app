export default function SectionCard({ children, className = '' }) {
  return <section className={`card ${className}`}>{children}</section>;
}