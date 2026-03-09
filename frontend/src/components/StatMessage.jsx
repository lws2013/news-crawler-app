export default function StatMessage({ type = 'info', title, message }) {
  if (!title && !message) return null;

  return (
    <div className={`status-box ${type}`}>
      <div className="status-title">{title}</div>
      {message ? <div className="status-message">{message}</div> : null}
    </div>
  );
}