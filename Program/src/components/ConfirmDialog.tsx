import { useEffect, useRef, type ReactNode } from 'react'

/** A native modal dialog: focus moves in, Escape closes it, and focus returns to the opener while it is still there. */
export function ConfirmDialog({ title, children, onClose, actions }: { title: string; children: ReactNode; onClose: () => void; actions: ReactNode }) {
  const dialog = useRef<HTMLDialogElement>(null)
  useEffect(() => {
    const element = dialog.current
    const opener = document.activeElement as HTMLElement | null
    element?.showModal()
    // When the dialog removed what opened it (a deleted item), continue from the top of the view.
    return () => { element?.close(); (opener?.isConnected ? opener : document.getElementById('main'))?.focus({ preventScroll: true }) }
  }, [])
  return (
    <dialog ref={dialog} className="dialog" aria-labelledby="dialog-title" onClose={onClose} onCancel={onClose}>
      <h2 id="dialog-title">{title}</h2>
      <div className="dialog-body">{children}</div>
      <div className="dialog-actions">{actions}</div>
    </dialog>
  )
}
