import { NextRequest, NextResponse } from 'next/server'

const BACKEND = process.env.SERVER_BASE_URL || 'http://localhost:8001'

export async function GET(
  _req: NextRequest,
  { params }: { params: { task_id: string } }
) {
  try {
    const res = await fetch(`${BACKEND}/api/tasks/${params.task_id}`, { cache: 'no-store' })
    const data = await res.json()
    return NextResponse.json(data, { status: res.status })
  } catch (error) {
    console.error('Error fetching task:', error)
    return NextResponse.json({ error: String(error) }, { status: 500 })
  }
}

export async function DELETE(
  _req: NextRequest,
  { params }: { params: { task_id: string } }
) {
  try {
    const res = await fetch(`${BACKEND}/api/tasks/${params.task_id}`, { method: 'DELETE' })
    const data = await res.json()
    return NextResponse.json(data, { status: res.status })
  } catch (error) {
    console.error('Error cancelling task:', error)
    return NextResponse.json({ error: String(error) }, { status: 500 })
  }
}
