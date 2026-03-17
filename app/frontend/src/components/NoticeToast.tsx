import { notices, dismissNotice } from '../state/signals';

export function NoticeToast() {
  const items = notices.value;
  if (!items.length) return null;

  return (
    <>
      {items.map(n => (
        <div
          key={n.id}
          class={`notice ${n.kind}`}
          style={{ display: 'block', cursor: 'pointer' }}
          onClick={() => dismissNotice(n.id)}
        >
          {n.msg}
        </div>
      ))}
    </>
  );
}
