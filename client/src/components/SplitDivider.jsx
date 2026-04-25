import { useCallback, useRef } from 'react';

export default function SplitDivider({ onDrag }) {
  const dragging = useRef(false);

  const onPointerDown = useCallback((e) => {
    e.preventDefault();
    dragging.current = true;
    document.body.style.cursor = 'row-resize';
    document.body.style.userSelect = 'none';

    const onPointerMove = (e) => {
      if (dragging.current) onDrag(e.clientY);
    };

    const onPointerUp = () => {
      dragging.current = false;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      document.removeEventListener('pointermove', onPointerMove);
      document.removeEventListener('pointerup', onPointerUp);
    };

    document.addEventListener('pointermove', onPointerMove);
    document.addEventListener('pointerup', onPointerUp);
  }, [onDrag]);

  return (
    <div className="split-divider" onPointerDown={onPointerDown}>
      <div className="split-divider__handle" />
    </div>
  );
}
