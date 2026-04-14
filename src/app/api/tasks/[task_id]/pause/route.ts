import { NextRequest, NextResponse } from 'next/server'

const BACKEND = process.env.SERVER_BASE_URL || 'http://localhost:8001'

export async function POST(
  _req: NextRequest,
  { params }: { params: { task_id: string } }
) {
  try {
    const res = await fetch(`${BACKEND}/api/tasks/${params.task_id}/pause`, {
      method: 'POST',
    })
    const data = await res.json()
    return NextResponse.json(data, { status: res.status })
  } catch (error) {
    console.error('Error pausing task:', error)
    return NextResponse.json({ error: String(error) }, { status: 500 })
  }
}
