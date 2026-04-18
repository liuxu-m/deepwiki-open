import { NextResponse } from 'next/server';

const PYTHON_BACKEND_URL = process.env.PYTHON_BACKEND_HOST || 'http://localhost:8001';

interface RouteContext {
  params: Promise<{
    project_id: string;
  }>;
}

export async function PUT(request: Request, context: RouteContext) {
  try {
    const { project_id } = await context.params;
    const body = await request.text();

    const response = await fetch(
      `${PYTHON_BACKEND_URL}/api/processed_projects/${encodeURIComponent(project_id)}/note`,
      {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body,
      }
    );

    const text = await response.text();
    return new NextResponse(text, {
      status: response.status,
      headers: {
        'Content-Type': response.headers.get('Content-Type') || 'application/json',
      },
    });
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : 'An unknown error occurred';
    return NextResponse.json(
      { detail: `Failed to update project note: ${message}` },
      { status: 500 }
    );
  }
}
