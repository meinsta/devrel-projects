import { NextRequest, NextResponse } from "next/server";

export async function POST(req: NextRequest) {
  try {
    const { topicA, topicB } = await req.json();

    if (!topicA || !topicB) {
      return NextResponse.json(
        { error: "Both topics are required" },
        { status: 400 }
      );
    }

    return NextResponse.json({
      imageId: null,
      imageUrl: null,
      message: "Image generation not available in serverless mode",
    });
  } catch {
    return NextResponse.json(
      { error: "Failed to generate image" },
      { status: 500 }
    );
  }
}
