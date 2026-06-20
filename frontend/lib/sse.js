import { API_BASE_URL, ApiError } from "@/lib/api";

/**
 * POST a JSON body and consume a Server-Sent Events stream.
 *
 * EventSource only supports GET, so we use fetch + a ReadableStream reader and
 * parse SSE frames by hand. Each frame ("event:" + "data:" lines, separated by a
 * blank line) is delivered to onEvent(eventName, parsedData).
 */
export async function streamSSE(path, body, { onEvent, signal } = {}) {
  const url = `${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify(body),
    signal,
  });

  if (!res.ok || !res.body) {
    const payload = await res.json().catch(() => null);
    const envelope = payload?.error;
    throw new ApiError(envelope?.message ?? `Stream failed (${res.status})`, {
      status: res.status,
      code: envelope?.code,
    });
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let boundary;
    while ((boundary = buffer.indexOf("\n\n")) !== -1) {
      const frame = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);

      let event = "message";
      const dataLines = [];
      for (const line of frame.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
      }
      if (dataLines.length === 0) continue;

      let data = {};
      try {
        data = JSON.parse(dataLines.join("\n"));
      } catch {
        data = { raw: dataLines.join("\n") };
      }
      onEvent?.(event, data);
    }
  }
}
