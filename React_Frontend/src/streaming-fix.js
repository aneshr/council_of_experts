/*
DROP-IN STREAMING FIX (MINIMAL CHANGE)

How to use:
1. Replace ONLY your stream-reading logic with the function below.
2. Keep your existing UI, components, and project structure.
3. This parses NDJSON and appends content per expert.

Assumes message shape:
{ role: "assistant", expert: "<ExpertName>", content: "" }
*/

export async function handleNDJSONStream(response, setMessages) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    const lines = buffer.split("\n");
    buffer = lines.pop(); // keep incomplete JSON

    for (const line of lines) {
      if (!line.trim()) continue;

      const data = JSON.parse(line);

      if (data.event === "end") continue;

      const { expert, content } = data;

      setMessages(prev => {
        const copy = [...prev];
        const idx = copy.findIndex(
          m => m.role === "assistant" && m.expert === expert
        );

        if (idx !== -1) {
          copy[idx] = {
            ...copy[idx],
            content: copy[idx].content + content
          };
        }

        return copy;
      });
    }
  }
}
