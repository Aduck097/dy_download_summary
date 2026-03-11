interface SectionHeaderProps {
  eyebrow?: string;
  title: string;
  body?: string;
}

export function SectionHeader({ eyebrow, title, body }: SectionHeaderProps) {
  return (
    <div className="section-header">
      {eyebrow ? <div className="section-eyebrow">{eyebrow}</div> : null}
      <h2>{title}</h2>
      {body ? <p>{body}</p> : null}
    </div>
  );
}
