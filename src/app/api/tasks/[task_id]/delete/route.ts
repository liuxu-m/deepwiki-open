import { NextRequest, NextResponse } from 'next/server'

const PYTHON_BACKEND_URL = process.env.PYTHON_BACKEND_HOST || 'http://localhost:8001'

export async function DELETE(
  _req: NextRequest,
  { params }: { params: Promise<{ task_id: string }> }
) {
  const { task_id } = await params
  try {
    const res = await fetch(`${PYTHON_BACKEND_URL}/api/tasks/${task_id}/delete`, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Delete failed' }))
      return NextResponse.json(err, { status: res.status })
    }
    return NextResponse.json(await res.json())
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e)
    return NextResponse.json({ error: msg }, { status: 502 })
  }
}
