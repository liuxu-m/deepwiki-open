import { NextRequest, NextResponse } from 'next/server'

const BACKEND = process.env.SERVER_BASE_URL || 'http://localhost:8001'

export async function GET() {
  try {
    const res = await fetch(`${BACKEND}/api/tasks`, { cache: 'no-store' })
    const data = await res.json()
    return NextResponse.json(data, { status: res.status })
  } catch (error) {
    console.error('Error fetching tasks:', error)
    return NextResponse.json({ error: String(error) }, { status: 500 })
  }
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json()
    const res = await fetch(`${BACKEND}/api/tasks`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    const data = await res.json()
    return NextResponse.json(data, { status: res.status })
  } catch (error) {
    console.error('Error creating task:', error)
    return NextResponse.json({ error: String(error) }, { status: 500 })
  }
}
